"""端到端管線：解碼 → 超分 → 補幀 → 編碼。"""
from __future__ import annotations

import pathlib

from engine.ffmpeg_pipe import Decoder, Encoder
from engine.policy import TARGET_H, TARGET_W, decide
from engine.presets import load
from engine.probe import probe
from engine.progress import emit
from engine.timestamps import FramePlan, schedule


def _even(n: int) -> int:
    return n + (n % 2)


def _decoded_size(width: int, height: int, rotation: int) -> tuple[int, int]:
    if rotation in (90, 270):
        width, height = height, width
    return _even(width), _even(height)


def run(input_path: str, output_path: str, preset: str,
        models_dir: str = "models", on_progress=None) -> None:
    info = probe(input_path)
    plan = decide(info, preset)
    if plan.reject_reason:
        raise ValueError(plan.reject_reason)

    p = load(preset)
    dec_w, dec_h = _decoded_size(info.width, info.height, info.rotation)
    out_w, out_h = (TARGET_W, TARGET_H) if plan.do_sr else (dec_w, dec_h)

    src_fps = info.frame_count / info.duration if info.duration > 0 else info.fps
    if src_fps <= 0:
        src_fps = float(info.fps or 24)

    if plan.do_fi:
        plans = schedule(info.frame_count, src_fps, plan.target_fps)
        enc_fps = plan.target_fps
    else:
        plans = [FramePlan(i, i, i, 0.0) for i in range(info.frame_count)]
        enc_fps = max(1, round(src_fps))

    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    sr = interp = None
    if plan.do_sr:
        from engine.models import ensure_model
        from engine.sr import SuperResolver

        weights = ensure_model(p.model, models_dir)
        sr = SuperResolver(weights, plan.scale, plan.tile)
    if plan.do_fi:
        from engine.fi import Interpolator
        from engine.models import ensure_model

        interp = Interpolator(ensure_model("rife426", models_dir))

    subtitle = "mov_text" if "mov_text" in info.subtitle_codecs else None
    dec = Decoder(input_path, dec_w, dec_h, info.frame_count)
    enc = Encoder(output_path, out_w, out_h, enc_fps, input_path,
                  info.audio_codec, subtitle, crf=p.crf, codec=p.encoder)

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
                    if sr is not None:
                        frame = sr.upscale_to(frame, out_h, out_w)
                    pending[next_src] = frame
                    last_frame = frame
                    next_src += 1

            a = pending.get(fp.src_a, last_frame)
            b = pending.get(fp.src_b, a)
            if a is None:
                break
            out = interp.blend(a, b, fp.t) if (interp is not None and fp.t > 0) else a
            enc.write(out)

            for k in [k for k in pending if k < fp.src_a]:
                del pending[k]
            if n % 10 == 0 or n == total:
                if on_progress:
                    on_progress(stage="fi" if interp else "sr", done=n, total=total)
                else:
                    emit("fi" if interp else "sr", n, total)
    finally:
        dec.close()
        enc.close()
