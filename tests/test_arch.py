import pytest
import torch

from engine.arch_srvgg import SRVGGNetCompact, load_srvgg


def test_srvgg_output_shape_x4():
    m = SRVGGNetCompact(upscale=4).eval()
    with torch.no_grad():
        out = m(torch.zeros(1, 3, 64, 64))
    assert out.shape == (1, 3, 256, 256)


def test_srvgg_roundtrip_deterministic():
    m = SRVGGNetCompact(upscale=4).eval()
    x = torch.rand(1, 3, 32, 32)
    with torch.no_grad():
        assert torch.allclose(m(x), m(x))


def test_official_weights_load_strict():
    m = load_srvgg("models/realesr-general-x4v3.pth", 4, device="cpu")
    assert isinstance(m, SRVGGNetCompact)


@pytest.mark.slow
def test_rife_loads_and_blends():
    from engine.arch_rife import load_rife

    m = load_rife("models/flownet.pkl")
    a = torch.rand(1, 3, 64, 96, device="cuda", dtype=torch.float16)
    with torch.no_grad():
        out = m(a, a, 0.5)
    assert out.shape == a.shape
