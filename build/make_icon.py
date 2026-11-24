"""產生安裝程式與 exe 共用的圖示（純 Qt，無額外依賴）。"""
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

OUT = Path(__file__).resolve().parent / "app.ico"
S = 256


def main() -> None:
    img = QImage(S, S, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    rect = QRectF(12, 12, S - 24, S - 24)
    p.setBrush(QColor("#111722"))
    p.setPen(QPen(QColor("#3A4B6B"), 3))
    p.drawRoundedRect(rect, 52, 52)

    # 兩層向上箭頭：放大 + 提升畫質的意象。
    def arrow(y: float, scale: float, color: str, width: float) -> None:
        half = 68 * scale
        h = 52 * scale
        cx = S / 2
        pts = QPolygonF([
            QPointF(cx - half, y + h),
            QPointF(cx, y),
            QPointF(cx + half, y + h),
        ])
        p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(pts)

    arrow(86, 1.0, "#5B8CFF", 17)
    arrow(140, 0.72, "#7BD3FF", 13)
    p.end()

    if not img.save(str(OUT), "ICO"):
        raise SystemExit("ICO 寫入失敗")
    print(OUT)


if __name__ == "__main__":
    main()
