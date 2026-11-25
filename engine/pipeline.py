"""端到端管線：解碼 → 超分 → 補幀 → 編碼。

解碼與編碼各跑一個執行緒，讓 CPU 解碼、GPU 計算、編碼寫入三者重疊。
輸出切成固定長度的片段分別編碼，manifest 記錄已完成片段，中斷後重跑只補缺的。
"""
from __future__ import annotations

import json
import pathlib
import queue
import shutil
import tempfile
import threading
import time

import torch

from engine import backend
from engine.encoders import Profile
from engine.ffmpeg_pipe import Decoder, Encoder, concat_segments
from engine.output import check_output, reserve_output
from engine.policy import TARGET_H, TARGET_W, Options, decide
from engine.probe import VideoInfo, probe
from engine.progress import emit
from engine.sr import frame_to_tensor, tensor_to_frame
from engine.timestamps import FramePlan, schedule, schedule_timestamps

_END = object()
SEGMENT_SECONDS = 10


class _DecodePrefetch(threading.Thread):
    def __init__(self, dec: Decoder, depth: int):
        super().__init__(daemon=True)
        self._dec = dec
        self._q: queue.Queue = queue.Queue(maxsize=depth)
        self._stop_reading = threading.Event()
        self.error: BaseException | None = None
        self.seconds = 0.0

    def run(self) -> None:
        try:
            while not self._stop_reading.is_set():
                start = time.perf_counter()
                frame = self._dec.read()
                self.seconds += time.perf_counter() - start
                if self._stop_reading.is_set():
                    return
                self._q.put(frame)
                if frame is None:
                    return
        except BaseException as exc:  # noqa: BLE001
            self.error = exc
            self._drain()
            self._q.put(None)

    def _drain(self) -> None:
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                return

    def read(self):
        frame = self._q.get()
        if self.error is not None:
            raise self.error
        return frame

    def discard(self) -> None:
        self._stop_reading.set()
        self._drain()


class _EncodeSink(threading.Thread):
    def __init__(self, enc: Encoder, depth: int):
        super().__init__(daemon=True)
        self._enc = enc
        self._q: queue.Queue = queue.Queue(maxsize=depth)
        self.error: BaseException | None = None
        self.copy_seconds = 0.0
        self.seconds = 0.0

    def run(self) -> None:
        try:
            while True:
                item = self._q.get()
                if item is _END:
                    return
                start = time.perf_counter()
                frame = tensor_to_frame(item)
                copied = time.perf_counter()
                self.copy_seconds += copied - start
                self._enc.write(frame)
                self.seconds += time.perf_counter() - copied
        except BaseException as exc:  # noqa: BLE001
            self.error = exc
            while True:
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    break

    def write(self, tensor: torch.Tensor) -> None:
        if self.error is not None:
            raise self.error
        self._q.put(tensor)

    def finish(self) -> None:
        if self.error is None:
            self._q.put(_END)
        self.join()
        if self.error is not None:
            raise self.error


def _even(n: int) -> int:
    return n + (n % 2)


def _decoded_size(width: int, height: int, rotation: int) -> tuple[int, int]:
    if rotation in (90, 270):
        width, height = height, width
    return _even(width), _even(height)


def _output_size(width: int, height: int, *, upscale: bool, aspect: float | None = None) -> tuple[int, int]:
    if not upscale:
        return width, height
    ratio = aspect or width / height
    max_w, max_h = (TARGET_W, TARGET_H) if ratio >= 1 else (TARGET_H, TARGET_W)
    w = min(max_w, max_h * ratio)
    h = w / ratio
    return max(2, 2 * round(w / 2)), max(2, 2 * round(h / 2))


def _src_fps(info) -> float:
    """來源幀率。CFR 用容器回報值（精確），VFR 用幀數／時長推算。

    直接用 frame_count/duration 會帶誤差：容器時長常含音軌尾巴，
    實測 576 幀 / 9.6212 秒 = 59.868（實際 60.0）。這個誤差會讓原本落在
    整數位置的幀變成 t=0.998x，導致每個原幀都白跑一次補幀網路。
    判準用「時長與幀數是否相符」，不受影片長度影響。
    """
    derived = info.frame_count / info.duration if info.duration > 0 else 0.0
    if info.fps and derived > 0:
        if abs(info.duration - info.frame_count / info.fps) <= 0.1:
            return float(info.fps)
        return derived
    return float(info.fps or 24)


def _frame_plans(info, plan) -> tuple[list[FramePlan], float]:
    if plan.do_fi:
        plans = (schedule_timestamps(info.frame_times, info.video_duration, plan.target_fps)
                 if info.frame_times else schedule(info.frame_count, _src_fps(info), plan.target_fps))
        return plans, plan.target_fps
    fps = (info.frame_count / info.video_duration if info.frame_times and
           abs(info.frame_count / (info.fps or 24) - info.video_duration) > 1e-4 else _src_fps(info))
    return ([FramePlan(i, i, i, 0.0) for i in range(info.frame_count)],
            max(1.0, fps))


def _report(on_progress, interp, done: int, total: int) -> None:
    stage = "fi" if interp is not None else "sr"
    if on_progress:
        on_progress(stage=stage, done=done, total=total)
    else:
        emit(stage, done, total)


def _measure_model(model_call, events, frame, *args):
    if frame.is_cuda:
        begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        begin.record()
        result = model_call(frame, *args)
        end.record()
        events.append((begin, end))
        return result, 0.0
    start = time.perf_counter()
    result = model_call(frame, *args)
    return result, time.perf_counter() - start


def _build_models(plan, models_dir: str):
    from engine.models import ensure_model

    device = backend.device()
    dtype = backend.dtype()
    sr = interp = None
    if plan.do_sr:
        from engine.sr import SuperResolver

        sr = SuperResolver(ensure_model(plan.model, models_dir), plan.scale, plan.tile,
                           device=device, dtype=dtype, use_trt=backend.has_trt())
    if plan.do_fi:
        from engine.fi import Interpolator

        interp = Interpolator(ensure_model("rife426", models_dir),
                              device=device, dtype=dtype)
    return sr, interp


def _process(plans: list[FramePlan], dec: Decoder, enc: Encoder, sr, interp,
             out_h: int, out_w: int, *, offset: int = 0, total: int | None = None,
             on_progress=None) -> dict[str, float]:
    """跑一段輸出幀。plans 內的 src_a/src_b 是絕對來源索引，offset 是進度起點。"""
    total = total if total is not None else len(plans)
    depth = max(2, min(8, (256 << 20) // max(1, dec.width * dec.height * 3)))
    prefetch = _DecodePrefetch(dec, depth)
    sink = _EncodeSink(enc, 3)
    prefetch.start()
    sink.start()

    pending: dict[int, torch.Tensor] = {}
    next_src = plans[0].src_a if plans else 0
    inference = 0.0
    gpu_events = []

    try:
        for n, fp in enumerate(plans, start=1):
            for idx in (fp.src_a, fp.src_b):
                while next_src <= idx:
                    frame = prefetch.read()
                    if frame is None:
                        raise RuntimeError(f"解碼提早結束：找不到第 {next_src + 1} 幀")
                    tensor = frame_to_tensor(frame, backend.device(), backend.dtype())
                    if sr is not None:
                        tensor, elapsed = _measure_model(sr.upscale_tensor, gpu_events, tensor, out_h, out_w)
                        inference += elapsed
                    pending[next_src] = tensor
                    next_src += 1

            a, b = pending[fp.src_a], pending[fp.src_b]
            out = a
            if interp is not None and fp.t > 0:
                out, elapsed = _measure_model(interp.blend_tensors, gpu_events, a, b, fp.t)
                inference += elapsed
            sink.write(out)

            for k in [k for k in pending if k < fp.src_a]:
                del pending[k]

            if n % 10 == 0 or n == len(plans):
                _report(on_progress, interp, offset + n, total)
    finally:
        started_wait = time.perf_counter()
        prefetch.discard()
        try:
            sink.finish()
        finally:
            prefetch.join(timeout=10)
    if gpu_events:
        gpu_events[-1][1].synchronize()
        inference += sum(begin.elapsed_time(end) for begin, end in gpu_events) / 1000
    return {"decode": prefetch.seconds, "inference": inference, "frame_copy": sink.copy_seconds,
            "encode": sink.seconds,
            "segment_wait": time.perf_counter() - started_wait}


def _resume_key(input_path: str, info, plan, profile: Profile,
                out_w: int, out_h: int, enc_fps: float, total: int,
                seg_frames: int) -> dict:
    src = pathlib.Path(input_path)
    stat = src.stat()
    return {
        "version": 2,
        "input": str(src.resolve()),
        "size": stat.st_size,
        "mtime": stat.st_mtime_ns,
        "frame_count": info.frame_count,
        "do_sr": plan.do_sr,
        "do_fi": plan.do_fi,
        "model": plan.model,
        "scale": plan.scale,
        "tile": plan.tile,
        "target_fps": plan.target_fps,
        "encoder": backend.effective_codec(profile.encoder, out_w, out_h),
        "crf": profile.crf,
        "out_w": out_w,
        "out_h": out_h,
        "enc_fps": enc_fps,
        "total": total,
        "seg_frames": seg_frames,
    }


def _load_done(parts: pathlib.Path, key: dict) -> set[int]:
    manifest = parts / "manifest.json"
    if not manifest.exists():
        return set()
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if data.get("key") != key:
        shutil.rmtree(parts, ignore_errors=True)
        return set()
    return {int(i) for i in data.get("done", [])}


def _save_done(parts: pathlib.Path, key: dict, done: set[int]) -> None:
    parts.mkdir(parents=True, exist_ok=True)
    tmp = parts / "manifest.json.tmp"
    tmp.write_text(json.dumps({"key": key, "done": sorted(done)}),
                   encoding="utf-8")
    tmp.replace(parts / "manifest.json")


def _encode_segment(slice_plans: list[FramePlan], offset: int, info, input_path: str,
                    seg_path: pathlib.Path, dec_w: int, dec_h: int,
                    out_w: int, out_h: int, enc_fps: float, profile: Profile,
                    sr, interp, total: int, on_progress) -> dict[str, float]:
    src_start = slice_plans[0].src_a
    start_time = 0.0
    if src_start:
        start_time = (info.seek_origin + info.frame_times[src_start] - 1e-6
                      if info.frame_times else src_start / _src_fps(info))
    dec = Decoder(input_path, dec_w, dec_h, info.frame_count - src_start,
                  start_time=start_time)
    enc = Encoder(str(seg_path), out_w, out_h, enc_fps, "", None, None,
                  crf=profile.crf, codec=backend.effective_codec(profile.encoder, out_w, out_h))
    try:
        timing = _process(slice_plans, dec, enc, sr, interp, out_h, out_w,
                          offset=offset, total=total, on_progress=on_progress)
    finally:
        start = time.perf_counter()
        try:
            enc.close()
        finally:
            try:
                dec.close()
            except RuntimeError:
                pass
    timing["segment_wait"] += time.perf_counter() - start
    return timing


def _concat(parts: pathlib.Path, n_seg: int, source: str, output: str, info) -> None:
    listing = parts / "list.txt"
    # FFmpeg 以清單所在目錄解析檔名。不把使用者輸入的目錄寫進清單。
    listing.write_text(
        "".join(f"file 'seg{i:04d}.mp4'\n" for i in range(n_seg)),
        encoding="utf-8")
    subtitle = "mov_text" if "mov_text" in info.subtitle_codecs else None
    index = info.subtitle_codecs.index(subtitle) if subtitle else 0
    concat_segments(str(listing), source, output, info.audio_codec, subtitle, index)


def run(input_path: str, output_path: str, opts: Options, profile: Profile,
        models_dir: str = "models", on_progress=None, resume: bool = True, *,
        info: VideoInfo | None = None, on_timing=None) -> None:
    with reserve_output(output_path):
        out_path = check_output(input_path, output_path)
        _run(input_path, out_path, opts, profile, models_dir, on_progress, resume, info, on_timing)


def _run(input_path: str, out_path: pathlib.Path, opts: Options, profile: Profile,
         models_dir: str, on_progress, resume: bool, info: VideoInfo | None, on_timing) -> None:
    started = time.perf_counter()
    info = info if info is not None else probe(input_path)
    plan = decide(info, opts, backend.vram_gb())
    if plan.reject_reason:
        raise ValueError(plan.reject_reason)

    dec_w, dec_h = _decoded_size(info.width, info.height, info.rotation)
    aspect = info.width * info.pixel_aspect / info.height
    if info.rotation in (90, 270):
        aspect = 1 / aspect
    out_w, out_h = _output_size(dec_w, dec_h, upscale=plan.do_sr, aspect=aspect)
    plans, enc_fps = _frame_plans(info, plan)
    total = len(plans)

    seg_frames = max(1, round(enc_fps * SEGMENT_SECONDS))
    n_seg = max(1, (total + seg_frames - 1) // seg_frames)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts = out_path.parent / f".{out_path.stem}.parts"

    key = _resume_key(input_path, info, plan, profile, out_w, out_h, enc_fps,
                      total, seg_frames)
    if not resume:
        shutil.rmtree(parts, ignore_errors=True)
    done = _load_done(parts, key)
    parts.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    sr, interp = _build_models(plan, models_dir)
    timings = {"models": time.perf_counter() - start, "decode": 0.0, "inference": 0.0,
               "frame_copy": 0.0, "encode": 0.0, "segment_wait": 0.0}

    for i in range(n_seg):
        a = i * seg_frames
        b = min(total, a + seg_frames)
        seg_path = parts / f"seg{i:04d}.mp4"
        if i in done and seg_path.exists():
            _report(on_progress, interp, b, total)
            continue
        elapsed = _encode_segment(plans[a:b], a, info, input_path, seg_path, dec_w, dec_h,
                                  out_w, out_h, enc_fps, profile, sr, interp, total, on_progress)
        for stage, seconds in elapsed.items():
            timings[stage] += seconds
        done.add(i)
        _save_done(parts, key, done)

    start = time.perf_counter()
    with tempfile.TemporaryDirectory(dir=parts) as staging:
        finished = pathlib.Path(staging) / out_path.name
        _concat(parts, n_seg, input_path, str(finished), info)
        # Windows rename fails atomically if another file appeared at the destination.
        finished.rename(out_path)
    shutil.rmtree(parts, ignore_errors=True)
    if on_timing:
        timings["mux"] = time.perf_counter() - start
        timings["total"] = time.perf_counter() - started
        on_timing(timings)
