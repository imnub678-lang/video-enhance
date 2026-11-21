"""輸出幀排程：以時間戳而非幀序號決定每個輸出幀從哪兩張來源幀插值。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FramePlan:
    out_index: int
    src_a: int
    src_b: int
    t: float


def schedule(n_src: int, src_fps: float, target_fps: int) -> list[FramePlan]:
    if n_src < 1:
        return []
    if src_fps <= 0:
        src_fps = float(target_fps)

    n_out = max(1, round(n_src * target_fps / src_fps))
    plans: list[FramePlan] = []
    for i in range(n_out):
        pos = i * src_fps / target_fps
        a = int(pos)
        if a >= n_src:
            a = n_src - 1
        t = pos - a
        b = a + 1 if t > 1e-6 else a
        if b >= n_src:
            b = n_src - 1
            t = 0.0 if b == a else t
        plans.append(FramePlan(out_index=i, src_a=a, src_b=b, t=t))
    return plans
