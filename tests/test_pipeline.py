"""來源幀率判定的回歸測試。"""
from engine.pipeline import _src_fps
from engine.probe import VideoInfo


def _info(frames: int, duration: float, fps_num: int = 60, fps_den: int = 1) -> VideoInfo:
    return VideoInfo(
        width=2560, height=1440, fps_num=fps_num, fps_den=fps_den,
        frame_count=frames, pix_fmt="yuv420p10le", rotation=0, duration=duration,
        has_audio=True, audio_codec="aac", subtitle_codecs=(), is_hdr=False,
        is_10bit=True,
    )


def test_cfr_uses_container_fps_despite_audio_padding():
    """容器時長含音軌尾巴時，不該用 frame_count/duration 推算幀率。

    實測素材：576 幀 / 9.6212 秒 = 59.868，但影片實際是 60fps（576/60 = 9.6）。
    用 59.868 會讓 575 個原幀全部被誤判為插值幀，補幀次數從 575 變 1150。
    """
    info = _info(576, 9.621188)
    assert _src_fps(info) == 60.0


def test_vfr_falls_back_to_derived_fps():
    """幀數與時長明顯不符時，視為 VFR，改用推算值。"""
    info = _info(250, 10.0)
    assert abs(_src_fps(info) - 25.0) < 1e-9
