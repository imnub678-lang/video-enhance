"""使用者設定與預設路徑。"""
from __future__ import annotations

import os
import pathlib
import sys

from PySide6.QtCore import QSettings, QStandardPaths

SETTINGS = QSettings("VideoEnhance", "VideoEnhance")


def videos_dir() -> pathlib.Path:
    path = QStandardPaths.writableLocation(QStandardPaths.MoviesLocation)
    return pathlib.Path(path) if path else pathlib.Path.home()


def default_output_dir() -> str:
    from app.ui.i18n import tr

    return str(videos_dir() / tr("outdir.default_name"))


def output_dir() -> str:
    return SETTINGS.value("output_dir") or default_output_dir()


def models_dir() -> str:
    """開發時用專案 models/；打包後改放 %LOCALAPPDATA%（安裝目錄不能寫）。"""
    if not getattr(sys, "frozen", False):
        return str(pathlib.Path(__file__).resolve().parents[2] / "models")
    base = pathlib.Path(os.environ.get("LOCALAPPDATA") or pathlib.Path.home())
    return str(base / "VideoEnhance" / "models")


def setup_done() -> bool:
    # 登錄沒有型別資訊，QSettings 讀回的是字串 "true"，不能拿 is True 比。
    return str(SETTINGS.value("setup_done", False)).lower() == "true"


def mark_setup_done() -> None:
    SETTINGS.setValue("setup_done", True)


def save_output_dir(path: str) -> None:
    SETTINGS.setValue("output_dir", path)


def language() -> str | None:
    return SETTINGS.value("language")
