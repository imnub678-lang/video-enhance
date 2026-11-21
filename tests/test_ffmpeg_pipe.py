import numpy as np

from engine.ffmpeg_pipe import Decoder, Encoder


def _drain(dec: Decoder) -> list[np.ndarray]:
    frames = []
    while (f := dec.read()) is not None:
        frames.append(f)
    dec.close()
    return frames


def test_decoder_frame_count(make_clip):
    frames = _drain(Decoder(make_clip(fps=24, seconds=1), 320, 240))
    assert len(frames) == 24
    assert frames[0].shape == (240, 320, 3)


def test_decoder_handles_odd_dimensions(make_clip):
    path = make_clip(width=319, height=241)
    frames = _drain(Decoder(path, 320, 242))
    assert len(frames) == 24
    assert frames[0].shape == (242, 320, 3)


def test_decoder_applies_rotation(make_clip):
    path = make_clip(width=320, height=240, rotation=90)
    frames = _drain(Decoder(path, 240, 320))
    assert frames[0].shape == (320, 240, 3)


def test_encoder_without_audio(make_clip, tmp_path):
    src = make_clip(has_audio=False)
    out = str(tmp_path / "out.mp4")
    dec, enc = Decoder(src, 320, 240), Encoder(out, 320, 240, 24, src, None, None)
    for f in _drain_frames(dec):
        enc.write(f)
    dec.close()
    enc.close()
    assert len(_drain(Decoder(out, 320, 240))) == 24


def _drain_frames(dec: Decoder):
    while (f := dec.read()) is not None:
        yield f


def test_encoder_unicode_path(make_clip, tmp_path):
    src = make_clip()
    out = str(tmp_path / "測試 檔（1）.mp4")
    dec, enc = Decoder(src, 320, 240), Encoder(out, 320, 240, 24, src, "aac", None)
    for f in _drain_frames(dec):
        enc.write(f)
    dec.close()
    enc.close()
    assert len(_drain(Decoder(out, 320, 240))) == 24
