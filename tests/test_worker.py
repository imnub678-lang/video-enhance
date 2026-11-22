import pytest

from app.worker import main
from engine.encoders import load
from engine.pipeline import run
from engine.policy import Options
from engine.probe import probe


def test_missing_input_returns_2(tmp_path):
    assert main(["--input", str(tmp_path / "nope.mp4"), "--profile", "standard"]) == 2


def test_unknown_profile_returns_2(make_clip):
    src = make_clip()
    assert main(["--input", src, "--profile", "nope"]) == 2


def test_rejects_4k_input(make_clip, tmp_path):
    src = make_clip(width=3840, height=2160, seconds=0.5)
    rc = main(["--input", src, "--output", str(tmp_path / "o.mp4")])
    assert rc == 3


def test_rejects_when_both_disabled(make_clip, tmp_path):
    src = make_clip()
    rc = main(["--input", src, "--output", str(tmp_path / "o.mp4"),
               "--no-sr", "--no-fi"])
    assert rc == 3


@pytest.mark.integration
def test_end_to_end_fi_only(make_clip, tmp_path):
    src = make_clip(fps=24, seconds=1, width=320, height=240)
    out = str(tmp_path / "out.mp4")
    run(src, out, Options(do_sr=False), load("standard"),
        on_progress=lambda **k: None)
    info = probe(out)
    assert (info.width, info.height) == (320, 240)
    assert info.fps == pytest.approx(60, abs=0.5)
    assert info.duration == pytest.approx(1.0, abs=0.15)


@pytest.mark.integration
def test_end_to_end_sr_only(make_clip, tmp_path):
    src = make_clip(fps=60, seconds=1, width=320, height=240)
    out = str(tmp_path / "out4k.mp4")
    run(src, out, Options(do_fi=False), load("fast"),
        on_progress=lambda **k: None)
    info = probe(out)
    assert (info.width, info.height) == (3840, 2160)
    assert info.fps == pytest.approx(60, abs=0.5)
    assert info.duration == pytest.approx(1.0, abs=0.2)


@pytest.mark.integration
def test_end_to_end_120fps(make_clip, tmp_path):
    src = make_clip(fps=60, seconds=1, width=320, height=240)
    out = str(tmp_path / "out120.mp4")
    run(src, out, Options(do_sr=False, target_fps=120), load("standard"),
        on_progress=lambda **k: None)
    info = probe(out)
    assert (info.width, info.height) == (320, 240)
    assert info.fps == pytest.approx(120, abs=1.0)
    assert info.duration == pytest.approx(1.0, abs=0.15)
