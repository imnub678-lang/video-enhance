# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir 打包設定（NVIDIA / AMD 共用）。

AMD 版需先在 ROCm 版 torch 環境下執行；本機是 CUDA 版，只能產出 NVIDIA 版。
"""
import pathlib

from PyInstaller.utils.hooks import collect_submodules

ROOT = pathlib.Path(SPECPATH).resolve().parent  # noqa: F821  (PyInstaller 注入的是 spec 所在資料夾)

datas = [
    (str(ROOT / "app" / "ui" / "assets"), "app/ui/assets"),
    (str(ROOT / "encoders"), "encoders"),
    (r"D:\ffmpeg\bin\ffmpeg.exe", "tools"),
]

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("engine") + collect_submodules("app"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "tkinter", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VideoEnhance",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "build" / "app.ico"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VideoEnhance",
)
