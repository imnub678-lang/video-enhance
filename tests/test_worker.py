import pytest

from app.worker import main
from engine.pipeline import run
from engine.probe import probe


def test_missing_input_returns_2(tmp_path):
    assert main(["--input", str(tmp_path / "nope.mp4"), "--preset", "balanced"]) == 2


def test_unknown_preset_returns_2(make_clip):
    src = make_clip()
    assert main(["--input", src, "--preset", "nope"]) == 2


def test_rejects_4k_input(make_clip, tmp_path):
    src = make_clip(width=3840, height=2160, seconds=0.5)
    rc = main(["--input", src, "--output", str(tmp_path / "o.mp4"), "--preset", "balanced"])
    assert rc == 3


@pytest.mark.integration
def test_end_to_end_fi_only_60fps(make_clip, tmp_path):
    src = make_clip(fps=24, seconds=1, width=320, height=240)
    out = str(tmp_path / "out.mp4")
    run(src, out, preset="fi_only", on_progress=lambda **k: None)
    info = probe(out)
    assert (info.width, info.height) == (320, 240)
    assert info.fps == pytest.approx(60, abs=0.5)
    assert info.duration == pytest.approx(1.0, abs=0.15)


@pytest.mark.integration
def test_end_to_end_sr_and_fi(make_clip, tmp_path):
    src = make_clip(fps=24, seconds=1, width=320, height=240)
    out = str(tmp_path / "out4k.mp4")
    run(src, out, preset="fast")
    info = probe(out)
    assert (info.width, info.height) == (3840, 2160)
    assert info.duration == pytest.approx(1.0, abs=0.2)
