import subprocess
import pathlib
import pytest

FFMPEG = r"D:\ffmpeg\bin\ffmpeg.exe"
TMP = pathlib.Path(__file__).parent / "tmp"


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, capture_output=True, check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)


@pytest.fixture
def make_clip(tmp_path):
    def _make(fps: int = 24, seconds: float = 1, width: int = 320, height: int = 240,
              has_audio: bool = True, rotation: int = 0, name: str = "clip.mp4") -> str:
        out = str(tmp_path / name)
        cmd = [FFMPEG, "-y", "-v", "error",
               "-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate={fps}:duration={seconds}"]
        if has_audio:
            cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if has_audio:
            cmd += ["-c:a", "aac", "-shortest"]
        if rotation:
            cmd += ["-metadata:s:v:0", f"rotate={rotation}"]
        cmd += [out]
        _run(cmd)
        return out
    return _make
