import os
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import threading

import numpy as np
import pytest

from app import worker
from engine import backend, pipeline
from engine.encoders import load
from engine.ffmpeg_pipe import Decoder
from engine.policy import Options
from engine.probe import probe
from engine.timestamps import FramePlan
from tests.conftest import _run


def test_worker_uses_a_separate_default_output(tmp_path):
    args = worker.build_parser().parse_args(["--input", str(tmp_path / "clip.mp4")])
    assert Path(worker._resolve_output(args)) == tmp_path / "clip_enhanced.mp4"


@pytest.mark.parametrize("alias", [False, True])
def test_pipeline_rejects_an_output_referring_to_source(tmp_path, alias):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"original")
    output = tmp_path / "alias.mp4" if alias else source
    if alias:
        os.link(source, output)
    with pytest.raises(FileExistsError):
        pipeline.run(str(source), str(output), Options(), load("standard"))
    assert source.read_bytes() == b"original"


def test_two_jobs_cannot_process_the_same_destination(tmp_path, monkeypatch):
    path = tmp_path / "out.mp4"
    started = threading.Event()
    release = threading.Event()

    def wait_in_probe(_):
        started.set()
        release.wait(5)
        raise ValueError("fixture stops before encoding")

    def first_job():
        with pytest.raises(ValueError, match="fixture"):
            pipeline.run("in.mp4", str(path), Options(), load("standard"))

    monkeypatch.setattr(pipeline, "probe", wait_in_probe)
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(tmp_path)
        job = threading.Thread(target=first_job, daemon=True)
        job.start()
        try:
            assert started.wait(5)
            with pytest.raises(FileExistsError):
                pipeline.run("in.mp4", "out.mp4", Options(), load("standard"))
        finally:
            release.set()
            job.join(5)
    assert not job.is_alive()


def test_ffprobe_uses_the_frozen_app_bundle(monkeypatch, tmp_path):
    tools = tmp_path / "_internal" / "tools"
    tools.mkdir(parents=True)
    bundled = tools / "ffprobe.exe"
    bundled.touch()
    monkeypatch.delenv("VIDEOTOOL_FFPROBE", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "VideoEnhance.exe"))
    assert backend.resolve_ffprobe() == str(bundled)


def test_hardware_encoder_missing_from_ffmpeg_falls_back(monkeypatch):
    monkeypatch.setattr(backend, "vendor", lambda: "nvidia")
    monkeypatch.setattr(backend, "ffmpeg_encoders", lambda: frozenset({"libx265"}))
    assert backend.effective_codec("hevc_nvenc", 3840, 2160) == "libx265"


@pytest.mark.integration
def test_small_portrait_clip_encodes_even_when_hardware_cannot(make_clip, tmp_path):
    src = make_clip(width=72, height=128, seconds=0.25, has_audio=False)
    out = tmp_path / "out.mp4"
    assert worker.main(["--input", src, "--output", str(out), "--no-sr"]) == 0
    info = probe(str(out))
    assert (info.width, info.height) == (72, 128)


def test_preview_can_read_metadata_without_counting_frames(make_clip):
    src = make_clip(name="clip.mkv", has_audio=False)
    preview = probe(src, include_frames=False)
    assert (preview.width, preview.height, preview.frame_count) == (320, 240, 0)
    assert probe(src).frame_count == 24


def test_irregular_frames_use_real_time_for_interpolation(tmp_path):
    src = tmp_path / "vfr.mp4"
    _run([backend.resolve_ffmpeg(), "-v", "error", "-f", "lavfi", "-i",
          "testsrc2=size=64x64:rate=25:duration=0.24", "-vf", r"setpts=PTS+10*gte(N\,3)",
          "-fps_mode", "vfr", "-c:v", "libx264", str(src)])
    info = probe(str(src))
    plans, fps = pipeline._frame_plans(info, pipeline.decide(info, Options(do_sr=False)))
    assert fps == 60
    assert (plans[9].src_a, plans[9].src_b) == (2, 3)
    assert plans[9].t == pytest.approx(0.07 / 0.44)
    assert pipeline.decide(replace(info, fps_num=120, fps_den=1), Options(do_sr=False)).do_fi

    full = Decoder(str(src), 64, 64)
    try:
        expected = [full.read() for _ in range(4)][-1]
        while full.read() is not None:
            pass
    finally:
        full.close()
    seek = Decoder(str(src), 64, 64, start_time=info.seek_origin + info.frame_times[3] - 1e-6)
    try:
        np.testing.assert_array_equal(seek.read(), expected)
        while seek.read() is not None:
            pass
    finally:
        seek.close()


@pytest.mark.parametrize(("dimensions", "expected"), [
    ((1080, 1920), (2160, 3840)),
    ((640, 480), (2880, 2160)),
    ((1920, 1080), (3840, 2160)),
])
def test_upscaling_preserves_display_aspect_ratio(dimensions, expected):
    assert pipeline._output_size(*dimensions, upscale=True) == expected


def test_silent_clip_keeps_mov_text_subtitles(make_clip, tmp_path):
    src = make_clip(has_audio=False)
    subtitles = tmp_path / "captions.srt"
    subtitles.write_text("1\n00:00:00,000 --> 00:00:00,500\nHello\n", encoding="utf-8")
    captioned = tmp_path / "captioned.mp4"
    _run([backend.resolve_ffmpeg(), "-v", "error", "-i", src, "-i", str(subtitles),
          "-map", "0:v:0", "-map", "1:s:0", "-c:v", "copy", "-c:s", "mov_text", str(captioned)])
    parts = tmp_path / "parts with 'quotes'"
    parts.mkdir()
    (parts / "seg0000.mp4").write_bytes(Path(src).read_bytes())
    output = tmp_path / "output.mp4"
    pipeline._concat(parts, 1, str(captioned), str(output), probe(str(captioned)))
    assert probe(str(output)).subtitle_codecs == ("mov_text",)


def test_pipeline_fails_instead_of_waiting_after_early_eof(make_clip):
    src = make_clip(fps=24, seconds=1 / 24, width=64, height=64, has_audio=False)
    dec = Decoder(src, 64, 64)
    failures = []

    class Sink:
        def write(self, frame):
            pass

    def process():
        try:
            pipeline._process([FramePlan(0, 0, 0, 0.0), FramePlan(1, 1, 1, 0.0)],
                              dec, Sink(), None, None, 64, 64)
        except RuntimeError as exc:
            failures.append(exc)

    job = threading.Thread(target=process, daemon=True)
    job.start()
    job.join(5)
    dec.close()
    assert not job.is_alive()
    assert failures
