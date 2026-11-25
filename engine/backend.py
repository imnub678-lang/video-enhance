"""執行後端偵測：ffmpeg 位置、推論裝置、可用編碼器。

所有「這台機器能不能跑」的判斷集中在這裡，其餘模組只問結果。
"""
from __future__ import annotations

import ctypes
import functools
import os
import pathlib
import shutil
import subprocess
import sys

import torch

NO_WINDOW = subprocess.CREATE_NO_WINDOW


def _exe_dir() -> pathlib.Path:
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parents[1]


def _resolve_media_tool(name: str) -> str:
    override = os.environ.get(f"VIDEOTOOL_{name.upper()}")
    if override and pathlib.Path(override).exists():
        return override

    base = _exe_dir()
    exe = f"{name}.exe"
    for candidate in (base / "tools" / exe, base / "_internal" / "tools" / exe):
        if candidate.exists():
            return str(candidate)

    return shutil.which(name) or name


def resolve_ffmpeg() -> str:
    return _resolve_media_tool("ffmpeg")


def resolve_ffprobe() -> str:
    return _resolve_media_tool("ffprobe")


def _tool_works(path: str) -> bool:
    try:
        return subprocess.run([path, "-version"], capture_output=True,
                              creationflags=NO_WINDOW, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@functools.lru_cache(maxsize=1)
def device() -> str:
    override = os.environ.get("VIDEOTOOL_DEVICE")
    if override:
        return override
    return "cuda" if torch.cuda.is_available() else "cpu"


@functools.lru_cache(maxsize=1)
def vendor() -> str:
    """nvidia / amd / cpu。ROCm 版 torch 也用 torch.cuda.* 介面，靠 torch.version.hip 分辨。"""
    if device() != "cuda" or not torch.cuda.is_available():
        return "cpu"
    if getattr(torch.version, "hip", None):
        return "amd"
    try:
        name = torch.cuda.get_device_name(0).lower()
    except Exception:  # noqa: BLE001
        return "nvidia"
    if "amd" in name or "radeon" in name or "gfx" in name:
        return "amd"
    return "nvidia"


@functools.lru_cache(maxsize=1)
def vram_gb() -> float | None:
    if device() != "cuda" or not torch.cuda.is_available():
        return None
    try:
        return round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1)
    except Exception:  # noqa: BLE001
        return None


@functools.lru_cache(maxsize=1)
def dtype() -> torch.dtype:
    return torch.float16 if device() == "cuda" else torch.float32


@functools.lru_cache(maxsize=1)
def has_trt() -> bool:
    """TensorRT 只在 NVIDIA 上有意義。"""
    if vendor() != "nvidia":
        return False
    try:
        import tensorrt  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


@functools.lru_cache(maxsize=1)
def ffmpeg_encoders() -> frozenset[str]:
    try:
        res = subprocess.run([resolve_ffmpeg(), "-hide_banner", "-encoders"],
                             capture_output=True, creationflags=NO_WINDOW, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    names = set()
    for line in res.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V"):
            names.add(parts[1])
    return frozenset(names)


@functools.lru_cache(maxsize=16)
def _hardware_encoder_works(codec: str, width: int, height: int) -> bool:
    try:
        result = subprocess.run([resolve_ffmpeg(), "-v", "error", "-f", "lavfi",
                                 "-i", f"color=size={width}x{height}:rate=1", "-frames:v", "1",
                                 "-c:v", codec, "-pix_fmt", "yuv420p10le", "-f", "null", "-"],
                                capture_output=True, creationflags=NO_WINDOW, timeout=15)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def effective_codec(preferred: str, width: int, height: int) -> str:
    """選擇 FFmpeg 與輸出尺寸都支援的 10-bit 編碼器。"""
    chain = {
        "nvidia": ("hevc_nvenc", "libx265"),
        "amd": ("hevc_amf", "libx265"),
        "cpu": ("libx265",),
    }[vendor()]
    available = ffmpeg_encoders()
    ordered = (preferred, *(codec for codec in chain if codec != preferred)) if preferred in chain else chain
    for codec in ordered:
        if codec in available and (codec == "libx265" or _hardware_encoder_works(codec, width, height)):
            return codec
    raise RuntimeError("無法使用 HEVC 編碼器，請使用提供 libx265 的 FFmpeg。")


def describe() -> dict:
    """給首啟掃描與診斷用。"""
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    ram_gb = None
    if sys.platform == "win32":
        try:
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(mem)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            ram_gb = round(mem.ullTotalPhys / 2**30, 1)
        except (AttributeError, OSError):
            pass

    disk_free_gb = None
    try:
        base = os.environ.get("LOCALAPPDATA") or str(pathlib.Path.home())
        disk_free_gb = round(shutil.disk_usage(base).free / 2**30, 1)
    except OSError:
        pass

    info = {
        "device": device(),
        "vendor": vendor(),
        "torch": torch.__version__,
        "cuda": getattr(torch.version, "cuda", None),
        "hip": getattr(torch.version, "hip", None),
        "gpu": None,
        "vram_gb": vram_gb(),
        "cpu_cores": os.cpu_count(),
        "ram_gb": ram_gb,
        "disk_free_gb": disk_free_gb,
        "trt": has_trt(),
        "ffmpeg": resolve_ffmpeg(),
        "ffprobe": resolve_ffprobe(),
        "media_tools_ok": all(_tool_works(path) for path in (resolve_ffmpeg(), resolve_ffprobe())),
        "encoders": sorted(ffmpeg_encoders()),
    }
    if device() == "cuda" and torch.cuda.is_available():
        try:
            info["gpu"] = torch.cuda.get_device_name(0)
        except Exception:  # noqa: BLE001
            pass
    return info
