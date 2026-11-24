"""無邊框視窗外殼 + 自繪磨砂玻璃背景。

Windows 的 DWM 亞克力對 Qt 的分層視窗不做背景採樣（只會退回單色），
所以磨砂層由程式自己畫：取桌面壁紙、預先模糊，再依視窗位置做視差裁切。
"""
from __future__ import annotations

import ctypes
import pathlib
import sys
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRegion,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from .i18n import tr

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWCP_ROUND = 2
DWMWA_COLOR_NONE = 0xFFFFFFFE
SPI_GETDESKWALLPAPER = 0x0073

CURSORS = {
    "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
    "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
    "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
    "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
}


def apply_dwm_chrome(hwnd: int) -> None:
    """深色沉浸模式 + 圓角 + 去邊框線。不支援時靜默略過。"""
    if sys.platform != "win32":
        return
    try:
        dwm = ctypes.windll.dwmapi
    except (AttributeError, OSError):
        return
    handle = wintypes.HWND(hwnd)
    for attr, value in (
        (DWMWA_USE_IMMERSIVE_DARK_MODE, 1),
        (DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND),
        (DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE),
    ):
        arg = ctypes.c_uint32(value)
        dwm.DwmSetWindowAttribute(handle, attr, ctypes.byref(arg), ctypes.sizeof(arg))


def desktop_wallpaper_path() -> str:
    if sys.platform != "win32":
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETDESKWALLPAPER, len(buf), buf, 0)
        return buf.value if ok else ""
    except (AttributeError, OSError):
        return ""


def blurred_wallpaper(size: QSize, radius: int = 14) -> QPixmap | None:
    """把壁紙縮放到指定尺寸並做兩輪降採樣模糊。"""
    path = desktop_wallpaper_path()
    if not path or not pathlib.Path(path).exists():
        return None
    source = QPixmap(path)
    if source.isNull() or size.isEmpty():
        return None
    pixmap = source.scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    for divisor in (radius, radius // 2):
        if divisor < 2:
            continue
        small = pixmap.scaled(
            max(1, pixmap.width() // divisor), max(1, pixmap.height() // divisor),
            Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        pixmap = small.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return pixmap


class GlassWindow(QMainWindow):
    """自繪標題列的無邊框視窗，背景是模糊壁紙 + 深色玻璃色調。"""

    RADIUS = 12
    EDGE = 6
    MIN_W = 860
    MIN_H = 560
    TINT_TOP = QColor(12, 15, 21, 200)
    TINT_BOTTOM = QColor(9, 11, 16, 222)
    FALLBACK = QColor(17, 20, 27)

    def __init__(self, title: str, icon: str = "◈"):
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self._edges = ""
        self._press_pos: QPoint | None = None
        self._press_geo = QRect()
        self._screen_geo = QRect()
        self._wall: QPixmap | None = None
        self._build_shell(title, icon)
        self._load_backdrop()

    # ---------- 背景 ----------
    def _load_backdrop(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        self._screen_geo = screen.geometry()
        self._wall = blurred_wallpaper(screen.size())

    def _apply_mask(self) -> None:
        if self.isMaximized():
            self.clearMask()
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.RADIUS, self.RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        if self._wall is None:
            painter.fillRect(self.rect(), self.FALLBACK)
        else:
            origin = self.geometry().topLeft() - self._screen_geo.topLeft()
            source = QRect(origin, QSize(self.width(), self.height())).intersected(self._wall.rect())
            painter.fillRect(self.rect(), self.FALLBACK)
            if not source.isEmpty():
                painter.drawPixmap(source.translated(-origin), self._wall, source)
            tint = QLinearGradient(0, 0, 0, self.height())
            tint.setColorAt(0.0, self.TINT_TOP)
            tint.setColorAt(1.0, self.TINT_BOTTOM)
            painter.fillRect(self.rect(), tint)
            sheen = QLinearGradient(0, 0, 0, 120)
            sheen.setColorAt(0.0, QColor(255, 255, 255, 16))
            sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.fillRect(self.rect(), sheen)

        if not self.isMaximized():
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                                self.RADIUS, self.RADIUS)
            painter.setPen(QPen(QColor(255, 255, 255, 32), 1))
            painter.drawPath(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_mask()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.update()

    # ---------- 外殼 ----------
    def _build_shell(self, title: str, icon: str) -> None:
        shell = QWidget()
        shell.setObjectName("shell")
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_title_bar(title, icon))

        self.content = QWidget()
        self.content.setObjectName("content")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(16, 6, 16, 14)
        self.content_layout.setSpacing(12)
        outer.addWidget(self.content, 1)
        self.setCentralWidget(shell)

    def _build_title_bar(self, title: str, icon: str) -> QWidget:
        self._titlebar = QWidget()
        self._titlebar.setObjectName("titleBar")
        self._titlebar.setFixedHeight(40)
        row = QHBoxLayout(self._titlebar)
        row.setContentsMargins(16, 0, 8, 0)
        row.setSpacing(9)

        logo = QLabel(icon)
        logo.setObjectName("appIcon")
        name = QLabel(title)
        name.setObjectName("appTitle")
        row.addWidget(logo)
        row.addWidget(name)
        row.addStretch(1)

        self.btn_min = self._win_button("\ue921", tr("tip.min"), self.showMinimized)
        self.btn_max = self._win_button("\ue922", tr("tip.max"), self._toggle_max)
        self.btn_close = self._win_button("\ue8bb", tr("tip.close"), self.close, close=True)
        for button in (self.btn_min, self.btn_max, self.btn_close):
            row.addWidget(button)
        return self._titlebar

    @staticmethod
    def _win_button(glyph: str, tip: str, slot, close: bool = False) -> QPushButton:
        button = QPushButton(glyph)
        button.setObjectName("winBtnClose" if close else "winBtn")
        button.setToolTip(tip)
        button.setFixedSize(44, 30)
        button.setCursor(Qt.ArrowCursor)
        button.setFocusPolicy(Qt.NoFocus)
        button.clicked.connect(slot)
        return button

    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            self.btn_max.setText("\ue923" if self.isMaximized() else "\ue922")
            self._apply_mask()
            self.update()

    def showEvent(self, event):
        super().showEvent(event)
        apply_dwm_chrome(int(self.winId()))

    # ---------- 縮放與拖動 ----------
    def _edges_at(self, pos: QPoint) -> str:
        if self.isMaximized():
            return ""
        m = self.EDGE
        left, right = pos.x() < m, pos.x() > self.width() - m
        top, bottom = pos.y() < m, pos.y() > self.height() - m
        if top and left:
            return "tl"
        if top and right:
            return "tr"
        if bottom and left:
            return "bl"
        if bottom and right:
            return "br"
        if left:
            return "l"
        if right:
            return "r"
        if top:
            return "t"
        if bottom:
            return "b"
        return ""

    def _in_titlebar(self, global_pos: QPoint) -> bool:
        return self._titlebar.rect().contains(self._titlebar.mapFromGlobal(global_pos))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        cursor = event.globalPosition().toPoint()
        edges = self._edges_at(self.mapFromGlobal(cursor))
        if edges or self._in_titlebar(cursor):
            self._edges = edges
            self._press_pos = cursor
            self._press_geo = self.geometry()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        cursor = event.globalPosition().toPoint()
        if self._press_pos is None:
            self.setCursor(CURSORS.get(self._edges_at(self.mapFromGlobal(cursor)), Qt.ArrowCursor))
            return super().mouseMoveEvent(event)

        delta = cursor - self._press_pos
        if self._edges:
            self._resize_to(delta)
        else:
            self._drag_to(delta, cursor)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._edges = ""
        self._press_pos = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._in_titlebar(event.globalPosition().toPoint()):
            self._toggle_max()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _resize_to(self, delta: QPoint) -> None:
        geo = QRect(self._press_geo)
        if "l" in self._edges:
            geo.setLeft(min(self._press_geo.left() + delta.x(), geo.right() - self.MIN_W))
        if "r" in self._edges:
            geo.setRight(max(self._press_geo.right() + delta.x(), geo.left() + self.MIN_W))
        if "t" in self._edges:
            geo.setTop(min(self._press_geo.top() + delta.y(), geo.bottom() - self.MIN_H))
        if "b" in self._edges:
            geo.setBottom(max(self._press_geo.bottom() + delta.y(), geo.top() + self.MIN_H))
        self.setGeometry(geo)

    def _drag_to(self, delta: QPoint, cursor: QPoint) -> None:
        if self.isMaximized():
            ratio = cursor.x() / max(1, self.width())
            normal = self.normalGeometry()
            normal.moveTo(cursor.x() - int(normal.width() * ratio), cursor.y() - 20)
            self.showNormal()
            self.setGeometry(normal)
            self._press_geo = QRect(normal)
            self._press_pos = cursor
            return
        self.move(self._press_geo.topLeft() + delta)
