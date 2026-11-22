"""依素材屬性與使用者選項決定處理計畫。純函式，無 IO。"""
from __future__ import annotations

from dataclasses import dataclass

from engine.probe import VideoInfo

TARGET_W = 3840
TARGET_H = 2160
DEFAULT_TILE = 768

DEFAULT_TARGET_FPS = 60
ALLOWED_TARGET_FPS = (60, 120)

# 模型選項：(權重名稱, 放大倍率, 分塊大小)
# RRDBNet 吃顯存，tile 要比 SRVGG 小一半。
MODEL_CHOICES: dict[str, tuple[str, int, int]] = {
    "light": ("realesr-general-x4v3", 4, DEFAULT_TILE),
    "anime": ("realesr-animevideov3", 4, DEFAULT_TILE),
    "anime-x4": ("RealESRGAN_x4plus_anime_6B", 4, 384),
    "x2plus": ("RealESRGAN_x2plus", 2, 384),
    "x4plus": ("RealESRGAN_x4plus", 4, 384),
}
DEFAULT_MODEL = "light"


@dataclass(frozen=True)
class Options:
    do_sr: bool = True
    do_fi: bool = True
    model: str = DEFAULT_MODEL
    target_fps: int = DEFAULT_TARGET_FPS


@dataclass(frozen=True)
class Plan:
    scale: int
    tile: int
    do_sr: bool
    do_fi: bool
    target_fps: int
    reject_reason: str | None
    model: str = ""


def decide(info: VideoInfo, opts: Options) -> Plan:
    if opts.model not in MODEL_CHOICES:
        raise ValueError(f"未知模型：{opts.model}")
    if opts.target_fps not in ALLOWED_TARGET_FPS:
        raise ValueError(f"目標幀率只支援 {ALLOWED_TARGET_FPS}，收到 {opts.target_fps}")

    if not opts.do_sr and not opts.do_fi:
        return _reject("超分與補幀都沒有勾選，沒有事情可做")
    if info.is_hdr:
        return _reject("HDR 輸入不支援（SDR 10-bit 可以）")
    if opts.do_fi and info.frame_count < 2:
        return _reject("素材幀數不足（少於 2 幀），無法補幀")
    if opts.do_sr and info.width * info.height >= TARGET_W * TARGET_H:
        return _reject("解析度已達 4K，超分無意義；可取消勾選超分")

    # 來源已達目標幀率時，補幀無意義，略過（由呼叫端記錄提示）。
    do_sr = opts.do_sr
    do_fi = opts.do_fi and opts.target_fps > round(info.fps)

    if not do_sr and not do_fi:
        return _reject(
            f"來源已是 {info.fps:.2f}fps，達到目標 {opts.target_fps}fps，"
            "且沒有勾選超分，沒有事情可做")

    model, scale, tile = MODEL_CHOICES[opts.model]
    return Plan(scale=scale if do_sr else 0,
                tile=tile if do_sr else 0,
                do_sr=do_sr, do_fi=do_fi,
                target_fps=opts.target_fps,
                reject_reason=None,
                model=model if do_sr else "")


def _reject(reason: str) -> Plan:
    return Plan(scale=0, tile=0, do_sr=False, do_fi=False,
                target_fps=DEFAULT_TARGET_FPS, reject_reason=reason)
