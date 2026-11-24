import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

INFO = {
    "device": "cuda", "vendor": "nvidia", "torch": "2.14.1", "cuda": "13.0",
    "hip": None, "gpu": "RTX 5070 Ti", "vram_gb": 12.0, "cpu_cores": 16,
    "ram_gb": 32.0, "disk_free_gb": 100.0, "trt": True,
    "ffmpeg": r"D:\ffmpeg\bin\ffmpeg.exe", "encoders": ["hevc_nvenc", "libx265"],
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _wizard(app, monkeypatch, info=None):
    from app.ui import wizard

    monkeypatch.setattr(wizard.backend, "describe", lambda: info or INFO)
    return wizard.SetupWizard()


def test_real_device_scan_runs(monkeypatch):
    """首啟掃描不能崩；曾經漏 import ctypes 導致 NameError。"""
    from engine import backend

    monkeypatch.setattr(backend, "ffmpeg_encoders", lambda: frozenset())
    info = backend.describe()
    assert info["vendor"] in {"nvidia", "amd", "cpu"}
    assert isinstance(info["cpu_cores"], int) or info["cpu_cores"] is None


def test_scan_enables_next_with_gpu(app, monkeypatch):
    from app.ui.wizard import ORDER, WEIGHTS
    from engine.models import MODELS

    assert set(WEIGHTS) == set(ORDER)
    assert all(weight in MODELS for weight in WEIGHTS.values())

    w = _wizard(app, monkeypatch)
    assert w._next.isEnabled()
    assert w._close.isVisible() or not w._close.isHidden()


def test_scan_blocks_without_gpu(app, monkeypatch):
    info = dict(INFO, vendor="cpu", gpu=None, vram_gb=None, device="cpu")
    w = _wizard(app, monkeypatch, info)
    assert not w._next.isEnabled()
    assert w._unsupported.text()


def test_all_models_checked_by_default(app, monkeypatch):
    from app.ui.wizard import ORDER

    w = _wizard(app, monkeypatch)
    assert w._selected() == list(ORDER)
    w._checks["x4plus"].setChecked(False)
    assert "x4plus" not in w._selected()


def test_finish_unlocks_after_download(app, monkeypatch):
    w = _wizard(app, monkeypatch)
    marked = []
    from app.ui import wizard

    monkeypatch.setattr(wizard.config, "mark_setup_done", lambda: marked.append(True))
    w._stack.setCurrentIndex(2)
    w._on_all_done()
    assert w._next.isEnabled()
    assert marked == [True]
