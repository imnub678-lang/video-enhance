from engine.probe import parse_ffprobe_json


def _raw(video=None, streams_extra=None, fmt=None):
    v = {
        "codec_type": "video", "width": 1920, "height": 1080,
        "avg_frame_rate": "24/1", "r_frame_rate": "24/1",
        "pix_fmt": "yuv420p", "nb_read_frames": "240",
        "color_transfer": "bt709", "color_primaries": "bt709",
    }
    if video:
        v.update(video)
    streams = [v] + (streams_extra or [])
    return {"streams": streams, "format": fmt or {"duration": "10.0"}}


def test_parse_1080p_sdr_with_audio():
    info = parse_ffprobe_json(_raw(streams_extra=[{"codec_type": "audio", "codec_name": "aac"}]))
    assert (info.width, info.height) == (1920, 1080)
    assert (info.fps_num, info.fps_den) == (24, 1)
    assert info.pix_fmt == "yuv420p"
    assert info.frame_count == 240
    assert info.has_audio is True
    assert info.audio_codec == "aac"
    assert info.is_hdr is False
    assert info.is_10bit is False
    assert info.rotation == 0
    assert info.duration == 10.0


def test_no_audio_stream():
    info = parse_ffprobe_json(_raw())
    assert info.has_audio is False
    assert info.audio_codec is None


def test_hdr_detected():
    info = parse_ffprobe_json(_raw(video={"color_transfer": "smpte2084"}))
    assert info.is_hdr is True


def test_10bit_detected():
    info = parse_ffprobe_json(_raw(video={"pix_fmt": "yuv420p10le"}))
    assert info.is_10bit is True


def test_rotation_90():
    info = parse_ffprobe_json(_raw(video={"side_data_list": [{"rotation": -90}]}))
    assert info.rotation == 90


def test_fps_falls_back_to_r_frame_rate():
    info = parse_ffprobe_json(_raw(video={"avg_frame_rate": "0/0", "r_frame_rate": "30000/1001"}))
    assert (info.fps_num, info.fps_den) == (30000, 1001)


def test_subtitle_codecs_collected():
    info = parse_ffprobe_json(_raw(streams_extra=[
        {"codec_type": "subtitle", "codec_name": "mov_text"},
        {"codec_type": "subtitle", "codec_name": "ass"},
    ]))
    assert info.subtitle_codecs == ("mov_text", "ass")
