"""RIFE 插幀封裝。"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F


def _to_tensor(img_bgr: np.ndarray, device: str, dtype: torch.dtype) -> torch.Tensor:
    rgb = np.ascontiguousarray(img_bgr[:, :, ::-1].transpose(2, 0, 1))
    t = torch.from_numpy(rgb).to(device=device, dtype=dtype).div_(255.0).unsqueeze(0)
    return t


def _to_numpy(t: torch.Tensor) -> np.ndarray:
    arr = t.squeeze(0).clamp_(0, 1).mul_(255).round_().to(torch.uint8).cpu().numpy()
    return np.ascontiguousarray(arr.transpose(1, 2, 0)[:, :, ::-1])


class Interpolator:
    def __init__(self, weights: str, device: str = "cuda", dtype: torch.dtype = torch.float16):
        from engine.arch_rife import load_rife

        self.model = load_rife(weights, device=device, dtype=dtype)
        self.device = device
        self.dtype = dtype
        self.align = 32

    def blend(self, a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
        if t <= 0.0:
            return a
        if t >= 1.0:
            return b

        h, w = a.shape[:2]
        ph = (self.align - h % self.align) % self.align
        pw = (self.align - w % self.align) % self.align

        ta = _to_tensor(a, self.device, self.dtype)
        tb = _to_tensor(b, self.device, self.dtype)
        if ph or pw:
            ta = F.pad(ta, (0, pw, 0, ph), mode="replicate")
            tb = F.pad(tb, (0, pw, 0, ph), mode="replicate")

        with torch.no_grad():
            out = self.model(ta, tb, float(t))
        return _to_numpy(out[:, :, :h, :w])
