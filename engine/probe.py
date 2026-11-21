"""ffprobe 輸出解析。"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

FFPROBE = r"D:\ffmpeg\bin\ffprobe.exe"

HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps_num: int
    fps_den: int
    frame_count: int
    pix_fmt: str
    rotation: int
    duration: float
    has_audio: bool
    audio_codec: str | None
    subtitle_codecs: tuple[str, ...]
    is_hdr: bool
    is_10bit: bool

    @property
    def fps(self) -> float:
        return self.fps_num / self.fps_den if self.fps_den else 0.0


def _ratio(text: str | None) -> tuple[int, int]:
    if not text or text in ("0/0", "N/A"):
        return (0, 1)
    num, _, den = text.partition("/")
    try:
        n = int(num)
        d = int(den) if den else 1
    except ValueError:
        return (0, 1)
    return (n, d if d else 1)


def _rotation(stream: dict) -> int:
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            try:
                return abs(int(float(side["rotation"]))) % 360
            except (TypeError, ValueError):
                return 0
    tags = stream.get("tags") or {}
    if "rotate" in tags:
        try:
            return abs(int(float(tags["rotate"]))) % 360
        except (TypeError, ValueError):
            return 0
    return 0


def parse_ffprobe_json(raw: dict) -> VideoInfo:
    streams = raw.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("找不到視訊流")

    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    subs = tuple(s.get("codec_name", "") for s in streams if s.get("codec_type") == "subtitle")

    num, den = _ratio(video.get("avg_frame_rate"))
    if num == 0:
        num, den = _ratio(video.get("r_frame_rate"))

    fmt = raw.get("format") or {}
    duration = float(fmt.get("duration") or video.get("duration") or 0.0)

    frames = video.get("nb_read_frames") or video.get("nb_frames")
    frame_count = int(frames) if frames and str(frames).isdigit() else 0

    pix_fmt = video.get("pix_fmt") or ""
    transfer = video.get("color_transfer") or ""
    primaries = video.get("color_primaries") or ""

    return VideoInfo(
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps_num=num,
        fps_den=den,
        frame_count=frame_count,
        pix_fmt=pix_fmt,
        rotation=_rotation(video),
        duration=duration,
        has_audio=audio is not None,
        audio_codec=audio.get("codec_name") if audio else None,
        subtitle_codecs=subs,
        is_hdr=transfer in HDR_TRANSFERS or primaries == "bt2020",
        is_10bit=("10" in pix_fmt or "12" in pix_fmt),
    )


def probe(path: str) -> VideoInfo:
    cmd = [
        FFPROBE, "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", "-count_frames", path,
    ]
    out = subprocess.run(cmd, capture_output=True, check=True,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    return parse_ffprobe_json(json.loads(out.stdout.decode("utf-8", "replace")))
