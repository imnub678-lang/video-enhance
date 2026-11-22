import pathlib
from types import SimpleNamespace

import pytest

import engine.pipeline as pipeline
from engine.encoders import load
from engine.policy import Options


def test_manifest_roundtrip(tmp_path):
    key = {"input": "x", "crf": 19}
    pipeline._save_done(tmp_path, key, {0, 2})
    assert pipeline._load_done(tmp_path, key) == {0, 2}


def test_manifest_invalidated_when_key_changes(tmp_path):
    pipeline._save_done(tmp_path, {"crf": 19}, {0, 1})
    assert pipeline._load_done(tmp_path, {"crf": 21}) == set()
    assert not (tmp_path / "manifest.json").exists()


def test_manifest_survives_corruption(tmp_path):
    (tmp_path / "manifest.json").write_text("{ not json", encoding="utf-8")
    assert pipeline._load_done(tmp_path, {"crf": 19}) == set()


def test_concat_list_uses_absolute_paths(tmp_path, monkeypatch):
    """concat demuxer 相對清單檔解析，寫相對路徑會找不到片段。"""
    monkeypatch.chdir(tmp_path)
    parts = pathlib.Path("p")
    parts.mkdir()
    (parts / "seg0000.mp4").write_bytes(b"x")

    captured: dict[str, str] = {}
    monkeypatch.setattr(pipeline, "concat_segments",
                        lambda lst, *a: captured.update(
                            text=pathlib.Path(lst).read_text(encoding="utf-8")))

    pipeline._concat(parts, 1, "src", "out",
                     SimpleNamespace(audio_codec=None, subtitle_codecs=()))

    expected = (parts / "seg0000.mp4").resolve().as_posix()
    assert f"file '{expected}'" in captured["text"]


@pytest.mark.integration
def test_resume_skips_finished_segments(make_clip, tmp_path, monkeypatch):
    src = make_clip(fps=24, seconds=4, width=320, height=240)
    out = str(tmp_path / "o.mp4")
    monkeypatch.setattr(pipeline, "SEGMENT_SECONDS", 1)

    real = pipeline._encode_segment
    seen: list[int] = []

    def interrupt_after_first(slice_plans, offset, *args, **kwargs):
        if seen:
            raise RuntimeError("模擬中斷")
        seen.append(offset)
        return real(slice_plans, offset, *args, **kwargs)

    monkeypatch.setattr(pipeline, "_encode_segment", interrupt_after_first)
    with pytest.raises(RuntimeError):
        pipeline.run(src, out, Options(do_sr=False), load("standard"), resume=False)

    parts = tmp_path / ".o.parts"
    assert (parts / "seg0000.mp4").exists()

    encoded: list[int] = []

    def spy(slice_plans, offset, *args, **kwargs):
        encoded.append(offset)
        return real(slice_plans, offset, *args, **kwargs)

    monkeypatch.setattr(pipeline, "_encode_segment", spy)
    pipeline.run(src, out, Options(do_sr=False), load("standard"), resume=True)

    assert 0 not in encoded, "已完成的片段不應重跑"
    assert encoded, "剩下的片段應該被編碼"
    assert not parts.exists(), "完成後暫存目錄應清除"
    assert (tmp_path / "o.mp4").stat().st_size > 0


@pytest.mark.integration
def test_no_resume_reencodes_everything(make_clip, tmp_path, monkeypatch):
    src = make_clip(fps=24, seconds=3, width=320, height=240)
    out = str(tmp_path / "o.mp4")
    monkeypatch.setattr(pipeline, "SEGMENT_SECONDS", 1)

    pipeline.run(src, out, Options(do_sr=False), load("standard"), resume=False)
    assert not (tmp_path / ".o.parts").exists()

    real = pipeline._encode_segment
    encoded: list[int] = []

    def spy(slice_plans, offset, *args, **kwargs):
        encoded.append(offset)
        return real(slice_plans, offset, *args, **kwargs)

    monkeypatch.setattr(pipeline, "_encode_segment", spy)
    pipeline.run(src, out, Options(do_sr=False), load("standard"), resume=False)
    assert encoded[0] == 0
