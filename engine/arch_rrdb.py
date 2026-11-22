"""Real-ESRGAN 的 RRDBNet 架構（自寫，不依賴 basicsr）。

與 SRVGGNetCompact 的差異：16.7M 參數（vs 1.21M），重建高頻細節的能力強得多，
代價是同解析度下算量約 10 倍。scale=2 的權重（RealESRGAN_x2plus）內部先做
pixel_unshuffle 降到 1/4 面積再算，因此比 scale=4 便宜約 4 倍。
"""
from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class ResidualDenseBlock(nn.Module):
    def __init__(self, num_feat: int = 64, num_grow_ch: int = 32):
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    def __init__(self, num_feat: int = 64, num_grow_ch: int = 32):
        super().__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x


class RRDBNet(nn.Module):
    def __init__(self, num_in_ch: int = 3, num_out_ch: int = 3, scale: int = 4,
                 num_feat: int = 64, num_block: int = 23, num_grow_ch: int = 32):
        super().__init__()
        self.scale = scale
        self.upscale = scale  # 供 tiled_tensor 讀取
        if scale == 2:
            num_in_ch *= 4  # pixel_unshuffle(x, 2) 把 3 通道展開成 12
        self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
        self.body = nn.Sequential(
            *[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = F.pixel_unshuffle(x, 2) if self.scale == 2 else x
        feat = self.conv_first(feat)
        feat = feat + self.conv_body(self.body(feat))
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
        return self.conv_last(self.lrelu(self.conv_hr(feat)))


def load_rrdb(weights_path: str, upscale: int | None = None,
              device: str = "cuda",
              dtype: torch.dtype = torch.float32) -> RRDBNet:
    """從權重自動推導架構參數；upscale 預設由 conv_first 的輸入通道判斷。"""
    state = torch.load(weights_path, map_location="cpu", weights_only=True)
    params = state.get("params_ema") or state.get("params") or state

    in_ch = params["conv_first.weight"].shape[1]
    inferred = 2 if in_ch == 12 else 4
    if upscale is not None and upscale != inferred:
        raise ValueError(f"權重是 {inferred}x 模型，但要求 {upscale}x")

    model = RRDBNet(
        num_in_ch=3,
        num_out_ch=3,
        scale=inferred,
        num_feat=params["conv_first.weight"].shape[0],
        num_block=1 + max(int(k.split(".")[1]) for k in params if k.startswith("body.")),
        num_grow_ch=params["body.0.rdb1.conv1.weight"].shape[0],
    )
    model.load_state_dict(params, strict=True)
    return model.eval().to(device=device, dtype=dtype)
