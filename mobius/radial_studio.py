"""Independent, keyboard-dismissable radial File Studio.

Nine native Qt-painted radial petals follow the supplied design references.
The top-notch is not resized. File operations still call the existing offline
converter and reject incompatible extensions before work starts.
"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget

from .engine import BY_KEY, OPERATIONS, IMAGES, PDF, WORD, supported

SUPPORTED = frozenset(IMAGES | PDF | WORD)
PALETTE = (
    "#DAD9DC", "#ADADB2", "#78777E", "#C3C0C5", "#96959B",
    "#DFDDE0", "#ABA9AF", "#706F76", "#BAB8BE",
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
    if radius < 79 or radius > 206:
        return -1
    # First petal occupies 40 degrees centered on 12 o'clock.
    clockwise_from_top = (math.degrees(math.atan2(dy, dx)) + 90) % 360
    return int((clockwise_from_top + 180 / count) // (360 / count)) % count


class RadialStudio(QWidget):
    """A standalone center-screen, monochrome radial menu for file conversion."""

    operation_requested = Signal(str)
    files_chosen = Signal(object)
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
        self.setFixedSize(500, 500)
        self.files: list[Path] = []
        self.highlight = -1
        self.message = "Drop a file or select one to begin"
        self._options = list(OPERATIONS)
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
        self.update()

    def show_centered(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        self.move(available.x() + (available.width() - self.width()) // 2,
                  available.y() + (available.height() - self.height()) // 2)
        self.show()
        self.raise_()
        self.update()

    @staticmethod
    def _petal(index: int, center: QPointF, count: int = 9) -> QPainterPath:
        sweep = 360 / count
        mid = -90 + index * sweep
        start, stop = mid - sweep / 2 + 2.1, mid + sweep / 2 - 2.1
        result = QPainterPath()
        for radius, a1, a2, steps in ((202, start, stop, 16), (80, stop, start, 16)):
            for j in range(steps + 1):
                angle = math.radians(a1 + (a2 - a1) * j / steps)
                p = QPointF(center.x() + radius * math.cos(angle),
                            center.y() + radius * math.sin(angle))
                if result.isEmpty():
                    result.moveTo(p)
                else:
                    result.lineTo(p)
        result.closeSubpath()
        return result

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2 + 6)

        # Floating matte disc, not an opaque rectangular app window.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 10, 13, 224))
        painter.drawEllipse(QRectF(center.x() - 224, center.y() - 224, 448, 448))

        valid = set(eligible_operations(self.files))
        for i, op in enumerate(self._options):
            allowed = op.key in valid
            hovered = i == self.highlight and allowed
            fill = QColor(PALETTE[i]) if allowed else QColor("#35353B")
            if hovered:
                fill = QColor("#F9F8FA")
            contour = self._petal(i, center)
            painter.setBrush(fill)
            painter.setPen(QPen(QColor("#111116"), 5,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(contour)

            angle = math.radians(-90 + i * 360 / len(self._options))
            text_radius = 140
            x = center.x() + math.cos(angle) * text_radius
            y = center.y() + math.sin(angle) * text_radius
            rect = QRectF(x - 38, y - 24, 76, 48)
            painter.setPen(QColor("#17171B") if allowed else QColor("#AAAAAF"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            first, second = self._labels.get(op.key, (op.label, ""))
            painter.drawText(QRectF(rect.x(), rect.y(), rect.width(), 21),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, first)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
            painter.drawText(QRectF(rect.x(), rect.y() + 21, rect.width(), 22),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, second)

        painter.setBrush(QColor("#111115"))
        painter.setPen(QPen(QColor("#49494E"), 1.2))
        painter.drawEllipse(QRectF(center.x() - 68, center.y() - 68, 136, 136))
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        painter.drawText(QRectF(center.x() - 63, center.y() - 37, 126, 23),
                         Qt.AlignmentFlag.AlignCenter, "FILE STUDIO")
        painter.setPen(QColor("#C3C3CA"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(center.x() - 60, center.y() - 8, 120, 46),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                         self.message)
        painter.end()

    def mouseMoveEvent(self, event):
        index = wheel_hit(event.position().x(), event.position().y(),
                          self.width(), self.height(), len(self._options))
        if index != self.highlight:
            self.highlight = index
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(event)
        self.activate_at(event.position().x(), event.position().y())

    def activate_at(self, x: float, y: float) -> str | None:
        index = wheel_hit(x, y, self.width(), self.height(), len(self._options))
        if index == -2:
            files, _ = QFileDialog.getOpenFileNames(
                self, "Choose files for Mobius", str(Path.home()),
                "Supported files (*.pdf *.doc *.docx *.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)")
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
        self.activate_at(event.position().x(), event.position().y())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)

    def hideEvent(self, event):
        self.closed.emit()
        super().hideEvent(event)
