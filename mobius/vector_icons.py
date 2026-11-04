"""Small consistent monochrome vector icons for Mobius.

Rendered locally with Qt painter primitives: no emoji glyphs, web fonts,
external icon services, extra runtime dependencies or image assets required.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def icon(name: str, size: int = 18, color: str = "#FAFAFA") -> QIcon:
    """Return a crisp 24-unit outline icon at the requested pixel size."""
    size = max(12, min(64, int(size)))
    px = QPixmap(size * 2, size * 2)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 12.0, size / 12.0)
    stroke = QColor(color)
    p.setPen(QPen(stroke, 1.8, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)

    def ln(*coords):
        p.drawLine(QPointF(coords[0], coords[1]), QPointF(coords[2], coords[3]))

    def circle(x, y, r):
        p.drawEllipse(QPointF(x, y), r, r)

    def path(points, close=False):
        shape = QPainterPath(QPointF(*points[0]))
        for point in points[1:]:
            shape.lineTo(*point)
        if close:
            shape.closeSubpath()
        p.drawPath(shape)

    if name in ("battery", "charging"):
        p.drawRoundedRect(QRectF(2, 6, 18, 12), 2, 2)
        ln(22, 10, 22, 14)
        if name == "charging":
            path([(13, 7), (9.5, 12.8), (13, 12.8), (11, 17), (16, 11), (12.5, 11)])
        else:
            ln(5, 9, 5, 15)
            ln(8, 9, 8, 15)
    elif name in ("clock", "timer"):
        circle(12, 12, 9)
        path([(12, 6.5), (12, 12), (16, 14)])
        if name == "timer":
            ln(9, 1, 15, 1)
    elif name == "music":
        path([(10, 16), (10, 5), (19, 3), (19, 14)])
        p.drawEllipse(QRectF(4, 15, 6, 4))
        p.drawEllipse(QRectF(13, 13, 6, 4))
        ln(10, 8, 19, 6)
    elif name == "lyrics":
        for y in (6, 11, 16):
            ln(5, y, 19 if y != 16 else 14, y)
    elif name == "water":
        shape = QPainterPath(QPointF(12, 2))
        shape.cubicTo(9, 7, 5.5, 10.5, 5.5, 14)
        shape.cubicTo(5.5, 19, 9, 21, 12, 21)
        shape.cubicTo(15, 21, 18.5, 19, 18.5, 14)
        shape.cubicTo(18.5, 10.5, 15, 7, 12, 2)
        p.drawPath(shape)
    elif name in ("file", "pdf", "image", "word"):
        path([(6, 2), (14, 2), (19, 7), (19, 22), (6, 22)], True)
        path([(14, 2), (14, 7), (19, 7)])
        if name == "image":
            circle(11, 11, 1)
            path([(8, 18), (11, 14), (13, 16), (16, 12)])
        else:
            ln(9, 13, 16, 13)
            ln(9, 17, 15, 17)
    elif name == "folder":
        path([(3, 7), (10, 7), (12, 9), (21, 9), (21, 19), (3, 19)], True)
        ln(3, 7, 3, 5)
        ln(3, 5, 10, 5)
    elif name == "mic":
        p.drawRoundedRect(QRectF(9, 3, 6, 13), 3, 3)
        shape = QPainterPath(QPointF(5.5, 12))
        shape.cubicTo(5.5, 22, 18.5, 22, 18.5, 12)
        p.drawPath(shape)
        ln(12, 20, 12, 23)
    elif name == "external":
        path([(12, 5), (20, 5), (20, 13)])
        ln(20, 5, 10, 15)
        path([(18, 16), (18, 20), (4, 20), (4, 7), (8, 7)])
    elif name in ("left", "right"):
        if name == "left":
            path([(15, 5), (8, 12), (15, 19)])
        else:
            path([(9, 5), (16, 12), (9, 19)])
    elif name == "play":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(stroke)
        p.drawPolygon(QPolygonF([QPointF(7, 4), QPointF(19, 12), QPointF(7, 20)]))
    elif name == "pause":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(stroke)
        p.drawRoundedRect(QRectF(6, 5, 4, 14), 1, 1)
        p.drawRoundedRect(QRectF(14, 5, 4, 14), 1, 1)
    elif name in ("next", "previous"):
        if name == "next":
            path([(5, 5), (13, 12), (5, 19)])
            ln(18, 5, 18, 19)
        else:
            path([(19, 5), (11, 12), (19, 19)])
            ln(6, 5, 6, 19)
    elif name == "reset":
        shape = QPainterPath(QPointF(20, 9))
        shape.arcTo(QRectF(3, 3, 18, 18), 18, 300)
        p.drawPath(shape)
        path([(20, 4), (20, 9), (15, 9)])
    elif name == "assistant":
        p.drawRoundedRect(QRectF(3, 4, 18, 16), 6, 6)
        circle(9, 12, 1.3)
        circle(15, 12, 1.3)
    elif name == "search":
        circle(10, 10, 6)
        ln(15, 15, 21, 21)
    elif name == "indicator":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(stroke)
        circle(12, 12, 4)
    else:
        circle(12, 12, 7)
    p.end()
    return QIcon(px)


def attach(button, name: str, *, size=17, color="#FAFAFA"):
    button.setIcon(icon(name, size, color))
    button.setIconSize(QSize(size, size))
    return button
