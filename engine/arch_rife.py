"""RIFE v4.26 的 IFNet_HDv3（官方實作，warp 改為本地實作）。

來源：hzwer/RIFE 的 RIFEv4.26_0921 套件（IFNet_HDv3.py + flownet.pkl）。
權重 key 帶 `module.` 前綴，並含推論時不用的 `teacher.`／`caltime.`，載入時剝除。
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

_GRIDS: dict[tuple[str, tuple[int, ...]], torch.Tensor] = {}


def warp(img: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
    key = (str(flow.device), tuple(flow.shape))
    if key not in _GRIDS:
        b, _, h, w = flow.shape
        horiz = torch.linspace(-1.0, 1.0, w, device=flow.device).view(1, 1, 1, w).expand(b, -1, h, -1)
        vert = torch.linspace(-1.0, 1.0, h, device=flow.device).view(1, 1, h, 1).expand(b, -1, -1, w)
        _GRIDS[key] = torch.cat([horiz, vert], 1)
    norm = torch.cat([
        flow[:, 0:1] / ((img.shape[3] - 1.0) / 2.0),
        flow[:, 1:2] / ((img.shape[2] - 1.0) / 2.0),
    ], 1)
    grid = (_GRIDS[key] + norm).permute(0, 2, 3, 1).to(img.dtype)
    return F.grid_sample(img, grid, mode="bilinear", padding_mode="border", align_corners=True)


def _conv(inp: int, outp: int, stride: int = 1) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(inp, outp, 3, stride, 1, bias=True),
        nn.LeakyReLU(0.2, True),
    )


class Head(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn0 = nn.Conv2d(3, 16, 3, 2, 1)
        self.cnn1 = nn.Conv2d(16, 16, 3, 1, 1)
        self.cnn2 = nn.Conv2d(16, 16, 3, 1, 1)
        self.cnn3 = nn.ConvTranspose2d(16, 4, 4, 2, 1)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        x = self.relu(self.cnn0(x))
        x = self.relu(self.cnn1(x))
        x = self.relu(self.cnn2(x))
        return self.cnn3(x)


class ResConv(nn.Module):
    def __init__(self, c: int):
        super().__init__()
        self.conv = nn.Conv2d(c, c, 3, 1, 1)
        self.beta = nn.Parameter(torch.ones((1, c, 1, 1)))
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        return self.relu(self.conv(x) * self.beta + x)


class IFBlock(nn.Module):
    def __init__(self, in_planes: int, c: int = 64):
        super().__init__()
        self.conv0 = nn.Sequential(_conv(in_planes, c // 2, 2), _conv(c // 2, c, 2))
        self.convblock = nn.Sequential(*(ResConv(c) for _ in range(8)))
        self.lastconv = nn.Sequential(nn.ConvTranspose2d(c, 4 * 13, 4, 2, 1), nn.PixelShuffle(2))

    def forward(self, x, flow=None, scale=1):
        x = F.interpolate(x, scale_factor=1.0 / scale, mode="bilinear", align_corners=False)
        if flow is not None:
            flow = F.interpolate(flow, scale_factor=1.0 / scale, mode="bilinear",
                                 align_corners=False) * 1.0 / scale
            x = torch.cat((x, flow), 1)
        feat = self.convblock(self.conv0(x))
        tmp = self.lastconv(feat)
        tmp = F.interpolate(tmp, scale_factor=scale, mode="bilinear", align_corners=False)
        return tmp[:, :4] * scale, tmp[:, 4:5], tmp[:, 5:]


class IFNet(nn.Module):
    PAD_ALIGN = 32
    SCALE_LIST = [8, 4, 2, 1, 1]

    def __init__(self):
        super().__init__()
        self.block0 = IFBlock(7 + 8, c=192)
        self.block1 = IFBlock(8 + 4 + 8 + 8, c=128)
        self.block2 = IFBlock(8 + 4 + 8 + 8, c=96)
        self.block3 = IFBlock(8 + 4 + 8 + 8, c=64)
        self.block4 = IFBlock(8 + 4 + 8 + 8, c=32)
        self.encode = Head()

    def forward(self, img0: torch.Tensor, img1: torch.Tensor, timestep: float | torch.Tensor = 0.5):
        if not torch.is_tensor(timestep):
            timestep = (img0[:, :1] * 0 + 1) * timestep
        else:
            timestep = timestep.repeat(1, 1, img0.shape[2], img0.shape[3])

        f0 = self.encode(img0)
        f1 = self.encode(img1)
        blocks = [self.block0, self.block1, self.block2, self.block3, self.block4]
        flow = mask = feat = None
        warped0, warped1 = img0, img1
        for i, block in enumerate(blocks):
            if flow is None:
                flow, mask, feat = block(
                    torch.cat((img0, img1, f0, f1, timestep), 1), None, scale=self.SCALE_LIST[i])
            else:
                fd, mask, feat = block(
                    torch.cat((warped0, warped1, warp(f0, flow[:, :2]), warp(f1, flow[:, 2:4]),
                               timestep, mask, feat), 1), flow, scale=self.SCALE_LIST[i])
                flow = flow + fd
            warped0 = warp(img0, flow[:, :2])
            warped1 = warp(img1, flow[:, 2:4])
        m = torch.sigmoid(mask)
        return warped0 * m + warped1 * (1 - m)


def load_rife(weights_path: str, device: str = "cuda",
              dtype: torch.dtype = torch.float16) -> IFNet:
    sd = torch.load(weights_path, map_location="cpu", weights_only=True)
    sd = {k.replace("module.", "", 1): v for k, v in sd.items()}
    sd = {k: v for k, v in sd.items() if not k.startswith(("teacher.", "caltime."))}
    model = IFNet()
    model.load_state_dict(sd, strict=True)
    return model.eval().to(device=device, dtype=dtype)
