"""依素材屬性與預設決定處理計畫。純函式，無 IO。"""
from __future__ import annotations

from dataclasses import dataclass

from engine.probe import VideoInfo

TARGET_FPS = 60
TARGET_W = 3840
TARGET_H = 2160

DEFAULT_TILE = 768


@dataclass(frozen=True)
class Plan:
    scale: int
    tile: int
    do_sr: bool
    do_fi: bool
    target_fps: int
    reject_reason: str | None


def decide(info: VideoInfo, preset: str) -> Plan:
    if info.is_hdr or info.is_10bit:
        return _reject("HDR／10-bit 輸入不支援")
    if info.frame_count < 2:
        return _reject("素材幀數不足（少於 2 幀），無法補幀")

    do_sr = preset != "fi_only"
    do_fi = preset != "sr_only" and info.fps < TARGET_FPS

    if do_sr and info.width * info.height > 1920 * 1080:
        return _reject("解析度已高於 1080p，超分無意義；可改用「只補幀」預設")

    scale = 4 if do_sr else 0
    tile = DEFAULT_TILE if do_sr else 0
    return Plan(scale=scale, tile=tile, do_sr=do_sr, do_fi=do_fi,
                target_fps=TARGET_FPS, reject_reason=None)


def _reject(reason: str) -> Plan:
    return Plan(scale=0, tile=0, do_sr=False, do_fi=False,
                target_fps=TARGET_FPS, reject_reason=reason)
