"""Lightweight native Qt animated arc indicators for focus and hydration.

Smooth 60ms+ easing, with motion only while an indicator changes; no heavy
browser engine, SVG asset, network resource or font dependency.
"""
from __future__ import annotations
import math
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QBrush, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .theme import ORANGE
from .vector_icons import icon


class ArcMeter(QWidget):
    def __init__(self, glyph="timer", diameter=86, parent=None):
        super().__init__(parent)
        self.setFixedSize(diameter, diameter)
        self._value = 1.0
        self._target = 1.0
        self._glyph = icon(glyph, max(20, diameter // 3))
        self._timer = QTimer(self)
        self._timer.setInterval(22)
        self._timer.timeout.connect(self._animate)

    def set_fraction(self, fraction: float):
        self._target = max(0.0, min(1.0, float(fraction)))
        if abs(self._target - self._value) > .001:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._value = self._target
            self.update()

    def _animate(self):
        self._value += (self._target - self._value) * .22
        if abs(self._target - self._value) < .002:
            self._value = self._target
            self._timer.stop()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = float(min(self.width(), self.height()))
        thickness = max(7.0, size * .105)
        box = QRectF(thickness, thickness, size - 2*thickness,
                     size - 2*thickness)
        track = QPen(QColor("#35343D"), thickness)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track)
        p.drawArc(box, 90 * 16, 360 * 16)
        if self._value > .001:
            active = QPen(QColor("#FF812E"), thickness)
            active.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(active)
            p.drawArc(box, 90 * 16, -round(self._value * 360 * 16))

        # Radial-repeat microticks, inspired by the user's compact dashboard
        # examples. Orange is reserved for progress; the remaining ticks
        # remain quiet graphite.
        center = size / 2
        for i in range(36):
            angle = -math.pi / 2 + i * 2 * math.pi / 36
            start_radius = size * .448
            end_radius = size * .477
            ink = QColor("#F98636") if i < round(self._value * 36) else QColor("#4C4A50")
            p.setPen(QPen(ink, 1.15, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(
                QPointF(center + math.cos(angle) * start_radius,
                        center + math.sin(angle) * start_radius),
                QPointF(center + math.cos(angle) * end_radius,
                        center + math.sin(angle) * end_radius)
            )
        px = self._glyph.pixmap(round(size*.34), round(size*.34))
        p.drawPixmap(round((size-px.width())/2), round((size-px.height())/2), px)
        p.end()
