"""Real-ESRGAN 的 SRVGGNetCompact 架構（自寫，不依賴 basicsr）。"""
from __future__ import annotations

import torch
from torch import nn


class SRVGGNetCompact(nn.Module):
    def __init__(self, num_in_ch: int = 3, num_out_ch: int = 3,
                 num_feat: int = 64, num_conv: int = 32, upscale: int = 4):
        super().__init__()
        self.upscale = upscale
        body: list[nn.Module] = [
            nn.Conv2d(num_in_ch, num_feat, 3, 1, 1),
            nn.PReLU(num_parameters=num_feat),
        ]
        for _ in range(num_conv):
            body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
            body.append(nn.PReLU(num_parameters=num_feat))
        body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
        self.body = nn.Sequential(*body)
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.upsampler(self.body(x))
        base = nn.functional.interpolate(x, scale_factor=self.upscale, mode="nearest")
        return out + base


def _infer_layout(params: dict) -> tuple[int, int]:
    """從權重推 num_conv 與 num_feat：body 結構為 conv,prelu,(conv,prelu)*n,conv。"""
    last = max(int(k.split(".")[1]) for k in params if k.startswith("body."))
    num_conv = (last + 1 - 3) // 2
    num_feat = params["body.0.weight"].shape[0]
    return num_conv, num_feat


def load_srvgg(weights_path: str, upscale: int = 4,
               num_conv: int | None = None, num_feat: int | None = None,
               device: str = "cuda",
               dtype: torch.dtype = torch.float32) -> SRVGGNetCompact:
    state = torch.load(weights_path, map_location="cpu", weights_only=True)
    params = state.get("params_ema") or state.get("params") or state
    auto_conv, auto_feat = _infer_layout(params)
    model = SRVGGNetCompact(num_conv=num_conv or auto_conv,
                            num_feat=num_feat or auto_feat, upscale=upscale)
    model.load_state_dict(params, strict=True)
    return model.eval().to(device=device, dtype=dtype)
