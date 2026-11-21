"""模型下載與快取。"""
from __future__ import annotations

import hashlib
import pathlib
import urllib.request

BASE = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0"

MODELS: dict[str, tuple[str, str | None, str]] = {
    "realesr-general-x4v3": (f"{BASE}/realesr-general-x4v3.pth",
        "8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292", "realesr-general-x4v3.pth"),
    "realesr-animevideov3": (f"{BASE}/realesr-animevideov3.pth",
        "b8a8376811077954d82ca3fcf476f1ac3da3e8a68a4f4d71363008000a18b75d", "realesr-animevideov3.pth"),
    "rife426": (
        "https://huggingface.co/hzwer/RIFE/resolve/main/RIFEv4.26_0921.zip",
        "45c7f74156704769dc9f85cfcaf8552e1e926f9399dcfa3a553dee88fac6f53f",
        "flownet.pkl",
    ),
}

DEFAULT_DIR = pathlib.Path(__file__).resolve().parent.parent / "models"


def sha256(path: str | pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_model(name: str, dest_dir: str | pathlib.Path = DEFAULT_DIR) -> str:
    if name not in MODELS:
        raise KeyError(f"未知模型：{name}")
    url, expected, filename = MODELS[name]
    d = pathlib.Path(dest_dir)
    d.mkdir(parents=True, exist_ok=True)
    target = d / filename

    if target.exists() and target.stat().st_size > 0:
        if expected is None or sha256(target) == expected:
            return str(target)

    tmp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)

    if url.endswith(".zip"):
        _extract_member(tmp, filename, target)
        tmp.unlink()
    else:
        tmp.replace(target)

    if expected is not None and sha256(target) != expected:
        target.unlink()
        raise ValueError(f"{name} 校驗失敗（SHA256 不符）")
    return str(target)


def _extract_member(archive: pathlib.Path, filename: str, target: pathlib.Path) -> None:
    import zipfile

    with zipfile.ZipFile(archive) as zf:
        match = [n for n in zf.namelist() if pathlib.PurePosixPath(n).name == filename]
        if not match:
            raise ValueError(f"壓縮檔內找不到 {filename}")
        with zf.open(match[0]) as src, open(target, "wb") as dst:
            while chunk := src.read(1 << 20):
                dst.write(chunk)
