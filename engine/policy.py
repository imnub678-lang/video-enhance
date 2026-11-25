"""依素材屬性與使用者選項決定處理計畫。純函式，無 IO。"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

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

# 給一般使用者的兩個白話維度，內部映射到上面的技術模型。
QUALITY_CHOICES = ("fast", "standard", "best")
CONTENT_CHOICES = ("live", "anime")


def qualities_for(content: str) -> tuple[str, ...]:
    """動畫只有輕量與強力兩個模型，畫質就只給快／最佳，避免兩個選項對到同一個模型。"""
    return ("fast", "best") if content == "anime" else QUALITY_CHOICES


def resolve_model(quality: str, content: str, src_height: int) -> str:
    if content == "anime":
        return "anime" if quality == "fast" else "anime-x4"
    if quality == "fast":
        return "light"
    if quality == "best":
        return "x4plus"
    # 標準＋實拍：1080p 以上用 x2（剛好 2 倍，沒有多餘重採樣）；
    # 低於 1000p 時 x2 到不了 4K，改用 4× 輕量。
    return "x2plus" if src_height >= 1000 else "light"


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


def tile_for_vram(base: int, vram: float | None) -> int:
    """顯存越小分塊越小，避免 4K 輸出時 OOM。sr.py 另有 OOM 時再降一級的保險。"""
    if vram is None or vram >= 12:
        return base
    if vram >= 8:
        return min(base, 512)
    if vram >= 6:
        return min(base, 384)
    return min(base, 256)


def decide(info: VideoInfo, opts: Options, vram: float | None = None) -> Plan:
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

    # 高平均幀率的 VFR 素材仍可能含有需要補幀的間隔。允許少量時間戳捨入誤差。
    has_gaps = opts.do_fi and any(b - a > 1.05 / opts.target_fps for a, b in pairwise(info.frame_times))
    do_sr = opts.do_sr
    do_fi = opts.do_fi and (opts.target_fps > round(info.fps) or has_gaps)

    if not do_sr and not do_fi:
        return _reject(
            f"來源已是 {info.fps:.2f}fps，達到目標 {opts.target_fps}fps，"
            "且沒有勾選超分，沒有事情可做")

    model, scale, tile = MODEL_CHOICES[opts.model]
    tile = tile_for_vram(tile, vram)
    return Plan(scale=scale if do_sr else 0,
                tile=tile if do_sr else 0,
                do_sr=do_sr, do_fi=do_fi,
                target_fps=opts.target_fps,
                reject_reason=None,
                model=model if do_sr else "")


def _reject(reason: str) -> Plan:
    return Plan(scale=0, tile=0, do_sr=False, do_fi=False,
                target_fps=DEFAULT_TARGET_FPS, reject_reason=reason)
