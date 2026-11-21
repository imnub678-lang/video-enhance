"""分塊超分推論（張量為主的管線，numpy 介面為相容層）。"""
from __future__ import annotations

import pathlib

import cv2
import numpy as np
import torch
import torch.nn.functional as F


def _to_tensor(img_bgr: np.ndarray, device: str, dtype: torch.dtype = torch.float32) -> torch.Tensor:
    rgb = np.ascontiguousarray(img_bgr[:, :, ::-1].transpose(2, 0, 1))
    return torch.from_numpy(rgb).to(device=device, dtype=dtype).div_(255.0).unsqueeze(0)


def _to_numpy(t: torch.Tensor) -> np.ndarray:
    arr = t.squeeze(0).clamp_(0, 1).mul_(255).round_().to(torch.uint8).cpu().numpy()
    return np.ascontiguousarray(arr.transpose(1, 2, 0)[:, :, ::-1])


def _dtype_of(model: torch.nn.Module) -> torch.dtype:
    try:
        return next(model.parameters()).dtype
    except StopIteration:
        return torch.float32


def _scale_of(runner: torch.nn.Module, sample: torch.Tensor) -> int:
    scale = getattr(runner, "upscale", 0)
    if scale:
        return int(scale)
    with torch.no_grad():
        return runner(sample[..., :8, :8]).shape[-1] // 8


def tiled_tensor(runner: torch.nn.Module, t: torch.Tensor,
                 tile: int, pad: int, scale: int = 0) -> torch.Tensor:
    """t: (1,3,H,W)；回傳放大後張量。所有 patch 同尺寸，適合固定形狀的 TRT 引擎。"""
    _, _, h, w = t.shape
    if tile <= 0:
        with torch.no_grad():
            return runner(t)

    scale = scale or _scale_of(runner, t)
    rows = (h + tile - 1) // tile
    cols = (w + tile - 1) // tile
    canvas = F.pad(t, (pad, cols * tile + pad - w, pad, rows * tile + pad - h), mode="replicate")

    out = torch.empty((1, 3, rows * tile * scale, cols * tile * scale),
                      dtype=t.dtype, device=t.device)
    patch = tile + 2 * pad
    for r in range(rows):
        for c in range(cols):
            y, x = r * tile, c * tile
            with torch.no_grad():
                res = runner(canvas[..., y:y + patch, x:x + patch])
            out[..., y * scale:(y + tile) * scale, x * scale:(x + tile) * scale] = \
                res[..., pad * scale:(pad + tile) * scale, pad * scale:(pad + tile) * scale]
    return out[..., :h * scale, :w * scale]


def tiled_infer(model: torch.nn.Module, img_bgr: np.ndarray,
                tile: int, pad: int, device: str = "cuda") -> np.ndarray:
    t = _to_tensor(img_bgr, device, _dtype_of(model))
    return _to_numpy(tiled_tensor(model, t, tile, pad))


class SuperResolver:
    def __init__(self, weights: str, upscale: int, tile: int,
                 tile_pad: int = 16, device: str = "cuda",
                 dtype: torch.dtype | None = None, use_trt: bool = True):
        from engine.arch_srvgg import load_srvgg
        from engine import trt

        if dtype is None:
            dtype = torch.float16 if device == "cuda" else torch.float32
        self.model = load_srvgg(weights, upscale=upscale, device=device, dtype=dtype)
        self.upscale = upscale
        self.tile = tile
        self.pad = tile_pad
        self.device = device
        self.dtype = dtype

        self.trt = None
        if use_trt and tile > 0 and device == "cuda":
            patch = tile + 2 * tile_pad
            sample = torch.zeros(1, 3, patch, patch, device=device, dtype=dtype)
            key = f"srvgg_{pathlib.Path(weights).stem}_{patch}_fp16"
            self.trt = trt.compile_fixed(self.model, [sample], key)

    @property
    def runner(self) -> torch.nn.Module:
        return self.trt if self.trt is not None else self.model

    def upscale_tensor(self, t: torch.Tensor, out_h: int, out_w: int) -> torch.Tensor:
        big = tiled_tensor(self.runner, t, self.tile, self.pad, self.upscale)
        if big.shape[-2:] == (out_h, out_w):
            return big
        return F.interpolate(big, size=(out_h, out_w), mode="area")

    def __call__(self, frame_bgr: np.ndarray) -> np.ndarray:
        t = _to_tensor(frame_bgr, self.device, self.dtype)
        try:
            big = tiled_tensor(self.runner, t, self.tile, self.pad, self.upscale)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            self.trt = None
            self.tile = max(128, self.tile // 2)
            big = tiled_tensor(self.model, t, self.tile, self.pad, self.upscale)
        return _to_numpy(big)

    def upscale_to(self, frame_bgr: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
        t = _to_tensor(frame_bgr, self.device, self.dtype)
        return _to_numpy(self.upscale_tensor(t, out_h, out_w))

    @staticmethod
    def resize_to(frame_bgr: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
        if frame_bgr.shape[:2] == (out_h, out_w):
            return frame_bgr
        return cv2.resize(frame_bgr, (out_w, out_h), interpolation=cv2.INTER_AREA)


frame_to_tensor = _to_tensor
tensor_to_frame = _to_numpy
