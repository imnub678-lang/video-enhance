"""分塊超分推論。"""
from __future__ import annotations

import cv2
import numpy as np
import torch


def _to_tensor(img_bgr: np.ndarray, device: str, dtype: torch.dtype = torch.float32) -> torch.Tensor:
    rgb = np.ascontiguousarray(img_bgr[:, :, ::-1].transpose(2, 0, 1))
    t = torch.from_numpy(rgb).to(device=device, dtype=dtype).div_(255.0).unsqueeze(0)
    return t


def _to_numpy(t: torch.Tensor) -> np.ndarray:
    arr = t.squeeze(0).clamp_(0, 1).mul_(255).round_().to(torch.uint8).cpu().numpy()
    return np.ascontiguousarray(arr.transpose(1, 2, 0)[:, :, ::-1])


def _dtype_of(model: torch.nn.Module) -> torch.dtype:
    try:
        return next(model.parameters()).dtype
    except StopIteration:
        return torch.float32


def tiled_infer(model: torch.nn.Module, img_bgr: np.ndarray,
                tile: int, pad: int, device: str = "cuda") -> np.ndarray:
    h, w = img_bgr.shape[:2]
    dtype = _dtype_of(model)
    if tile <= 0 or (tile >= h and tile >= w):
        with torch.no_grad():
            return _to_numpy(model(_to_tensor(img_bgr, device, dtype)))

    scale = getattr(model, "upscale", 0)
    if not scale:
        with torch.no_grad():
            scale = model(_to_tensor(img_bgr[:8, :8], device, dtype)).shape[-1] // 8

    out = np.zeros((h * scale, w * scale, 3), dtype=np.uint8)
    for y0 in range(0, h, tile):
        for x0 in range(0, w, tile):
            y1, x1 = min(y0 + tile, h), min(x0 + tile, w)
            py0, px0 = max(0, y0 - pad), max(0, x0 - pad)
            py1, px1 = min(h, y1 + pad), min(w, x1 + pad)
            patch = img_bgr[py0:py1, px0:px1]
            with torch.no_grad():
                res = _to_numpy(model(_to_tensor(patch, device, dtype)))
            top, left = (y0 - py0) * scale, (x0 - px0) * scale
            out[y0 * scale:y1 * scale, x0 * scale:x1 * scale] = \
                res[top:top + (y1 - y0) * scale, left:left + (x1 - x0) * scale]
    return out


class SuperResolver:
    def __init__(self, weights: str, upscale: int, tile: int,
                 tile_pad: int = 16, device: str = "cuda",
                 dtype: torch.dtype | None = None):
        from engine.arch_srvgg import load_srvgg

        if dtype is None:
            dtype = torch.float16 if device == "cuda" else torch.float32
        self.model = load_srvgg(weights, upscale=upscale, device=device, dtype=dtype)
        self.upscale = upscale
        self.tile = tile
        self.pad = tile_pad
        self.device = device
        self.dtype = dtype

    def __call__(self, frame_bgr: np.ndarray) -> np.ndarray:
        try:
            return tiled_infer(self.model, frame_bgr, self.tile, self.pad, self.device)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            self.tile = max(128, self.tile // 2)
            return tiled_infer(self.model, frame_bgr, self.tile, self.pad, self.device)

    def upscale_to(self, frame_bgr: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
        """超分後直接在 GPU 降採到目標尺寸，避免搬 4 倍大的陣列回主記憶體。"""
        big = self(frame_bgr)
        if big.shape[:2] == (out_h, out_w):
            return big
        t = torch.from_numpy(np.ascontiguousarray(big[:, :, ::-1].transpose(2, 0, 1)))
        t = t.to(device=self.device, dtype=torch.float32).unsqueeze(0)
        small = torch.nn.functional.interpolate(t, size=(out_h, out_w), mode="area")
        arr = small.squeeze(0).clamp_(0, 255).round_().to(torch.uint8).cpu().numpy()
        return np.ascontiguousarray(arr.transpose(1, 2, 0)[:, :, ::-1])

    @staticmethod
    def resize_to(frame_bgr: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
        if frame_bgr.shape[:2] == (out_h, out_w):
            return frame_bgr
        return cv2.resize(frame_bgr, (out_w, out_h), interpolation=cv2.INTER_AREA)
