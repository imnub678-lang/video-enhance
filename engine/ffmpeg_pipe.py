"""ffmpeg 解碼與編碼子進程封裝。"""
from __future__ import annotations

import subprocess

import numpy as np

from engine.backend import resolve_ffmpeg

FFMPEG = resolve_ffmpeg()
NO_WINDOW = subprocess.CREATE_NO_WINDOW

COPYABLE_AUDIO = {"aac", "mp3", "ac3", "eac3", "alac", "opus", "flac"}


class Decoder:
    def __init__(self, path: str, width: int, height: int, frame_count: int = 0,
                 start_time: float = 0.0):
        self.width = width
        self.height = height
        self.frame_count = frame_count
        self._frame_bytes = width * height * 3
        cmd = [FFMPEG, "-v", "error"]
        if start_time > 0:
            cmd += ["-ss", f"{start_time:.6f}"]
        cmd += [
            "-i", path,
            "-vf", f"scale={width}:{height}:flags=bicubic",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-",
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     creationflags=NO_WINDOW)

    def read(self) -> np.ndarray | None:
        buf = self.proc.stdout.read(self._frame_bytes)
        if not buf or len(buf) < self._frame_bytes:
            return None
        return np.frombuffer(buf, np.uint8).reshape(self.height, self.width, 3).copy()

    def __len__(self) -> int:
        return self.frame_count

    def close(self) -> None:
        if self.proc.stdout:
            self.proc.stdout.close()
        if self.proc.poll() is None:
            self.proc.terminate()
        err = self.proc.stderr.read() if self.proc.stderr else b""
        self.proc.wait(timeout=10)
        if self.proc.stderr:
            self.proc.stderr.close()
        if self.proc.returncode not in (0, None) and err:
            raise RuntimeError(f"解碼失敗：{err.decode('utf-8', 'replace').strip()[:400]}")


class Encoder:
    def __init__(self, path: str, width: int, height: int, fps: int, source: str,
                 audio_codec: str | None, subtitle_codec: str | None,
                 crf: int = 19, codec: str = "hevc_nvenc"):
        self.width = width
        self.height = height
        self._frame_bytes = width * height * 3

        cmd = [
            FFMPEG, "-v", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        ]
        if audio_codec is not None:
            cmd += ["-i", source]
        cmd += ["-map", "0:v:0"]
        if audio_codec is not None:
            cmd += ["-map", "1:a:0?"]
        if subtitle_codec == "mov_text":
            cmd += ["-map", "1:s:0?", "-c:s", "copy"]

        cmd += ["-c:v", codec]
        if codec == "libx265":
            cmd += ["-crf", str(crf), "-preset", "medium"]
        elif codec == "hevc_amf":
            cmd += ["-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf),
                    "-quality", "balanced"]
        else:
            cmd += ["-preset", "p5", "-cq", str(crf)]
        cmd += ["-pix_fmt", "yuv420p10le"]

        if audio_codec is not None:
            if audio_codec in COPYABLE_AUDIO:
                cmd += ["-c:a", "copy"]
            else:
                cmd += ["-c:a", "aac", "-b:a", "192k"]

        cmd += ["-movflags", "+faststart", path]

        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                                     creationflags=NO_WINDOW)

    def write(self, frame_bgr: np.ndarray) -> None:
        if frame_bgr.shape[:2] != (self.height, self.width):
            raise ValueError(f"幀尺寸不符：{frame_bgr.shape[:2]} != {(self.height, self.width)}")
        self.proc.stdin.write(np.ascontiguousarray(frame_bgr, dtype=np.uint8).tobytes())

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        err = self.proc.stderr.read() if self.proc.stderr else b""
        self.proc.wait()
        if self.proc.stderr:
            self.proc.stderr.close()
        if self.proc.returncode != 0:
            raise RuntimeError(f"編碼失敗：{err.decode('utf-8', 'replace').strip()[:400]}")


def concat_segments(list_path: str, source: str, output: str,
                    audio_codec: str | None, subtitle_codec: str | None) -> None:
    """把分段檔串成成品，並從原始素材掛回音軌與內封字幕。"""
    cmd = [FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", list_path]
    if audio_codec is not None:
        cmd += ["-i", source]
    cmd += ["-map", "0:v:0"]
    if audio_codec is not None:
        cmd += ["-map", "1:a:0?"]
    if subtitle_codec == "mov_text":
        cmd += ["-map", "1:s:0?", "-c:s", "copy"]
    cmd += ["-c:v", "copy"]
    if audio_codec is not None:
        if audio_codec in COPYABLE_AUDIO:
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", output]

    res = subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW)
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"分段串接失敗：{err[:400]}")
