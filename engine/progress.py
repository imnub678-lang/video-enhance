"""進度協議：worker 以 JSON 行寫 stderr，GUI 逐行解析。"""
from __future__ import annotations

import json
import sys

STAGES = ("probe", "sr", "fi", "encode")


def emit(stage: str, done: int, total: int) -> None:
    sys.stderr.write(json.dumps({"stage": stage, "done": done, "total": total}) + "\n")
    sys.stderr.flush()


def parse(line: str) -> dict | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or "stage" not in obj:
        return None
    return obj
