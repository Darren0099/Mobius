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
ACTIVE_ORANGE = "#FF812F"
HOVER_ORANGE = "#FF9F52"
INACTIVE_GRAPHITE = "#38383F"


def fan_piece_progress(progress: float, index: int, count: int = 9) -> float:
    """Staggered ease: first fan leaf opens, then each subsequent leaf follows."""
    if count < 1 or index < 0 or index >= count:
        return 0.0
    start = 0.57 * index / max(1, count - 1)
    x = max(0.0, min(1.0, (progress - start) / 0.43))
    return x * x * (3.0 - 2.0 * x)



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
        self._fan_progress = 1.0  # tests/direct clicks work before first show
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
        if self.isVisible():
            self._animation.start()
        self._animate()
        self.update()

    def show_centered(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        self.move(available.x() + (available.width() - self.width()) // 2,
                  available.y() + (available.height() - self.height()) // 2)
        new_open = not self.isVisible()
        if new_open:
            self._fan_progress = 0.0
            self._pop = [0.0] * len(self._options)
        self.show()
        self.raise_()
        self._animation.start()
        self.update()

    def _animate(self):
        """Unfold leaves one by one; then ease hovered eligible petal outward."""
        moving = False
        if self._fan_progress < 1.0:
            self._fan_progress = min(1.0, self._fan_progress + 0.026)
            moving = True

        valid = set(eligible_operations(self.files))
        for i, op in enumerate(self._options):
            target = (1.0 if i == self.highlight else 0.12) if op.key in valid else 0.0
            old = self._pop[i]
            new = old + (target - old) * .24
            if abs(target - new) < .01:
                new = target
            self._pop[i] = new
            moving = moving or abs(new - old) > .002

        if moving:
            self.update()
        elif self._animation.isActive():
            self._animation.stop()

    def pop_distance(self, index: int) -> float:
        return 16.0 * self._pop[index]

    @staticmethod
    def _petal(index: int, center: QPointF, count: int = 9,
               boost: float = 0.0, opening: float = 1.0) -> QPainterPath:
        """Rounded fan sector; opening moves it from the top to its final angle."""
        sweep = 360.0 / count
        # A folded Chinese fan begins as one narrow piece at the top.
        mid = -90.0 + index * sweep * opening
        aperture = max(.3, sweep - 4.8) * max(.014, opening)
        start = mid - aperture / 2
        stop = mid + aperture / 2
        inner = 76 + .35 * boost
        outer = 192 + 1.2 * boost
        shape = QPainterPath()
        first = True
        for radius, a1, a2 in ((outer, start, stop), (inner, stop, start)):
            for j in range(21):
                angle = math.radians(a1 + (a2 - a1) * j / 20)
                point = QPointF(center.x() + radius * math.cos(angle),
                                center.y() + radius * math.sin(angle))
                if first:
                    shape.moveTo(point)
                    first = False
                else:
                    shape.lineTo(point)
        shape.closeSubpath()
        return shape

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2 + 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#0B0B0E"))
        painter.drawEllipse(QRectF(center.x() - 207, center.y() - 207, 414, 414))

        enabled = set(eligible_operations(self.files))
        # Subtle radial ticks echo the reference without adding noisy cards.
        painter.setPen(QPen(QColor(255, 255, 255, 14), .9))
        for tick in range(72):
            angle = math.radians(tick * 5)
            x, y = math.cos(angle), math.sin(angle)
            painter.drawLine(
                QPointF(center.x() + x * 202, center.y() + y * 202),
                QPointF(center.x() + x * 206, center.y() + y * 206)
            )

        # A folded fan opens progressively clockwise, with each petal
        # following the previous one. Only compatible options are orange.
        for i, operation in enumerate(self._options):
            piece = fan_piece_progress(self._fan_progress, i, len(self._options))
            if piece <= .008:
                continue
            allowed = operation.key in enabled
            pop = self._pop[i] if allowed else 0.0
            mid = math.radians(-90 + i * 360 / len(self._options) * piece)
            shifted = QPointF(center.x() + math.cos(mid) * 16 * pop,
                              center.y() + math.sin(mid) * 16 * pop)
            sector = self._petal(i, shifted, len(self._options),
                                 boost=pop, opening=piece)

            painter.save()
            painter.setOpacity(min(1.0, .15 + .85 * piece))
            if allowed and pop > .45:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, int(64 * pop)))
                painter.drawPath(sector.translated(0, 2 + 3 * pop))
            if allowed:
                fill = QLinearGradient(shifted.x() - 115, shifted.y() - 130,
                                       shifted.x() + 130, shifted.y() + 140)
                fill.setColorAt(0, QColor(HOVER_ORANGE if pop > .6 else ACTIVE_ORANGE))
                fill.setColorAt(1, QColor("#DD622D"))
                painter.setBrush(QBrush(fill))
                painter.setPen(QPen(QColor("#1A1010"), 1.4,
                                    Qt.PenStyle.SolidLine,
                                    Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                ink = QColor("#1A1111")
            else:
                painter.setBrush(QColor(INACTIVE_GRAPHITE))
                painter.setPen(QPen(QColor("#626169"), .8))
                ink = QColor("#B7B3BE")
            painter.drawPath(sector)

            # Text is readable only after each leaf has unfolded.
            if piece > .56:
                angle = math.radians(-90 + i * 360 / len(self._options) * piece)
                x = shifted.x() + math.cos(angle) * 137
                y = shifted.y() + math.sin(angle) * 137
                painter.setOpacity(min(1.0, (piece - .56) / .35))
                painter.setPen(ink)
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
                first, second = self._labels.get(operation.key, (operation.label, ""))
                painter.drawText(QRectF(x - 41, y - 21, 82, 19),
                                 Qt.AlignmentFlag.AlignCenter, first)
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(QRectF(x - 41, y, 82, 19),
                                 Qt.AlignmentFlag.AlignCenter, second)
            painter.restore()

        # Quiet center hub with file name, not a giant dialog.
        painter.setPen(QPen(QColor("#514A4D"), 1.1))
        painter.setBrush(QColor("#101014"))
        painter.drawEllipse(QRectF(center.x() - 66, center.y() - 66, 132, 132))
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        painter.drawText(QRectF(center.x() - 58, center.y() - 39, 116, 24),
                         Qt.AlignmentFlag.AlignCenter, "FILE STUDIO")
        painter.setPen(QColor("#BEBBC3"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(center.x() - 57, center.y() - 13, 114, 48),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                         self.message)
        painter.end()

    def mouseMoveEvent(self, event):
        index = wheel_hit(event.position().x(), event.position().y(),
                          self.width(), self.height(), len(self._options))
        if index != self.highlight:
            self.highlight = index
            self._animation.start()
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
        self._animation.start()
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
        self._fan_progress = 1.0
        self.closed.emit()
        super().hideEvent(event)
