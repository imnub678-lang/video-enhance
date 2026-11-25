"""ffprobe 輸出解析。"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, replace

from engine.backend import resolve_ffprobe

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
    frame_times: tuple[float, ...] = ()
    video_duration: float = 0.0
    seek_origin: float = 0.0
    pixel_aspect: float = 1.0

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


def _seconds(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), None)
    if video is None:
        raise ValueError("找不到視訊流")

    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    subs = tuple(s.get("codec_name", "") for s in streams if s.get("codec_type") == "subtitle")

    num, den = _ratio(video.get("avg_frame_rate"))
    if num == 0:
        num, den = _ratio(video.get("r_frame_rate"))

    fmt = raw.get("format") or {}
    video_duration = _seconds(video.get("duration"))
    duration = _seconds(fmt.get("duration")) or video_duration
    sar_num, sar_den = _ratio((video.get("sample_aspect_ratio") or "").replace(":", "/"))

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
        video_duration=video_duration,
        seek_origin=_seconds(fmt.get("start_time")),
        pixel_aspect=sar_num / sar_den if sar_num > 0 and sar_den > 0 else 1.0,
    )


def probe(path: str, *, include_frames: bool = True) -> VideoInfo:
    cmd = [resolve_ffprobe(), "-v", "error"]
    metadata = subprocess.run([*cmd, "-show_streams", "-show_format", "-of", "json", path],
                              capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    info = parse_ffprobe_json(json.loads(metadata.stdout))
    if not include_frames:
        return info

    scan = subprocess.run([*cmd, "-select_streams", "V:0", "-show_frames",
                           "-show_entries", "frame=best_effort_timestamp_time,duration_time",
                           "-of", "compact=p=1:nk=0", path],
                          capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if scan.stderr.strip():
        raise ValueError(scan.stderr.decode("utf-8", "replace").strip())
    times: list[float] = []
    count = 0
    last_duration = 0.0
    for line in scan.stdout.splitlines():
        if not line.startswith(b"frame"):
            continue
        count += 1
        fields = dict(field.split(b"=", 1) for field in line.split(b"|")[1:] if b"=" in field)
        pts = fields.get(b"best_effort_timestamp_time")
        if pts not in (None, b"N/A"):
            times.append(float(pts))
        last_duration = _seconds(fields.get(b"duration_time"))
    if not count:
        raise ValueError("找不到可解碼的視訊影格")
    if len(times) != count or any(a >= b for a, b in zip(times, times[1:])):
        return replace(info, frame_count=count, seek_origin=0.0)
    first = times[0]
    end = times[-1] - first
    duration = end + (last_duration or 1 / (info.fps or 24))
    return replace(info, frame_count=count, frame_times=tuple(t - first for t in times),
                   video_duration=duration, seek_origin=first - info.seek_origin)
