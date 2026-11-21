"""RIFE 插幀封裝（張量介面為主，numpy 為相容層）。"""
from __future__ import annotations

import pathlib

import numpy as np
import torch
import torch.nn.functional as F


def to_tensor(img_bgr: np.ndarray, device: str, dtype: torch.dtype) -> torch.Tensor:
    rgb = np.ascontiguousarray(img_bgr[:, :, ::-1].transpose(2, 0, 1))
    return torch.from_numpy(rgb).to(device=device, dtype=dtype).div_(255.0).unsqueeze(0)


def to_numpy(t: torch.Tensor) -> np.ndarray:
    arr = t.squeeze(0).clamp_(0, 1).mul_(255).round_().to(torch.uint8).cpu().numpy()
    return np.ascontiguousarray(arr.transpose(1, 2, 0)[:, :, ::-1])


class Interpolator:
    def __init__(self, weights: str, device: str = "cuda", dtype: torch.dtype = torch.float16,
                 use_trt: bool = True):
        from engine.arch_rife import load_rife

        self.model = load_rife(weights, device=device, dtype=dtype)
        self.device = device
        self.dtype = dtype
        self.align = 32
        self.use_trt = use_trt
        self._engines: dict[tuple[int, int], torch.nn.Module | None] = {}
        self._weights_name = pathlib.Path(weights).stem

    def _engine(self, ph: int, pw: int):
        key = (ph, pw)
        if key in self._engines:
            return self._engines[key]

        from engine import trt

        engine = None
        if self.use_trt:
            a = torch.zeros(1, 3, ph, pw, device=self.device, dtype=self.dtype)
            ts = torch.zeros(1, 1, 1, 1, device=self.device, dtype=self.dtype)
            engine = trt.compile_fixed(self.model, [a, a, ts],
                                       f"{self._weights_name}_{ph}x{pw}_fp16")
        self._engines[key] = engine
        return engine

    def blend_tensors(self, ta: torch.Tensor, tb: torch.Tensor, t: float) -> torch.Tensor:
        if t <= 0.0:
            return ta
        if t >= 1.0:
            return tb

        h, w = ta.shape[-2:]
        ph = (-h) % self.align
        pw = (-w) % self.align
        if ph or pw:
            ta = F.pad(ta, (0, pw, 0, ph), mode="replicate")
            tb = F.pad(tb, (0, pw, 0, ph), mode="replicate")

        engine = self._engine(h + ph, w + pw)
        with torch.no_grad():
            if engine is not None:
                ts = torch.full((1, 1, 1, 1), float(t), device=self.device, dtype=self.dtype)
                out = engine(ta, tb, ts)
            else:
                out = self.model(ta, tb, float(t))
        return out[..., :h, :w]

    def blend(self, a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
        if t <= 0.0:
            return a
        if t >= 1.0:
            return b
        ta = to_tensor(a, self.device, self.dtype)
        tb = to_tensor(b, self.device, self.dtype)
        return to_numpy(self.blend_tensors(ta, tb, t))
