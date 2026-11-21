"""worker 入口：被 GUI 以子進程啟動。"""
from __future__ import annotations

import argparse
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from engine.pipeline import run  # noqa: E402
from engine.policy import decide
from engine.presets import load
from engine.probe import probe
from engine.progress import emit

DEFAULT_OUTPUT_DIR = pathlib.Path(r"D:\AI視頻完成品")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="worker")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output")
    ap.add_argument("--preset", default="balanced")
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
        load(args.preset)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        info = probe(args.input)
    except Exception as exc:  # noqa: BLE001
        print(f"讀取素材資訊失敗：{exc}", file=sys.stderr)
        return 2

    plan = decide(info, args.preset)
    if plan.reject_reason:
        print(f"拒絕處理：{plan.reject_reason}", file=sys.stderr)
        return 3

    emit("probe", info.frame_count, info.frame_count)
    try:
        run(args.input, _resolve_output(args), args.preset, args.models_dir)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
