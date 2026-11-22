import pytest

from engine.probe import VideoInfo
from engine.policy import Options, decide


def mk(**kw) -> VideoInfo:
    base = dict(width=1920, height=1080, fps_num=24, fps_den=1, frame_count=240,
                pix_fmt="yuv420p", rotation=0, duration=10.0, has_audio=True,
                audio_codec="aac", subtitle_codecs=(), is_hdr=False, is_10bit=False)
    base.update(kw)
    return VideoInfo(**base)


def test_defaults_upscale_and_interpolate():
    p = decide(mk(), Options())
    assert (p.do_sr, p.scale, p.do_fi, p.target_fps, p.tile) == (True, 4, True, 60, 768)
    assert p.model == "realesr-general-x4v3"
    assert p.reject_reason is None


def test_sr_only():
    p = decide(mk(), Options(do_fi=False))
    assert (p.do_sr, p.do_fi) == (True, False)


def test_fi_only_keeps_resolution():
    p = decide(mk(), Options(do_sr=False))
    assert (p.do_sr, p.scale, p.tile, p.do_fi) == (False, 0, 0, True)
    assert p.model == ""


def test_both_off_is_rejected():
    assert decide(mk(), Options(do_sr=False, do_fi=False)).reject_reason is not None


def test_rejects_4k_input_when_upscaling():
    assert decide(mk(width=3840, height=2160), Options()).reject_reason is not None


def test_4k_input_allowed_when_only_interpolating():
    p = decide(mk(width=3840, height=2160), Options(do_sr=False))
    assert p.reject_reason is None


def test_hdr_rejected():
    assert decide(mk(is_hdr=True), Options()).reject_reason is not None


def test_10bit_sdr_allowed():
    p = decide(mk(is_10bit=True, pix_fmt="yuv420p10le"), Options())
    assert p.reject_reason is None


def test_single_frame_rejected_when_interpolating():
    assert decide(mk(frame_count=1), Options()).reject_reason is not None


def test_single_frame_allowed_when_only_upscaling():
    p = decide(mk(frame_count=1), Options(do_fi=False))
    assert p.reject_reason is None


def test_60fps_source_skips_interpolation_to_60():
    p = decide(mk(fps_num=60), Options(do_sr=True))
    assert p.do_fi is False


def test_60fps_source_interpolates_to_120():
    p = decide(mk(fps_num=60), Options(do_sr=False, target_fps=120))
    assert (p.do_fi, p.target_fps) == (True, 120)


def test_60fps_source_without_sr_and_target_60_is_rejected():
    p = decide(mk(fps_num=60), Options(do_sr=False))
    assert p.reject_reason is not None


def test_120fps_source_skips_interpolation():
    assert decide(mk(fps_num=120), Options(do_sr=True)).do_fi is False


def test_model_choice_sets_scale_and_tile():
    p = decide(mk(), Options(model="x2plus"))
    assert (p.scale, p.tile, p.model) == (2, 384, "RealESRGAN_x2plus")
    q = decide(mk(), Options(model="x4plus"))
    assert (q.scale, q.tile, q.model) == (4, 384, "RealESRGAN_x4plus")


def test_anime_model_choice():
    p = decide(mk(), Options(model="anime"))
    assert p.model == "realesr-animevideov3"


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        decide(mk(), Options(model="x8plus"))


def test_invalid_target_fps_raises():
    with pytest.raises(ValueError):
        decide(mk(), Options(target_fps=48))
