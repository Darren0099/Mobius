"""Independent, keyboard-dismissable radial File Studio.

Nine native Qt-painted radial petals follow the supplied design references.
The top-notch is not resized. File operations still call the existing offline
converter and reject incompatible extensions before work starts.
"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPainter, QPainterPath, QPen, QLinearGradient
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget

from .engine import BY_KEY, OPERATIONS, IMAGES, PDF, WORD, supported
from .theme import ORANGE, CORAL, RED, SURFACE, SURFACE_RAISED

SUPPORTED = frozenset(IMAGES | PDF | WORD)
PALETTE = (
    "#FFA54C", "#FF9945", "#FF8B43", "#FF7944", "#FF6A43",
    "#FF5E48", "#F95349", "#EC454D", "#E13A51",
)


def eligible_files(paths) -> bool:
    return bool(paths) and all(
        isinstance(p, Path) and p.is_file() and p.suffix.lower() in SUPPORTED
        for p in paths
    )


def eligible_operations(paths) -> list[str]:
    return [op.key for op in OPERATIONS if supported(list(paths), op.key)]


def wheel_hit(x: float, y: float, width: float, height: float, count: int = 9) -> int:
    """Return sector index, -1 outside ring, -2 for middle 'choose files' disc."""
    if count < 1:
        return -1
    center_y = height / 2 + 6
    dx, dy = x - width / 2, y - center_y
    radius = math.hypot(dx, dy)
    if radius < 70:
        return -2
    if radius < 79 or radius > 226:
        return -1
    # First petal occupies 40 degrees centered on 12 o'clock.
    clockwise_from_top = (math.degrees(math.atan2(dy, dx)) + 90) % 360
    return int((clockwise_from_top + 180 / count) // (360 / count)) % count


class RadialStudio(QWidget):
    """Animated screen-centered nine-option conversion palette."""

    operation_requested = Signal(str)
    files_chosen = Signal(object)
    drop_finished = Signal()
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(
            parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setObjectName("radialStudio")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setFixedSize(450, 450)
        self.files: list[Path] = []
        self.highlight = -1
        self.message = "Drop a file or select one to begin"
        self._options = list(OPERATIONS)
        self._pop = [0.0] * len(self._options)
        self._animation = QTimer(self)
        self._animation.setInterval(16)
        self._animation.timeout.connect(self._animate)
        self._choose_dialog_open = False
        self._labels = {
            "image_pdf": ("Image", "to PDF"),
            "pdf_image": ("PDF", "to Image"),
            "word_pdf": ("Word", "to PDF"),
            "pdf_word": ("PDF", "to Word"),
            "merge_pdf": ("Merge", "PDF"),
            "split_pdf": ("Split", "PDF"),
            "compress_pdf": ("Compress", "PDF"),
            "rotate_pdf": ("Rotate", "PDF"),
            "convert_image": ("Image", "Format"),
        }

    def set_files(self, paths: list[Path]):
        self.files = list(paths) if eligible_files(paths) else []
        if self.files:
            self.message = (self.files[0].name[:32] if len(self.files) == 1
                            else f"{len(self.files)} files selected")
        else:
            self.message = "Select a PDF, document or image"
        self._animate()
        self.update()

    def show_centered(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        self.move(available.x() + (available.width() - self.width()) // 2,
                  available.y() + (available.height() - self.height()) // 2)
        self.show()
        self.raise_()
        self._animation.start()
        self.update()

    def _animate(self):
        """Ease only eligible petals outward; hover has a larger 16px lift."""
        valid = set(eligible_operations(self.files))
        changed = False
        for index, spec in enumerate(self._options):
            target = 1.0 if index == self.highlight and spec.key in valid else (
                .20 if spec.key in valid else 0.0
            )
            old = self._pop[index]
            new = old + (target - old) * .23
            if abs(new - target) < .012:
                new = target
            if abs(new - old) > .001:
                changed = True
            self._pop[index] = new
        if changed:
            self.update()

    def pop_distance(self, index: int) -> float:
        return 16.0 * self._pop[index]

    @staticmethod
    def _petal(index: int, center: QPointF, count: int = 9,
               boost: float = 0.0) -> QPainterPath:
        sweep = 360 / count
        mid = -90 + index * sweep
        start, stop = mid - sweep / 2 + 2.1, mid + sweep / 2 - 2.1
        result = QPainterPath()
        first = True
        for radius, a1, a2, steps in ((202 + 3*boost, start, stop, 20), (80 + boost, stop, start, 20)):
            for j in range(steps + 1):
                angle = math.radians(a1 + (a2 - a1) * j / steps)
                p = QPointF(center.x() + radius * math.cos(angle),
                            center.y() + radius * math.sin(angle))
                if first:
                    result.moveTo(p)
                    first = False
                else:
                    result.lineTo(p)
        result.closeSubpath()
        return result

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2 + 6)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 10, 14, 232))
        painter.drawEllipse(QRectF(center.x()-223, center.y()-223, 446, 446))

        valid = set(eligible_operations(self.files))
        # Draw eligible slices after disabled ones so raised pieces sit on top.
        indices = sorted(range(len(self._options)),
                         key=lambda i: (self._options[i].key in valid, self._pop[i]))
        for i in indices:
            spec = self._options[i]
            allowed = spec.key in valid
            energy = self._pop[i] if allowed else 0.0
            angle = math.radians(-90 + i * 360 / len(self._options))
            dx = math.cos(angle) * self.pop_distance(i)
            dy = math.sin(angle) * self.pop_distance(i)
            shifted = QPointF(center.x() + dx, center.y() + dy)
            petal = self._petal(i, shifted, boost=energy)
            if energy > .2:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, round(45 * energy)))
                painter.drawPath(petal.translated(0, 2+energy*3))
            if allowed:
                fill = QLinearGradient(shifted.x()-145, shifted.y()-160,
                                       shifted.x()+135, shifted.y()+170)
                base = QColor(PALETTE[i])
                fill.setColorAt(0, base.lighter(112 if energy > .55 else 105))
                fill.setColorAt(1, base.darker(110))
                painter.setBrush(QBrush(fill))
                edge = QColor("#100B0E")
                text_color = QColor("#170E13")
            else:
                painter.setBrush(QColor("#414047"))
                edge = QColor("#17171A")
                text_color = QColor("#939098")
            painter.setPen(QPen(edge, 4,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(petal)

            rx = shifted.x() + math.cos(angle) * 143
            ry = shifted.y() + math.sin(angle) * 143
            painter.setPen(text_color)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            a, b = self._labels.get(spec.key, (spec.label, ""))
            painter.drawText(QRectF(rx-38, ry-20, 76, 20),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, a)
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(rx-39, ry, 78, 17),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, b)

        # The central button always remains stationary, separate from petals.
        painter.setPen(QPen(QColor("#56525A"), 1.4))
        painter.setBrush(QColor("#121216"))
        painter.drawEllipse(QRectF(center.x()-68, center.y()-68, 136, 136))
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        painter.drawText(QRectF(center.x()-60, center.y()-37, 120, 25),
                         Qt.AlignmentFlag.AlignCenter, "FILE STUDIO")
        painter.setPen(QColor("#C5BCC1"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(center.x()-60, center.y()-11, 120, 49),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                         self.message)
        painter.end()

    def mouseMoveEvent(self, event):
        index = wheel_hit(event.position().x(), event.position().y(),
                          self.width(), self.height(), len(self._options))
        if index != self.highlight:
            self.highlight = index
            self._animate()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(event)
        self.activate_at(event.position().x(), event.position().y())

    def activate_at(self, x: float, y: float) -> str | None:
        index = wheel_hit(x, y, self.width(), self.height(), len(self._options))
        if index == -2:
            self._choose_dialog_open = True
            try:
                files, _ = QFileDialog.getOpenFileNames(
                    self, "Choose files for Mobius", str(Path.home()),
                    "Supported files (*.pdf *.doc *.docx *.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)")
            finally:
                self._choose_dialog_open = False
            if files:
                paths = [Path(p) for p in files]
                self.set_files(paths)
                self.files_chosen.emit(paths)
            return None
        if index == -1:
            self.hide()
            return None
        operation = self._options[index].key
        if operation not in eligible_operations(self.files):
            self.message = "Choose compatible files first"
            self.update()
            return None
        self.operation_requested.emit(operation)
        return operation

    def dragEnterEvent(self, event):
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()
                 if url.isLocalFile()]
        if eligible_files(paths):
            self.set_files(paths)
            self.files_chosen.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.mouse_hover_at(event.position().x(), event.position().y())
        if eligible_files(self.files):
            event.acceptProposedAction()
        else:
            event.ignore()

    def mouse_hover_at(self, x: float, y: float):
        self.highlight = wheel_hit(x, y, self.width(), self.height(), len(self._options))
        self._animate()
        self.update()

    def dropEvent(self, event):
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()
                 if url.isLocalFile()]
        if not eligible_files(paths):
            event.ignore()
            return
        self.set_files(paths)
        self.files_chosen.emit(paths)
        event.acceptProposedAction()
        self.drop_finished.emit()
        self.activate_at(event.position().x(), event.position().y())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)

    def hideEvent(self, event):
        self._animation.stop()
        self.highlight = -1
        self._pop = [0.0] * len(self._options)
        self.closed.emit()
        super().hideEvent(event)
