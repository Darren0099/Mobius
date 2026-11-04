"""Mobius's original, restrained two-eye robot identity.

Subtle almond geometry, animated gaze and eyelids replace the old flat,
round white dots. There are no emoji, downloaded graphics or timers doing
heavy work: everything is hand-drawn as native antialiased Qt paths.
"""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class Eyes(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(94, 27)
        self._base_mood = "listening"
        self._flash_mood = None
        self._hold_until = 0.0
        self._expression = "open"
        self._next_expression_at = 0.0
        self._blink_until = 0.0
        self._next_blink = time.monotonic() + 4
        self._last_cursor = QCursor.pos()
        self._last_activity = time.monotonic()
        self._target = QPointF(0, 0)
        self._gaze = QPointF(0, 0)
        self._timer = QTimer(self)
        self._timer.setInterval(55)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_mode(self, mood: str, *, temporary_ms: int = 0):
        if temporary_ms:
            self._flash_mood = mood
            self._hold_until = time.monotonic() + temporary_ms / 1000
        else:
            self._base_mood = mood
        self._next_expression_at = 0.0
        self.update()

    def _select_expression(self, mood: str) -> str:
        if mood == "happy":
            return random.choice(("smile", "smile", "wink"))
        if mood in ("warning", "error"):
            return random.choice(("worried", "squint"))
        if mood == "thinking":
            return random.choice(("thinking", "curious", "focus"))
        if mood == "sleepy":
            return "sleepy"
        if mood == "dozing":
            return "sleep"
        return random.choice(("open", "open", "open", "curious", "wink", "focus"))

    def _tick(self):
        if not self.isVisible():
            return
        now = time.monotonic()
        cursor = QCursor.pos()
        if (abs(cursor.x() - self._last_cursor.x())
                + abs(cursor.y() - self._last_cursor.y())) > 4:
            self._last_activity = now
            self._last_cursor = cursor
        position = self.mapFromGlobal(cursor)
        self._target = QPointF(
            max(-2.8, min(2.8, (position.x() - self.width() / 2) / 38)),
            max(-1.6, min(1.6, (position.y() - self.height() / 2) / 50)),
        )
        new_x = self._gaze.x() * .75 + self._target.x() * .25
        new_y = self._gaze.y() * .75 + self._target.y() * .25
        moving = (abs(new_x - self._gaze.x()) + abs(new_y - self._gaze.y())) > .025
        self._gaze = QPointF(new_x, new_y)

        if self._flash_mood and now >= self._hold_until:
            self._flash_mood = None
            self._next_expression_at = 0
        mood = self._flash_mood or self._base_mood
        if not self._flash_mood and mood in ("listening", "idle"):
            still = now - self._last_activity
            if still >= 300:
                mood = "dozing"
            elif still >= 95:
                mood = "sleepy"
        if now >= self._next_expression_at:
            self._expression = self._select_expression(mood)
            self._next_expression_at = now + (3.6 if mood == "listening" else 2.3)
            moving = True
        if now >= self._next_blink and mood not in ("dozing", "sleepy"):
            self._blink_until = now + 0.15
            self._next_blink = now + random.uniform(3.5, 7.2)
        if moving or now <= self._blink_until:
            self.update()

    def _line(self, painter: QPainter, pts: list[tuple[float, float]], width=3):
        path = QPainterPath(QPointF(*pts[0]))
        for point in pts[1:]:
            path.lineTo(*point)
        painter.setPen(QPen(QColor("#FCFCFE"), width,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _eye(self, painter: QPainter, x: float, y: float, *, scale=1.0):
        """Soft almond silhouette with a moving charcoal pupil and white glint."""
        painter.save()
        painter.translate(x, y)
        painter.scale(scale, scale)
        shape = QPainterPath(QPointF(-10, 0))
        shape.cubicTo(-5.7, -7.6, 4.9, -8.5, 10, 0)
        shape.cubicTo(5.2, 7.1, -5.4, 7.5, -10, 0)
        painter.setPen(QPen(QColor("#F6F6F9"), 2.6,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QColor("#F6F6F9"))
        painter.drawPath(shape)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#151519"))
        painter.drawEllipse(QPointF(self._gaze.x(), self._gaze.y()), 3.5, 4.4)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QPointF(self._gaze.x() - 1.1, self._gaze.y() - 1.1), .9, .9)
        painter.restore()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        mode = self._expression
        if time.monotonic() < self._blink_until:
            mode = "blink"

        left, right = (26, 13.5), (68, 13.5)
        if mode == "open":
            self._eye(p, *left)
            self._eye(p, *right)
        elif mode == "curious":
            self._eye(p, *left, scale=.8)
            self._eye(p, *right, scale=1.18)
        elif mode == "wink":
            self._eye(p, *left)
            self._line(p, [(58, 15), (63, 11), (69, 11), (77, 15)], 3.0)
        elif mode == "focus":
            self._eye(p, *left, scale=.79)
            self._eye(p, *right, scale=.79)
            self._line(p, [(16, 5), (35, 7)], 2.2)
            self._line(p, [(59, 7), (78, 5)], 2.2)
        elif mode == "thinking":
            self._eye(p, *left, scale=.85)
            self._line(p, [(59, 17), (64, 12), (70, 12), (77, 17)])
            self._line(p, [(16, 4), (35, 7)], 2.1)
        elif mode == "smile":
            self._line(p, [(17, 17), (20, 10), (26, 8), (32, 10), (35, 17)], 3.1)
            self._line(p, [(59, 17), (62, 10), (68, 8), (74, 10), (77, 17)], 3.1)
        elif mode == "squint":
            self._line(p, [(18, 8), (31, 14), (18, 20)], 3.1)
            self._line(p, [(76, 8), (63, 14), (76, 20)], 3.1)
        elif mode == "worried":
            self._line(p, [(16, 11), (29, 5)], 2.2)
            self._line(p, [(65, 5), (78, 11)], 2.2)
            self._eye(p, *left, scale=.78)
            self._eye(p, *right, scale=.78)
        elif mode in ("blink", "sleep", "sleepy"):
            if mode == "blink":
                self._line(p, [(18, 14), (34, 14)])
                self._line(p, [(60, 14), (76, 14)])
            else:
                d = 0 if mode == "sleep" else 3
                self._line(p, [(18, 13 - d), (22, 15), (30, 15), (35, 13 - d)], 2.8)
                self._line(p, [(59, 13 - d), (64, 15), (72, 15), (77, 13 - d)], 2.8)
        else:
            self._eye(p, *left)
            self._eye(p, *right)
        p.end()
