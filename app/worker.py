"""worker 入口：被 GUI 以子進程啟動。"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from engine import backend  # noqa: E402
from engine.encoders import load as load_profile  # noqa: E402
from engine.output import check_output  # noqa: E402
from engine.pipeline import run  # noqa: E402
from engine.policy import MODEL_CHOICES, Options, decide  # noqa: E402
from engine.probe import probe  # noqa: E402
from engine.progress import emit  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="worker")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output")
    ap.add_argument("--sr", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--fi", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--fps", type=int, default=60, choices=[60, 120])
    ap.add_argument("--model", default="light", choices=list(MODEL_CHOICES))
    ap.add_argument("--profile", default="standard")
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--models-dir", default="models")
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    return ap


def _resolve_output(args) -> str:
    if args.output:
        return args.output
    src = pathlib.Path(args.input)
    if not args.title and not args.subtitle:
        return str(src.with_name(f"{src.stem}_enhanced.mp4"))
    title = args.title or src.stem
    name = f"{title}_{args.subtitle}" if args.subtitle else title
    return str(src.parent / f"{name}.mp4")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)

    if not pathlib.Path(args.input).exists():
        print(f"找不到輸入檔：{args.input}", file=sys.stderr)
        return 2
    try:
        profile = load_profile(args.profile)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        out = _resolve_output(args)
        check_output(args.input, out)
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        started = time.perf_counter()
        info = probe(args.input)
        probe_seconds = time.perf_counter() - started
    except Exception as exc:  # noqa: BLE001
        print(f"讀取素材資訊失敗：{exc}", file=sys.stderr)
        return 2

    opts = Options(do_sr=args.sr, do_fi=args.fi, model=args.model,
                   target_fps=args.fps)
    plan = decide(info, opts, backend.vram_gb())
    if plan.reject_reason:
        print(f"拒絕處理：{plan.reject_reason}", file=sys.stderr)
        return 3
    if args.fi and not plan.do_fi:
        print(f"來源已是 {info.fps:.2f}fps，達到目標 {args.fps}fps，補幀略過",
              file=sys.stderr)

    emit("probe", info.frame_count, info.frame_count)
    try:
        def log_timing(timing):
            fields = {"probe": probe_seconds, **timing}
            print("Timing (s): " + ", ".join(f"{key}={value:.2f}" for key, value in fields.items()),
                  file=sys.stderr, flush=True)

        run(args.input, out, opts, profile, args.models_dir,
            resume=args.resume, info=info, on_timing=log_timing)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
