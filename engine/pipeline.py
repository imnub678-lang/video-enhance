"""端到端管線：解碼 → 超分 → 補幀 → 編碼。

解碼與編碼各跑一個執行緒，讓 CPU 解碼、GPU 計算、編碼寫入三者重疊。
輸出切成固定長度的片段分別編碼，manifest 記錄已完成片段，中斷後重跑只補缺的。
"""
from __future__ import annotations

import json
import pathlib
import queue
import shutil
import threading

import torch

from engine.encoders import Profile
from engine.ffmpeg_pipe import Decoder, Encoder, concat_segments
from engine.policy import TARGET_H, TARGET_W, Options, decide
from engine.probe import probe
from engine.progress import emit
from engine.sr import frame_to_tensor, tensor_to_frame
from engine.timestamps import FramePlan, schedule

_END = object()
SEGMENT_SECONDS = 10


class _DecodePrefetch(threading.Thread):
    def __init__(self, dec: Decoder, depth: int):
        super().__init__(daemon=True)
        self._dec = dec
        self._q: queue.Queue = queue.Queue(maxsize=depth)
        self.error: BaseException | None = None

    def run(self) -> None:
        try:
            while True:
                frame = self._dec.read()
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
        """提早結束時清空隊列，讓可能卡在 put 的執行緒繼續跑。"""
        self._drain()


class _EncodeSink(threading.Thread):
    def __init__(self, enc: Encoder, depth: int):
        super().__init__(daemon=True)
        self._enc = enc
        self._q: queue.Queue = queue.Queue(maxsize=depth)
        self.error: BaseException | None = None

    def run(self) -> None:
        try:
            while True:
                item = self._q.get()
                if item is _END:
                    return
                self._enc.write(tensor_to_frame(item))
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


def _src_fps(info) -> float:
    fps = info.frame_count / info.duration if info.duration > 0 else info.fps
    return fps if fps > 0 else float(info.fps or 24)


def _frame_plans(info, plan) -> tuple[list[FramePlan], int]:
    if plan.do_fi:
        return schedule(info.frame_count, _src_fps(info), plan.target_fps), plan.target_fps
    return ([FramePlan(i, i, i, 0.0) for i in range(info.frame_count)],
            max(1, round(_src_fps(info))))


def _report(on_progress, interp, done: int, total: int) -> None:
    stage = "fi" if interp is not None else "sr"
    if on_progress:
        on_progress(stage=stage, done=done, total=total)
    else:
        emit(stage, done, total)


def _build_models(plan, models_dir: str):
    from engine.models import ensure_model

    sr = interp = None
    if plan.do_sr:
        from engine.sr import SuperResolver

        sr = SuperResolver(ensure_model(plan.model, models_dir), plan.scale, plan.tile)
    if plan.do_fi:
        from engine.fi import Interpolator

        interp = Interpolator(ensure_model("rife426", models_dir))
    return sr, interp


def _process(plans: list[FramePlan], dec: Decoder, enc: Encoder, sr, interp,
             out_h: int, out_w: int, *, offset: int = 0, total: int | None = None,
             on_progress=None) -> None:
    """跑一段輸出幀。plans 內的 src_a/src_b 是絕對來源索引，offset 是進度起點。"""
    total = total if total is not None else len(plans)
    depth = max(2, min(8, (256 << 20) // max(1, dec.width * dec.height * 3)))
    prefetch = _DecodePrefetch(dec, depth)
    sink = _EncodeSink(enc, 3)
    prefetch.start()
    sink.start()

    pending: dict[int, torch.Tensor] = {}
    next_src = plans[0].src_a if plans else 0
    last_frame = None

    try:
        for n, fp in enumerate(plans, start=1):
            for idx in (fp.src_a, fp.src_b):
                while next_src <= idx:
                    frame = prefetch.read()
                    if frame is None:
                        break
                    tensor = frame_to_tensor(frame, "cuda", torch.float16)
                    if sr is not None:
                        tensor = sr.upscale_tensor(tensor, out_h, out_w)
                    pending[next_src] = tensor
                    last_frame = tensor
                    next_src += 1

            a = pending.get(fp.src_a, last_frame)
            b = pending.get(fp.src_b, a)
            if a is None:
                break
            out = interp.blend_tensors(a, b, fp.t) if (interp is not None and fp.t > 0) else a
            sink.write(out)

            for k in [k for k in pending if k < fp.src_a]:
                del pending[k]

            if n % 10 == 0 or n == len(plans):
                _report(on_progress, interp, offset + n, total)
    finally:
        try:
            sink.finish()
        finally:
            prefetch.discard()
            prefetch.join(timeout=10)


def _resume_key(input_path: str, info, plan, profile: Profile,
                out_w: int, out_h: int, enc_fps: int, total: int,
                seg_frames: int) -> dict:
    src = pathlib.Path(input_path)
    stat = src.stat()
    return {
        "input": str(src.resolve()),
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
        "frame_count": info.frame_count,
        "do_sr": plan.do_sr,
        "do_fi": plan.do_fi,
        "model": plan.model,
        "scale": plan.scale,
        "tile": plan.tile,
        "target_fps": plan.target_fps,
        "encoder": profile.encoder,
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
                    out_w: int, out_h: int, enc_fps: int, profile: Profile,
                    sr, interp, total: int, on_progress) -> None:
    src_start = slice_plans[0].src_a
    dec = Decoder(input_path, dec_w, dec_h, info.frame_count - src_start,
                  start_time=src_start / _src_fps(info))
    enc = Encoder(str(seg_path), out_w, out_h, enc_fps, "", None, None,
                  crf=profile.crf, codec=profile.encoder)
    try:
        _process(slice_plans, dec, enc, sr, interp, out_h, out_w,
                 offset=offset, total=total, on_progress=on_progress)
    finally:
        try:
            enc.close()
        finally:
            try:
                dec.close()
            except RuntimeError:
                pass


def _concat(parts: pathlib.Path, n_seg: int, source: str, output: str, info) -> None:
    listing = parts / "list.txt"
    listing.write_text(
        "".join(f"file '{(parts / f'seg{i:04d}.mp4').as_posix()}'\n" for i in range(n_seg)),
        encoding="utf-8")
    subtitle = "mov_text" if "mov_text" in info.subtitle_codecs else None
    concat_segments(str(listing), source, output, info.audio_codec, subtitle)


def run(input_path: str, output_path: str, opts: Options, profile: Profile,
        models_dir: str = "models", on_progress=None, resume: bool = True) -> None:
    info = probe(input_path)
    plan = decide(info, opts)
    if plan.reject_reason:
        raise ValueError(plan.reject_reason)

    dec_w, dec_h = _decoded_size(info.width, info.height, info.rotation)
    out_w, out_h = (TARGET_W, TARGET_H) if plan.do_sr else (dec_w, dec_h)
    plans, enc_fps = _frame_plans(info, plan)
    total = len(plans)

    seg_frames = max(1, round(enc_fps * SEGMENT_SECONDS))
    n_seg = max(1, (total + seg_frames - 1) // seg_frames)

    out_path = pathlib.Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts = out_path.parent / f".{out_path.stem}.parts"

    key = _resume_key(input_path, info, plan, profile, out_w, out_h, enc_fps,
                      total, seg_frames)
    if not resume:
        shutil.rmtree(parts, ignore_errors=True)
    done = _load_done(parts, key)
    parts.mkdir(parents=True, exist_ok=True)

    sr, interp = _build_models(plan, models_dir)

    for i in range(n_seg):
        a = i * seg_frames
        b = min(total, a + seg_frames)
        seg_path = parts / f"seg{i:04d}.mp4"
        if i in done and seg_path.exists():
            _report(on_progress, interp, b, total)
            continue
        _encode_segment(plans[a:b], a, info, input_path, seg_path, dec_w, dec_h,
                        out_w, out_h, enc_fps, profile, sr, interp, total, on_progress)
        done.add(i)
        _save_done(parts, key, done)

    _concat(parts, n_seg, input_path, str(out_path), info)
    shutil.rmtree(parts, ignore_errors=True)
