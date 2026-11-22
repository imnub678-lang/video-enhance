import numpy as np
import pytest
import torch

from engine.sr import SuperResolver, tensor_to_frame, tiled_infer


class Identity(torch.nn.Module):
    def forward(self, x):
        return x


def test_tiled_matches_whole():
    img = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
    whole = tiled_infer(Identity(), img, tile=0, pad=16, device="cpu")
    tiled = tiled_infer(Identity(), img, tile=64, pad=16, device="cpu")
    assert np.array_equal(whole, tiled)


def test_tiled_odd_sizes():
    img = np.random.randint(0, 255, (97, 131, 3), dtype=np.uint8)
    out = tiled_infer(Identity(), img, tile=32, pad=8, device="cpu")
    assert out.shape == img.shape


def test_resize_to_target():
    img = np.zeros((4320, 7680, 3), np.uint8)
    out = SuperResolver.resize_to(img, 2160, 3840)
    assert out.shape == (2160, 3840, 3)


@pytest.mark.slow
def test_real_model_upscales_1080p_tile():
    sr = SuperResolver("models/realesr-general-x4v3.pth", 4, tile=512)
    out = sr(np.zeros((1080, 1920, 3), dtype=np.uint8))
    assert out.shape == (4320, 7680, 3)
    assert torch.cuda.max_memory_allocated() < 11 * 2**30


def test_tensor_to_frame_does_not_mutate_input():
    """t=0 的輸出幀就是來源張量本身，就地轉換會污染後續插幀的輸入。"""
    t = torch.rand(1, 3, 8, 8)
    before = t.clone()
    tensor_to_frame(t)
    assert torch.equal(before, t)
