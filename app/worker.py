"""worker 入口：被 GUI 以子進程啟動。"""
from __future__ import annotations

import argparse
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from engine.encoders import load as load_profile  # noqa: E402
from engine.pipeline import run  # noqa: E402
from engine.policy import MODEL_CHOICES, Options, decide  # noqa: E402
from engine.probe import probe  # noqa: E402
from engine.progress import emit  # noqa: E402

DEFAULT_OUTPUT_DIR = pathlib.Path(r"D:\AI視頻完成品")


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
    return ap


def _resolve_output(args) -> str:
    if args.output:
        return args.output
    stem = pathlib.Path(args.input).stem
    title = args.title or stem
    name = f"{title}_{args.subtitle}" if args.subtitle else title
    return str(DEFAULT_OUTPUT_DIR / f"{name}.mp4")


def main(argv: list[str] | None = None) -> int:
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
        info = probe(args.input)
    except Exception as exc:  # noqa: BLE001
        print(f"讀取素材資訊失敗：{exc}", file=sys.stderr)
        return 2

    opts = Options(do_sr=args.sr, do_fi=args.fi, model=args.model,
                   target_fps=args.fps)
    plan = decide(info, opts)
    if plan.reject_reason:
        print(f"拒絕處理：{plan.reject_reason}", file=sys.stderr)
        return 3
    if args.fi and not plan.do_fi:
        print(f"來源已是 {info.fps:.2f}fps，未達目標 {args.fps}fps 之上，補幀略過",
              file=sys.stderr)

    emit("probe", info.frame_count, info.frame_count)
    try:
        run(args.input, _resolve_output(args), opts, profile, args.models_dir)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
