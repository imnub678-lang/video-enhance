"""編碼檔位：只描述輸出編碼參數，與超分／補幀無關。"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

DEFAULT_DIR = pathlib.Path(__file__).resolve().parent.parent / "encoders"
ORDER = ("standard", "fast", "small")


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    encoder: str
    crf: int


def load(name: str, profiles_dir: str | pathlib.Path = DEFAULT_DIR) -> Profile:
    path = pathlib.Path(profiles_dir) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"編碼檔位不存在：{name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["name"] = name
    return Profile(**data)


def all_profiles(profiles_dir: str | pathlib.Path = DEFAULT_DIR) -> list[Profile]:
    """依畫質優先排序，第一個即為介面預設。

    不直接用檔名字母序：那會讓 fast 排最前面而成為預設，
    與 worker 的 --profile 預設值（standard）不一致。
    """
    d = pathlib.Path(profiles_dir)
    names = {p.stem for p in d.glob("*.json")}
    ordered = [n for n in ORDER if n in names] + sorted(names - set(ORDER))
    return [load(n, d) for n in ordered]
