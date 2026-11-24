"""深色玻璃主題：配色與樣式表。"""
from __future__ import annotations

import pathlib

from PySide6.QtGui import QFont

ASSETS = pathlib.Path(__file__).resolve().parent / "assets"

TEXT = "#E9ECF2"
TEXT_DIM = "#9BA4B4"
TEXT_FAINT = "#79839A"
ACCENT = "#5B8CFF"
ACCENT_HOVER = "#6E9BFF"
ACCENT_PRESS = "#4674E6"

_QSS = """
QWidget {
    color: #E9ECF2;
    font-size: 13px;
}
QWidget#shell, QWidget#content { background: transparent; }
QDialog, QStackedWidget, QStackedWidget > QWidget { background: #14171E; }
QLabel { background: transparent; }
QLabel#appIcon { color: #5B8CFF; font-size: 16px; }
QLabel#appTitle { font-size: 13px; font-weight: 600; }
QLabel#section { font-size: 11px; font-weight: 600; color: #8A93A6; }
QLabel#pct { font-size: 13px; font-weight: 600; color: #5B8CFF; }
QLabel#status { font-size: 12px; color: #9BA4B4; }
QLabel#field { font-size: 12px; color: #98A1B1; }
QLabel#dropLabel { font-size: 13px; color: #B6BFCE; }
QLabel#hint { font-size: 11px; color: #79839A; }

QFrame#card {
    background: rgba(255, 255, 255, 20);
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 12px;
}
QFrame#dropZone {
    background: rgba(91, 140, 255, 22);
    border: 1px dashed rgba(255, 255, 255, 58);
    border-radius: 10px;
}
QFrame#dropZone[drag="true"] {
    background: rgba(91, 140, 255, 52);
    border: 1px dashed #5B8CFF;
}
QFrame#hline { background: rgba(255, 255, 255, 26); border: none; max-height: 1px; }

QPushButton#primary {
    background: #5B8CFF;
    color: #0A0E17;
    border: none;
    border-radius: 8px;
    padding: 9px 24px;
    font-weight: 600;
}
QPushButton#primary:hover { background: #6E9BFF; }
QPushButton#primary:pressed { background: #4674E6; }
QPushButton#primary:disabled { background: rgba(255, 255, 255, 20); color: #6B7382; }

QPushButton#ghost {
    background: rgba(255, 255, 255, 8);
    color: #C7CEDB;
    border: 1px solid rgba(255, 255, 255, 28);
    border-radius: 8px;
    padding: 8px 18px;
}
QPushButton#ghost:hover { background: rgba(255, 255, 255, 22); border-color: rgba(255, 255, 255, 46); }
QPushButton#ghost:pressed { background: rgba(255, 255, 255, 12); }
QPushButton#ghost:disabled { color: #5E6675; border-color: rgba(255, 255, 255, 12); background: transparent; }

QPushButton#winBtn, QPushButton#winBtnClose {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: #C7CEDB;
    font-family: "Segoe Fluent Icons";
    font-size: 10px;
}
QPushButton#winBtn:hover { background: rgba(255, 255, 255, 26); }
QPushButton#winBtnClose:hover { background: #C42B1C; color: #FFFFFF; }

QLineEdit, QComboBox {
    background: rgba(255, 255, 255, 10);
    border: 1px solid rgba(255, 255, 255, 28);
    border-radius: 8px;
    padding: 7px 10px;
    color: #E9ECF2;
    selection-background-color: #5B8CFF;
    selection-color: #0A0E17;
}
QLineEdit:hover, QComboBox:hover { border-color: rgba(255, 255, 255, 44); }
QLineEdit:focus, QComboBox:focus { border-color: #5B8CFF; background: rgba(91, 140, 255, 22); }
QLineEdit:disabled, QComboBox:disabled { color: #6B7382; background: rgba(255, 255, 255, 6); }

QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow {
    image: url("@CHEVRON@");
    width: 10px;
    height: 6px;
    margin-right: 9px;
}
QComboBox QAbstractItemView {
    background: #1A1D24;
    border: 1px solid rgba(255, 255, 255, 32);
    border-radius: 8px;
    padding: 4px;
    outline: none;
    color: #E9ECF2;
    selection-background-color: rgba(91, 140, 255, 70);
    selection-color: #FFFFFF;
}
QComboBox QAbstractItemView::item { min-height: 26px; padding: 2px 8px; }

QCheckBox { spacing: 9px; color: #E9ECF2; }
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 64);
    background: rgba(255, 255, 255, 10);
}
QCheckBox::indicator:hover { border-color: rgba(91, 140, 255, 150); }
QCheckBox::indicator:checked {
    background: #5B8CFF;
    border-color: #5B8CFF;
    image: url("@CHECK@");
}
QCheckBox:disabled { color: #6B7382; }

QProgressBar {
    background: rgba(255, 255, 255, 18);
    border: none;
    border-radius: 3px;
}
QProgressBar::chunk {
    border-radius: 3px;
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #5B8CFF, stop: 1 #7BD3FF);
}

QPlainTextEdit {
    background: transparent;
    border: none;
    color: #A9B2C2;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    selection-background-color: rgba(91, 140, 255, 80);
}

QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255, 255, 255, 36); border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 64); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px; }
QScrollBar::handle:horizontal { background: rgba(255, 255, 255, 36); border-radius: 4px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QToolTip {
    background: #1A1D24;
    color: #E9ECF2;
    border: 1px solid rgba(255, 255, 255, 34);
    padding: 4px 8px;
}
"""

QSS = (_QSS
       .replace("@CHECK@", (ASSETS / "check.svg").as_posix())
       .replace("@CHEVRON@", (ASSETS / "chevron.svg").as_posix()))


def app_font() -> QFont:
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Microsoft YaHei UI", "Segoe UI"])
    font.setPointSize(10)
    return font
