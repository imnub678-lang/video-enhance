"""依素材屬性與預設決定處理計畫。純函式，無 IO。"""
from __future__ import annotations

from dataclasses import dataclass

from engine.probe import VideoInfo

TARGET_FPS = 60
TARGET_W = 3840
TARGET_H = 2160

DEFAULT_TILE = 768

# 模型選項：(權重名稱, 放大倍率, 分塊大小)
# 空字串表示沿用預設本身的模型。RRDBNet 吃顯存，tile 要比 SRVGG 小一半。
MODEL_CHOICES: dict[str, tuple[str, int, int]] = {
    "light": ("realesr-general-x4v3", 4, DEFAULT_TILE),
    "x2plus": ("RealESRGAN_x2plus", 2, 384),
    "x4plus": ("RealESRGAN_x4plus", 4, 384),
    "anime-x4": ("RealESRGAN_x4plus_anime_6B", 4, 384),
}


@dataclass(frozen=True)
class Plan:
    scale: int
    tile: int
    do_sr: bool
    do_fi: bool
    target_fps: int
    reject_reason: str | None
    model: str = ""


def decide(info: VideoInfo, preset: str, model_choice: str = "auto") -> Plan:
    if model_choice != "auto" and model_choice not in MODEL_CHOICES:
        raise ValueError(f"未知模型選項：{model_choice}")

    if info.is_hdr:
        return _reject("HDR 輸入不支援（SDR 10-bit 可以）")
    if info.frame_count < 2:
        return _reject("素材幀數不足（少於 2 幀），無法補幀")

    do_sr = preset != "fi_only"
    do_fi = preset != "sr_only" and info.fps < TARGET_FPS

    if do_sr and info.width * info.height >= TARGET_W * TARGET_H:
        return _reject("解析度已達 4K，超分無意義；可改用「只補幀」預設")

    if not do_sr:
        return Plan(scale=0, tile=0, do_sr=False, do_fi=do_fi,
                    target_fps=TARGET_FPS, reject_reason=None)

    model, scale, tile = MODEL_CHOICES.get(model_choice, ("", 4, DEFAULT_TILE))
    return Plan(scale=scale, tile=tile, do_sr=True, do_fi=do_fi,
                target_fps=TARGET_FPS, reject_reason=None, model=model)


def _reject(reason: str) -> Plan:
    return Plan(scale=0, tile=0, do_sr=False, do_fi=False,
                target_fps=TARGET_FPS, reject_reason=reason)
