import numpy as np
import pytest

from engine.fi import Interpolator


class _Stub(Interpolator):
    def __init__(self):
        pass


def test_t_zero_returns_a():
    it = _Stub()
    a = np.full((8, 8, 3), 10, np.uint8)
    b = np.full((8, 8, 3), 200, np.uint8)
    assert np.array_equal(it.blend(a, b, 0.0), a)


def test_t_one_returns_b():
    it = _Stub()
    a = np.full((8, 8, 3), 10, np.uint8)
    b = np.full((8, 8, 3), 200, np.uint8)
    assert np.array_equal(it.blend(a, b, 1.0), b)


@pytest.mark.slow
def test_midpoint_shape_and_range():
    it = Interpolator("models/flownet.pkl")
    a = np.zeros((64, 64, 3), np.uint8)
    b = np.full((64, 64, 3), 255, np.uint8)
    out = it.blend(a, b, 0.5)
    assert out.shape == (64, 64, 3) and out.dtype == np.uint8


@pytest.mark.slow
def test_identical_frames_reproduce_input():
    it = Interpolator("models/flownet.pkl")
    rng = np.random.default_rng(0)
    a = rng.integers(0, 255, (96, 160, 3), dtype=np.uint8)
    out = it.blend(a, a, 0.5)
    assert np.abs(out.astype(int) - a.astype(int)).mean() < 3.0
