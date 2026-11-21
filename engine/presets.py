"""預設載入。"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

DEFAULT_DIR = pathlib.Path(__file__).resolve().parent.parent / "presets"


@dataclass(frozen=True)
class Preset:
    name: str
    label: str
    do_sr: bool
    do_fi: bool
    model: str
    tile: int
    encoder: str
    crf: int


def load(name: str, presets_dir: str | pathlib.Path = DEFAULT_DIR) -> Preset:
    path = pathlib.Path(presets_dir) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"預設不存在：{name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["name"] = name
    return Preset(**data)


def all_presets(presets_dir: str | pathlib.Path = DEFAULT_DIR) -> list[Preset]:
    d = pathlib.Path(presets_dir)
    return [load(p.stem, d) for p in sorted(d.glob("*.json"))]
