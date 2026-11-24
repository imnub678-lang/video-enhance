"""TensorRT 引擎編譯與磁碟快取。

固定形狀編譯（動態形狀對 TRT 不友善且慢），首次編譯後存成 .pt2，
之後載入只要幾十毫秒。任何環節失敗都回 None，呼叫方退回 eager。
"""
from __future__ import annotations

import os
import pathlib
import sys

import torch

def _cache_dir() -> pathlib.Path:
    override = os.environ.get("VIDEOTOOL_CACHE_DIR")
    if override:
        return pathlib.Path(override)
    if getattr(sys, "frozen", False):
        # 安裝在 Program Files 時不能寫，快取一樣放使用者目錄。
        base = pathlib.Path(os.environ.get("LOCALAPPDATA") or pathlib.Path.home())
        return base / "VideoEnhance" / "trt_cache"
    return pathlib.Path(__file__).resolve().parent.parent / "models" / "trt_cache"


CACHE_DIR = _cache_dir()


def available() -> bool:
    if os.environ.get("VIDEOTOOL_NO_TRT"):
        return False
    try:
        import torch_tensorrt  # noqa: F401
    except Exception:
        return False
    return True


def compile_fixed(model: torch.nn.Module, samples: list[torch.Tensor], key: str,
                  cache_dir: pathlib.Path = CACHE_DIR) -> torch.nn.Module | None:
    if not available():
        return None
    import torch_tensorrt

    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.pt2"

    try:
        if path.exists():
            loaded = torch_tensorrt.load(str(path))
            return loaded.module() if hasattr(loaded, "module") else loaded

        module = torch_tensorrt.compile(
            model, ir="dynamo",
            inputs=[torch_tensorrt.Input(shape=tuple(s.shape), dtype=s.dtype) for s in samples],
            enabled_precisions={torch.float16},
            device=torch.device("cuda:0"),
            offload_module_to_cpu=True,
        )
        torch_tensorrt.save(module, str(path), output_format="exported_program", inputs=samples)
        return module
    except Exception as exc:  # noqa: BLE001
        print(f"[trt] {key} 編譯失敗，退回 eager：{type(exc).__name__}: {str(exc)[:200]}")
        return None
