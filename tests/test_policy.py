from engine.probe import VideoInfo
from engine.policy import decide


def mk(**kw) -> VideoInfo:
    base = dict(width=1920, height=1080, fps_num=24, fps_den=1, frame_count=240,
                pix_fmt="yuv420p", rotation=0, duration=10.0, has_audio=True,
                audio_codec="aac", subtitle_codecs=(), is_hdr=False, is_10bit=False)
    base.update(kw)
    return VideoInfo(**base)


def test_1080p24_balanced_upscales_and_interpolates():
    p = decide(mk(), "balanced")
    assert (p.do_sr, p.scale, p.do_fi, p.target_fps, p.tile) == (True, 4, True, 60, 768)
    assert p.reject_reason is None


def test_720p_upscales_with_x4():
    p = decide(mk(width=1280, height=720), "balanced")
    assert (p.do_sr, p.scale) == (True, 4)


def test_over_1080p_rejected():
    assert decide(mk(width=2560, height=1440), "balanced").reject_reason is not None


def test_over_1080p_allowed_for_fi_only():
    p = decide(mk(width=2560, height=1440), "fi_only")
    assert p.reject_reason is None
    assert p.do_sr is False


def test_60fps_skips_interpolation():
    assert decide(mk(fps_num=60), "balanced").do_fi is False


def test_120fps_skips_interpolation():
    assert decide(mk(fps_num=120), "balanced").do_fi is False


def test_hdr_rejected():
    assert decide(mk(is_hdr=True), "balanced").reject_reason is not None


def test_ten_bit_rejected():
    assert decide(mk(is_10bit=True, pix_fmt="yuv420p10le"), "balanced").reject_reason is not None


def test_single_frame_rejected():
    assert decide(mk(frame_count=1), "balanced").reject_reason is not None


def test_sr_only_disables_interpolation():
    p = decide(mk(), "sr_only")
    assert (p.do_sr, p.do_fi) == (True, False)


def test_all_sr_presets_use_768_tile():
    assert {decide(mk(), p).tile for p in ("balanced", "quality", "fast", "sr_only")} == {768}
