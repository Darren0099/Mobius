"""Swipeable, dark, per-feature accent carousel for the expanded Mobius island.

Each feature owns its own page; only the active page is on screen.
Arrow buttons, numbered dots, Shift+wheel and horizontal touchpad wheel
navigate without mixing File Studio into the music/timer UI.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QEasingCurve, QPoint, QParallelAnimationGroup, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class IslandCarousel(QWidget):
    page_changed = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pages: list[QWidget] = []
        self.labels: list[str] = []
        self.accents: list[str] = []
        self._index = -1
        self._group = None
        self._gesture_start = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        top = QHBoxLayout()
        top.setContentsMargins(4, 0, 4, 0)
        self.previous = QPushButton("‹")
        self.next_button = QPushButton("›")
        for b in (self.previous, self.next_button):
            b.setObjectName("carouselArrow")
            b.setFixedSize(38, 34)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.previous.clicked.connect(lambda: self.step(-1))
        self.next_button.clicked.connect(lambda: self.step(+1))
        self.title = QLabel("MOBIUS")
        self.title.setObjectName("carouselTitle")
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.index_label = QLabel("")
        self.index_label.setObjectName("carouselIndex")
        top.addWidget(self.previous)
        top.addWidget(self.title, 1)
        top.addWidget(self.index_label)
        top.addWidget(self.next_button)
        layout.addLayout(top)

        self.viewport = QFrame(self)
        self.viewport.setObjectName("carouselViewport")
        self.viewport.setMinimumHeight(363)
        self.viewport.setMaximumHeight(363)
        self.viewport.installEventFilter(self)
        layout.addWidget(self.viewport)

        self.dots_row = QHBoxLayout()
        self.dots_row.setSpacing(7)
        self.dots_row.addStretch(1)
        self.dots: list[QPushButton] = []
        self.dots_row.addStretch(1)
        layout.addLayout(self.dots_row)

    @property
    def current_index(self) -> int:
        return self._index

    def add_page(self, widget: QWidget, title: str, accent: str):
        widget.setParent(self.viewport)
        widget.setObjectName({
            "Music": "musicPage",
            "Lyrics": "lyricsPage",
            "Focus Timer": "focusPage",
            "Water Reminder": "waterPage",
            "File Studio": "filePage",
            "Assistant": "assistantPage",
        }.get(title, "carouselContent"))
        widget.hide()
        self.pages.append(widget)
        self.labels.append(title)
        self.accents.append(accent)
        idx = len(self.pages) - 1
        dot = QPushButton("●")
        dot.setObjectName("carouselDot")
        dot.setToolTip(title)
        dot.setFixedSize(23, 22)
        dot.setCursor(Qt.CursorShape.PointingHandCursor)
        dot.clicked.connect(lambda _=False, target=idx: self.go_to(target))
        self.dots_row.insertWidget(self.dots_row.count() - 1, dot)
        self.dots.append(dot)
        if self._index < 0:
            self._index = 0
            widget.show()
        self._update_navigation()
        self._position_current()

    def _position_current(self):
        if not self.pages or self._index < 0:
            return
        page = self.pages[self._index]
        page.setGeometry(0, 0, max(1, self.viewport.width()), self.viewport.height())

    def eventFilter(self, watched, event):
        if watched is self.viewport and event.type() == QEvent.Type.Resize:
            if self._group is None:
                self._position_current()
        return super().eventFilter(watched, event)

    def _update_navigation(self):
        if self._index < 0:
            return
        accent = self.accents[self._index]
        self.title.setText(self.labels[self._index])
        self.title.setStyleSheet(f"color: {accent}; font-size: 17px; font-weight: 800;")
        self.index_label.setText(f"{self._index + 1} / {len(self.pages)}")
        self.previous.setEnabled(self._index > 0)
        self.next_button.setEnabled(self._index < len(self.pages) - 1)
        for idx, dot in enumerate(self.dots):
            dot.setStyleSheet(
                f"color: {accent if idx == self._index else '#50545F'}; "
                "border: 0; background: transparent; font-size: 15px;"
            )
        self.page_changed.emit(self._index, self.labels[self._index])

    def _finish(self):
        if self._group is not None:
            group = self._group
            self._group = None
            if group.state() == QParallelAnimationGroup.State.Running:
                group.stop()
            group.deleteLater()
        for idx, widget in enumerate(self.pages):
            widget.setVisible(idx == self._index)
        self._position_current()

    def go_to(self, index: int, *, animated: bool = True):
        if not 0 <= index < len(self.pages):
            return
        if self._index == index:
            return
        self._finish()
        old_index = self._index
        self._index = index
        self._update_navigation()

        if not animated or not self.isVisible() or self.viewport.width() < 80:
            self._finish()
            return

        old = self.pages[old_index]
        incoming = self.pages[index]
        w, h = max(1, self.viewport.width()), self.viewport.height()
        direction = 1 if index > old_index else -1
        old.setGeometry(0, 0, w, h)
        incoming.setGeometry(direction * w, 0, w, h)
        old.show()
        incoming.show()
        incoming.raise_()
        group = QParallelAnimationGroup(self)
        for widget, start, end in (
            (old, QPoint(0, 0), QPoint(-direction * w, 0)),
            (incoming, QPoint(direction * w, 0), QPoint(0, 0)),
        ):
            animation = QPropertyAnimation(widget, b"pos", group)
            animation.setDuration(360)
            animation.setStartValue(start)
            animation.setEndValue(end)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            group.addAnimation(animation)
        self._group = group
        group.finished.connect(self._finish)
        group.start()

    def step(self, direction: int):
        self.go_to(self._index + direction)

    def wheelEvent(self, event):
        delta = event.angleDelta()
        value = delta.x() or (delta.y() if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 0)
        if value:
            self.step(-1 if value > 0 else +1)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._gesture_start = event.position()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._gesture_start is not None:
            movement = event.position().x() - self._gesture_start.x()
            if abs(movement) > 55:
                self.step(-1 if movement > 0 else 1)
        self._gesture_start = None
        super().mouseReleaseEvent(event)

    def stop(self):
        self._finish()
