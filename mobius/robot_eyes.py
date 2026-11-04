"""Original kaomoji-inspired robot face rendered with antialiased Qt strokes.

A compact white-on-black face, not emoji/font glyphs or an image asset.
Eyelids, pupils, tiny expressions and mouth shapes morph with a soft
cross-fade. The facial vocabulary is intentionally similar in spirit to
user-supplied reference sketches, without copying their pixels.
"""
from __future__ import annotations

import random
import time

from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


EXPRESSIONS = {
    "listening": ("neutral", "curious", "smile", "wink", "neutral"),
    "idle": ("neutral", "smile", "curious", "wink"),
    "thinking": ("thinking", "focus", "curious"),
    "happy": ("happy", "happy", "excited", "wink"),
    "warning": ("worried", "sad", "confused"),
    "error": ("worried", "confused"),
    "focus": ("focus", "focus", "determined"),
    "sleepy": ("sleepy",),
    "dozing": ("sleep",),
    "surprised": ("surprised",),
    "angry": ("angry",),
    "sad": ("sad",),
    "smug": ("smug",),
    "kiss": ("kiss",),
}
WHITE = QColor("#FFFAFC")


class Eyes(QWidget):
    """Compact expressive 94x29 face with natural idle and cursor motion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(94, 29)
        self._base_mood = "listening"
        self._flash_mood = None
        self._hold_until = 0.0
        self._expression = "neutral"
        self._previous = "neutral"
        self._transition_at = 0.0
        self._next_expression_at = 0.0
        self._blink_until = 0.0
        self._next_blink = time.monotonic() + 3.5
        self._last_cursor = QCursor.pos()
        self._last_activity = time.monotonic()
        self._gaze = QPointF(0, 0)
        self._target = QPointF(0, 0)
        self._timer = QTimer(self)
        self._timer.setInterval(42)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_mode(self, mood: str, *, temporary_ms: int = 0):
        if temporary_ms:
            self._flash_mood = mood
            self._hold_until = time.monotonic() + temporary_ms / 1000
        else:
            self._base_mood = mood
        self._next_expression_at = 0
        self._tick()

    def _tick(self):
        if not self.isVisible():
            return
        now = time.monotonic()
        cursor = QCursor.pos()
        distance = abs(cursor.x() - self._last_cursor.x()) + abs(cursor.y() - self._last_cursor.y())
        if distance > 4:
            self._last_activity = now
            self._last_cursor = cursor
        local = self.mapFromGlobal(cursor)
        self._target = QPointF(
            max(-2.1, min(2.1, (local.x() - self.width() / 2) / 41)),
            max(-1.2, min(1.2, (local.y() - self.height() / 2) / 48)),
        )
        self._gaze = QPointF(
            .78 * self._gaze.x() + .22 * self._target.x(),
            .78 * self._gaze.y() + .22 * self._target.y(),
        )

        if self._flash_mood and now >= self._hold_until:
            self._flash_mood = None
            self._next_expression_at = 0
        mood = self._flash_mood or self._base_mood
        if not self._flash_mood and mood in ("idle", "listening"):
            inactivity = now - self._last_activity
            if inactivity >= 300:
                mood = "dozing"
            elif inactivity >= 95:
                mood = "sleepy"
        if now >= self._next_expression_at:
            self._previous = self._expression
            self._expression = random.choice(EXPRESSIONS.get(mood, EXPRESSIONS["idle"]))
            self._transition_at = now
            self._next_expression_at = now + (5.3 if mood == "listening" else 3.4)
        if now >= self._next_blink and mood not in ("sleepy", "dozing"):
            self._blink_until = now + .13
            self._next_blink = now + random.uniform(3.3, 6.0)
        self.update()

    @staticmethod
    def _stroke(p: QPainter, points, *, width=2.8, closed=False):
        path = QPainterPath(QPointF(*points[0]))
        for x, y in points[1:]:
            path.lineTo(x, y)
        if closed:
            path.closeSubpath()
        p.setPen(QPen(WHITE, width, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    @staticmethod
    def _curve(p: QPainter, points, *, width=2.8):
        path = QPainterPath(QPointF(*points[0]))
        # Three points define a clean symmetric quadratic curve.
        path.quadTo(QPointF(*points[1]), QPointF(*points[2]))
        p.setPen(QPen(WHITE, width, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    @staticmethod
    def _oval(p: QPainter, x, y, rx, ry, *, filled=False):
        p.setPen(QPen(WHITE, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(WHITE if filled else Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(x, y), rx, ry)

    def _look(self, p, x, y, *, big=False):
        rx, ry = (7.5, 8.8) if big else (6.8, 7.6)
        self._oval(p, x, y, rx, ry, filled=False)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(WHITE)
        p.drawEllipse(QPointF(x + self._gaze.x(), y + self._gaze.y()), 2, 2.5)

    def _eye_shape(self, p: QPainter, x: float, y: float, kind: str):
        if kind == "look":
            self._look(p, x, y)
        elif kind == "wide":
            self._look(p, x, y, big=True)
        elif kind == "dot":
            self._oval(p, x, y, 3.1, 3.1, filled=True)
        elif kind == "flat":
            self._stroke(p, [(x-8, y), (x+8, y)], width=2.7)
        elif kind == "smile":
            self._curve(p, [(x-8, y+3), (x, y-7), (x+8, y+3)], width=3.2)
        elif kind == "droop":
            self._curve(p, [(x-8, y-4), (x, y+3), (x+8, y-4)], width=2.6)
        elif kind == "angry":
            self._stroke(p, [(x-8, y+6), (x, y-4), (x+8, y+6)], width=2.8)
        elif kind == "wink":
            self._curve(p, [(x-7, y+1), (x, y-6), (x+7, y+1)], width=2.8)
        elif kind == "sleep":
            self._stroke(p, [(x-8, y+3), (x+8, y+3)], width=3.1)
        elif kind == "half":
            self._curve(p, [(x-8, y+1), (x, y-1), (x+8, y+1)], width=2.7)
            self._oval(p, x, y+3, 2, 2, filled=True)

    def _mouth(self, p: QPainter, kind: str):
        x, y = 47, 20
        if kind == "smile":
            self._curve(p, [(x-6, y-3), (x, y+8), (x+6, y-3)], width=2.3)
        elif kind == "cat":
            self._curve(p, [(x-7, y), (x-4, y+6), (x, y+1)], width=2.2)
            self._curve(p, [(x, y+1), (x+4, y+6), (x+7, y)], width=2.2)
        elif kind == "open":
            self._oval(p, x, y+1.5, 3.6, 4.3)
        elif kind == "kiss":
            self._curve(p, [(x-2, y-5), (x+6, y-2), (x, y+2)], width=2.2)
            self._curve(p, [(x, y+2), (x+7, y+8), (x-1, y+8)], width=2.2)
        elif kind == "sad":
            self._curve(p, [(x-5, y+5), (x, y-1), (x+5, y+5)], width=2.1)
        elif kind == "w":
            self._stroke(p, [(x-5, y-1), (x-2, y+3), (x, y), (x+2, y+3), (x+5, y-1)], width=2.3)
        elif kind == "smirk":
            self._stroke(p, [(x-4, y+1), (x+5, y-2)], width=2.1)
        elif kind == "flat":
            self._stroke(p, [(x-3, y+1), (x+3, y+1)], width=2.0)

    def _draw(self, p: QPainter, expression: str):
        # Coordinates are kept within the small notch even during blinking.
        pairs = {
            "neutral": (("flat", "flat"), "cat"),
            "happy": (("smile", "smile"), "cat"),
            "excited": (("dot", "dot"), "open"),
            "smile": (("wink", "smile"), "smile"),
            "wink": (("look", "wink"), "w"),
            "curious": (("look", "wide"), "cat"),
            "focus": (("half", "half"), "flat"),
            "thinking": (("half", "look"), "smirk"),
            "determined": (("angry", "angry"), "w"),
            "worried": (("droop", "droop"), "sad"),
            "confused": (("wide", "half"), "flat"),
            "sad": (("droop", "droop"), "sad"),
            "angry": (("angry", "angry"), "sad"),
            "surprised": (("wide", "wide"), "open"),
            "smug": (("half", "half"), "smirk"),
            "kiss": (("flat", "flat"), "kiss"),
            "sleepy": (("droop", "droop"), "w"),
            "sleep": (("sleep", "sleep"), "flat"),
            "blink": (("sleep", "sleep"), "cat"),
        }
        eyes, mouth = pairs.get(expression, pairs["neutral"])
        self._eye_shape(p, 23, 10, eyes[0])
        self._eye_shape(p, 71, 10, eyes[1])
        self._mouth(p, mouth)
        if expression == "sad":
            self._oval(p, 10, 20, 1.3, 3.0, filled=False)
            self._oval(p, 84, 20, 1.3, 3.0, filled=False)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = time.monotonic()
        if now < self._blink_until:
            self._draw(p, "blink")
        else:
            amount = max(0.0, min(1.0, (now - self._transition_at) / .22))
            amount = 1 - (1-amount) ** 3
            if amount < 1 and self._previous != self._expression:
                p.setOpacity(1 - amount)
                self._draw(p, self._previous)
            p.setOpacity(amount)
            self._draw(p, self._expression)
        p.end()
