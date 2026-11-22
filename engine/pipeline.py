"""端到端管線：解碼 → 超分 → 補幀 → 編碼。"""
from __future__ import annotations

import pathlib

import torch

from engine.encoders import Profile
from engine.ffmpeg_pipe import Decoder, Encoder
from engine.policy import TARGET_H, TARGET_W, Options, decide
from engine.probe import probe
from engine.progress import emit
from engine.sr import frame_to_tensor, tensor_to_frame
from engine.timestamps import FramePlan, schedule


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


def run(input_path: str, output_path: str, opts: Options, profile: Profile,
        models_dir: str = "models", on_progress=None) -> None:
    info = probe(input_path)
    plan = decide(info, opts)
    if plan.reject_reason:
        raise ValueError(plan.reject_reason)

    dec_w, dec_h = _decoded_size(info.width, info.height, info.rotation)
    out_w, out_h = (TARGET_W, TARGET_H) if plan.do_sr else (dec_w, dec_h)
    plans, enc_fps = _frame_plans(info, plan)

    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    sr = interp = None
    if plan.do_sr:
        from engine.models import ensure_model
        from engine.sr import SuperResolver

        sr = SuperResolver(ensure_model(plan.model, models_dir), plan.scale, plan.tile)
    if plan.do_fi:
        from engine.fi import Interpolator
        from engine.models import ensure_model

        interp = Interpolator(ensure_model("rife426", models_dir))

    subtitle = "mov_text" if "mov_text" in info.subtitle_codecs else None
    dec = Decoder(input_path, dec_w, dec_h, info.frame_count)
    enc = Encoder(output_path, out_w, out_h, enc_fps, input_path,
                  info.audio_codec, subtitle, crf=profile.crf, codec=profile.encoder)

    total = len(plans)
    pending: dict[int, object] = {}
    next_src = 0
    last_frame = None

    try:
        for n, fp in enumerate(plans, start=1):
            for idx in (fp.src_a, fp.src_b):
                while next_src <= idx:
                    frame = dec.read()
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
            enc.write(tensor_to_frame(out))

            for k in [k for k in pending if k < fp.src_a]:
                del pending[k]
            if n % 10 == 0 or n == total:
                if on_progress:
                    on_progress(stage="fi" if interp else "sr", done=n, total=total)
                else:
                    emit("fi" if interp else "sr", n, total)
    finally:
        try:
            enc.close()
        finally:
            try:
                dec.close()
            except RuntimeError:
                pass
