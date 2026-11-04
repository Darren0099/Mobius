"""Mobius desktop interface: an animated top-of-screen drag-and-drop island."""
from __future__ import annotations

import math
import random
import re
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QObject, QPoint, QRect, Qt, QPropertyAnimation,
                             QThread, QTimer, Signal)
from PySide6.QtGui import (QBrush, QColor, QCursor, QDesktopServices, QFont, QGradient,
                            QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient)
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QGridLayout,
                                QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton, QScrollArea,
                                QSystemTrayIcon, QVBoxLayout, QWidget, QTabWidget, QLineEdit, QMessageBox, QInputDialog)
from PySide6.QtCore import QUrl

from .engine import BY_KEY, OPERATIONS, IMAGES, PDF, WORD, Result, convert, supported
from .assistant_core import execute, resolve_document, Intent
from .local_ai import interpret
from .desktop_visibility import foreground_class, visibility_mode, DESKTOP_CLASSES, left_mouse_down
from .hotkey import RecoveryHotkey
from .voice_commands import should_handle_utterance, normalized_utterance
from .voice_feedback import SpeechFeedback, english_confirmation
from .quick_deck import QuickDeck
from .vector_icons import icon, attach
from .carousel import IslandCarousel
from .ambient import GlanceController, read_windows_power, clock_label

COLORS = {
    'bg': '#141414', 'tile': '#222322', 'tile_hover': '#303328', 'line': '#454941',
    'text': '#FBF8EF', 'muted': '#B8BBAE', 'sky': '#C7FF10', 'accent': '#83AF3B'
}




def _paths(event) -> list[Path]:
    if not event.mimeData().hasUrls():
        return []
    paths = []
    for url in event.mimeData().urls():
        if url.isLocalFile():
            p = Path(url.toLocalFile())
            if p.is_file():
                paths.append(p)
    return paths


class Eyes(QWidget):
    """Reactive robot personality: cursor-following pupils, moods and drowsiness.

    At rest the avatar only redraws when its gaze/expression changes. Tired
    expressions come after inactivity; a moving cursor wakes it up.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(94, 26)
        self._base_mood = 'listening'
        self._flash_mood = None
        self._hold_until = 0.0
        self._expression = 'open'
        self._next_refresh = 0.0
        self._last_cursor = QCursor.pos()
        self._last_activity = time.monotonic()
        self._gaze = (0, 0)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(115)

    def set_mode(self, mood: str, *, temporary_ms: int = 0):
        if temporary_ms:
            self._flash_mood = mood
            self._hold_until = time.monotonic() + temporary_ms / 1000.0
        else:
            self._base_mood = mood
        self._expression = self._choose(mood)
        self._next_refresh = time.monotonic() + 0.5
        self.update()

    def _choose(self, mood: str) -> str:
        pools = {
            'listening': ['open', 'open', 'open', 'curious', 'wink', 'blink'],
            'thinking': ['squint', 'focus', 'focus', 'thinking', 'scan'],
            'happy': ['smile', 'smile', 'wink', 'open'],
            'warning': ['flat', 'squint', 'uneasy'],
            'sleepy': ['droop', 'droop', 'flat', 'blink', 'doze'],
            'dozing': ['doze', 'doze', 'flat'],
            'idle': ['open', 'wink', 'curious', 'blink'],
        }
        return random.choice(pools.get(mood, pools['idle']))

    def _tick(self):
        if not self.isVisible():
            return
        now = time.monotonic()
        cursor = QCursor.pos()
        moved = (abs(cursor.x() - self._last_cursor.x()) +
                 abs(cursor.y() - self._last_cursor.y())) > 7
        if moved:
            slept = now - self._last_activity
            self._last_activity = now
            self._last_cursor = cursor
            if slept > 120 and not self._flash_mood:
                self.set_mode('happy', temporary_ms=700)
        position = self.mapFromGlobal(cursor)
        gaze = (max(-4, min(4, int((position.x() - self.width()/2) / 55))),
                max(-2, min(2, int((position.y() - self.height()/2) / 55))))
        if gaze != self._gaze:
            self._gaze = gaze
            self.update()
        if self._flash_mood and now >= self._hold_until:
            self._flash_mood = None
            self._next_refresh = 0
        if now < self._next_refresh:
            return
        mood = self._flash_mood or self._base_mood
        if not self._flash_mood and mood in ('listening', 'idle'):
            idle_seconds = now - self._last_activity
            if idle_seconds >= 300:
                mood = 'dozing'
            elif idle_seconds >= 95:
                mood = 'sleepy'
        self._expression = self._choose(mood)
        self._next_refresh = now + (0.16 if self._expression == 'blink' else
                                    1.0 if mood == 'thinking' else 2.4)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        aura = QRadialGradient(self.width()/2, self.height()/2, 44)
        aura.setColorAt(0, QColor(255, 255, 255, 13))
        aura.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(aura))
        p.drawRoundedRect(self.rect(), 15, 15)

        color = QColor('#FAFAFC')  # white-green light from the reference
        p.setPen(QPen(color, 3.8, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        left, right = (26, 13), (68, 13)

        def circle(c, radius=7):
            x, y = c
            p.setBrush(QColor('#FFFFFF'))
            p.drawEllipse(QRect(x-radius, y-radius, radius*2, radius*2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            if self._expression not in ('blink', 'doze'):
                dx, dy = self._gaze
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor('#3A3A41'))
                p.drawEllipse(QRect(x+dx-2, y+dy-2, 4, 4))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(color, 3.8, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        def flat(c):
            x, y = c
            p.drawLine(x-9, y, x+9, y)

        def angle(c, leftward=True):
            x, y = c
            if leftward:
                p.drawLine(x-8, y-7, x+3, y)
                p.drawLine(x-8, y+7, x+3, y)
            else:
                p.drawLine(x+8, y-7, x-3, y)
                p.drawLine(x+8, y+7, x-3, y)

        def w(c):
            x,y=c
            p.drawLine(x-10,y-5,x-4,y+5)
            p.drawLine(x-4,y+5,x,y-1)
            p.drawLine(x,y-1,x+4,y+5)
            p.drawLine(x+4,y+5,x+10,y-5)

        expr = self._expression
        if expr == 'open':
            circle(left); circle(right)
        elif expr in ('blink', 'flat', 'doze'):
            flat(left); flat(right)
        elif expr == 'wink':
            circle(left, 7); angle(right, False)
        elif expr == 'curious':
            circle(left, 5); circle(right, 8)
        elif expr in ('focus', 'scan'):
            circle(left, 5); angle(right, False)
        elif expr == 'squint':
            angle(left); angle(right, False)
        elif expr == 'thinking':
            angle(left); circle(right, 6)
        elif expr == 'smile':
            w(left); w(right)
        elif expr == 'droop':
            p.drawArc(QRect(25, 9, 18, 18), 0, 180*16)
            p.drawArc(QRect(75, 9, 18, 18), 0, 180*16)
        elif expr == 'uneasy':
            flat(left); angle(right, False)
        else:
            circle(left); circle(right)
        p.end()


class DropHeader(QFrame):
    def __init__(self, app: 'MobiusWindow'):
        super().__init__(app)
        self.app = app
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName('dropHeader')

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.app.toggle()
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        self.app._drag_enter(event)

    def dragMoveEvent(self, event):
        self.app._drag_enter(event)

    def dropEvent(self, event):
        self.app._drop(event, None)


class ToolTile(QFrame):
    def __init__(self, window: 'MobiusWindow', key: str, index: int):
        super().__init__(window.panel)
        self.window = window
        self.key = key
        self.setObjectName('toolTile')
        self.setProperty('available', True)
        self.setProperty('selected', False)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(55)
        self.setToolTip('Klik untuk memilih file, atau drop file langsung di sini')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 4, 6, 4)
        layout.setSpacing(6)
        self.icon = QLabel()
        icon_name = ('image' if 'image' in key or 'img' in key else
                     'word' if 'word' in key else 'pdf' if 'pdf' in key else 'file')
        self.icon.setPixmap(icon(icon_name, 18).pixmap(18, 18))
        self.icon.setObjectName('toolIcon')
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.icon.setFixedSize(27, 31)
        layout.addWidget(self.icon)
        block = QVBoxLayout()
        block.setSpacing(3)
        self.name = QLabel(BY_KEY[key].label)
        self.name.setObjectName('toolTitle')
        self.name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.detail = QLabel(BY_KEY[key].subtitle)
        self.detail.setObjectName('toolSubtitle')
        self.detail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        block.addWidget(self.name)
        block.addWidget(self.detail)
        layout.addLayout(block, 1)
        self._highlight = False

    def set_available(self, available: bool):
        self.setProperty('available', available)
        self._refresh()

    def set_highlight(self, on: bool):
        self.setProperty('selected', on)
        self._refresh()

    def _refresh(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window.request_operation(self.key)
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        paths = _paths(event)
        if paths and all(p.suffix.lower() in BY_KEY[self.key].extensions for p in paths):
            event.acceptProposedAction()
            self.set_highlight(True)
        elif paths:
            event.acceptProposedAction()  # show a readable mismatch rather than silently reject

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        self.set_highlight(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.set_highlight(False)
        self.window._drop(event, self.key)


class ConvertWorker(QObject):
    success = Signal(object)
    failure = Signal(str)
    progress = Signal(str)
    done = Signal()

    def __init__(self, action, paths, output, fmt):
        super().__init__()
        self.action = action
        self.paths = paths
        self.output = output
        self.fmt = fmt

    def run(self):
        try:
            results = convert(self.action, self.paths, self.output, self.fmt, self.progress.emit)
            self.success.emit(results)
        except Exception as exc:
            self.failure.emit(f'{type(exc).__name__}: {exc}')
        finally:
            self.done.emit()


class InterpretWorker(QObject):
    ready = Signal(object)
    done = Signal()

    def __init__(self, command: str):
        super().__init__()
        self.command = command

    def run(self):
        try:
            self.ready.emit(interpret(self.command))
        except Exception as exc:
            self.ready.emit(Intent('error', f'Penafsiran gagal: {exc}'))
        finally:
            self.done.emit()


class MobiusWindow(QWidget):
    """Unified always-listening assistant and drag-drop file tool island."""
    COMPACT_W, COMPACT_H = 124, 38
    OPEN_W, OPEN_H = 408, 255  # small floating island; conversion tools scroll internally

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Mobius • Asisten Desktop Offline')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self._expanded = False
        self._busy = False
        self._drag_active = False
        self._temporary_until = time.monotonic() + 0.8  # do not cover browser tabs on launch
        self._drag_armed_at = None
        self._mouse_press_start = None
        self._voice_failed = False
        self._was_visible = True
        self._manual_override = False
        self._recoverable = False
        # Ordinary launches stay desktop-only. Debug mode pins the overlay
        # until the user can visually confirm the window is functioning.
        self._show_over_apps = False  # Never cover another app by default, even in debug mode
        self._edge_hover_since = None
        self._last_left_down = False
        self._expanded_at = 0.0
        self._hide_animating = False
        self._tip_mode = False
        self._last_foreground_class = None
        self._suppress_hover_until_leave = False
        self.pending: list[Path] = []
        self.destination = Path.home() / 'Documents' / 'Mobius'
        self.destination.mkdir(parents=True, exist_ok=True)
        self._last_results = None
        self.thread = self.worker = None
        self.voice_thread = self.voice_worker = None
        self._interpret_thread = self._interpret_worker = None
        self.listening_enabled = True  # always listening, with no wake word required
        self.feedback = SpeechFeedback()  # local English Windows SAPI, background thread
        self._last_voice_phrase = ''
        self._last_voice_at = 0.0
        self._quick_extra = 0
        self._compact_width = self.COMPACT_W
        self._island_status_visible = False
        self._voice_media_pending = None
        self._glance = GlanceController(start_now=time.monotonic())
        self._last_power = None
        self._power_label = ""
        self.setStyleSheet(self._style())

        self.header = DropHeader(self)
        self.header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.header.customContextMenuRequested.connect(self._show_context_menu)
        bar = QHBoxLayout(self.header)
        bar.setContentsMargins(5, 2, 5, 2)
        bar.setSpacing(5)
        bar.addStretch(1)
        self.eyes = Eyes(self.header)
        self.eyes.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        bar.addWidget(self.eyes, 0, Qt.AlignmentFlag.AlignCenter)
        self.island_status = QLabel('')
        self.island_status.setObjectName('islandStatus')
        self.island_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.island_status.setMinimumWidth(0)
        self.island_status.setMaximumWidth(180)
        self.island_status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.island_glance_icon = QLabel(self.header)
        self.island_glance_icon.setFixedSize(16, 19)
        self.island_glance_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.island_glance_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.island_glance_icon.hide()
        bar.addWidget(self.island_glance_icon)
        self.island_status.hide()
        bar.addWidget(self.island_status)
        bar.addStretch(1)

        self.panel = QFrame(self)
        self.panel.setObjectName('panel')
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(12, 5, 12, 6)
        panel_layout.setSpacing(4)
        self.assistant_page = QWidget(self.panel)
        assistant_layout = QVBoxLayout(self.assistant_page)
        assistant_layout.setContentsMargins(15, 12, 15, 10)
        assistant_layout.setSpacing(13)
        self.file_page = QWidget(self.panel)
        file_layout = QVBoxLayout(self.file_page)
        file_layout.setContentsMargins(10, 8, 10, 8)
        file_layout.setSpacing(10)
        self.intro = QLabel('Satu Mobius. Semua dalam satu tempat.')
        self.intro.setObjectName('assistantTitle')
        assistant_layout.addWidget(self.intro)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        self.assistant_status = QLabel('Menyiapkan mikrofon offline...')
        self.assistant_status.setObjectName('assistantStatus')
        top_row.addWidget(self.assistant_status, 1)
        self.voice_button = QPushButton('Matikan mikrofon')
        attach(self.voice_button, 'mic', size=15)
        self.voice_button.setObjectName('voiceButton')
        self.voice_button.clicked.connect(self.toggle_mic)
        top_row.addWidget(self.voice_button)
        self.folder_button = QPushButton('Folder hasil')
        attach(self.folder_button, 'folder', size=15)
        self.folder_button.setObjectName('secondaryButton')
        self.folder_button.clicked.connect(self.choose_folder)
        top_row.addWidget(self.folder_button)
        assistant_layout.addLayout(top_row)

        self.assistant_response = QLabel('Langsung ucapkan “buka kalkulator” atau “cari resep rendang di browser”. Tanpa wake word.')
        self.assistant_response.setObjectName('assistantResponse')
        self.assistant_response.setWordWrap(True)
        self.assistant_response.setMinimumHeight(48)
        assistant_layout.addWidget(self.assistant_response)
        # A unified quick-deck: music, lyrics, focus and water live above
        # the existing file tools, without switching assistant/studio modes.
        self.quick = QuickDeck(self.panel)
        self.quick.changed.connect(self._quick_changed)
        self.quick.alert.connect(self._quick_alert)
        self.quick.media.message.connect(self._spoken_media_success)
        self.quick.media.error.connect(self._spoken_media_error)
        self.quick.media.snapshot.connect(self._refresh_island_status)
        self.quick.hide()  # timers/media remain active; pages move into carousel
        title_row = QHBoxLayout()
        self.selection = QLabel('DROP FILE  /  PILIH KONVERSI')
        self.selection.setObjectName('sectionLabel')
        title_row.addWidget(self.selection)
        title_row.addStretch()
        self.selected_file = QLabel('Belum ada file')
        self.selected_file.setObjectName('selectedFile')
        title_row.addWidget(self.selected_file)
        file_layout.addLayout(title_row)
        grid = QGridLayout()
        grid.setContentsMargins(5, 4, 5, 4)
        grid.setSpacing(5)
        self.tiles = {}
        for i, spec in enumerate(OPERATIONS):
            tile = ToolTile(self, spec.key, i)
            self.tiles[spec.key] = tile
            grid.addWidget(tile, i // 2, i % 2)
        # Scroll only the conversion tools, keeping output controls visible.
        self.tools_inner = QWidget(self.file_page)
        self.tools_inner.setLayout(grid)
        self.tools_scroller = QScrollArea(self.file_page)
        self.tools_scroller.setObjectName('toolsScroller')
        self.tools_scroller.setWidgetResizable(True)
        self.tools_scroller.setFrameShape(QFrame.Shape.NoFrame)
        self.tools_scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tools_scroller.setWidget(self.tools_inner)
        file_layout.addWidget(self.tools_scroller, 1)
        bottom = QHBoxLayout()
        self.format_label = QLabel('OUTPUT')
        self.format_label.setObjectName('sectionLabel')
        bottom.addWidget(self.format_label)
        self.format_box = QComboBox()
        self.format_box.addItems(['PNG', 'JPG', 'WEBP'])
        self.format_box.setFixedWidth(78)
        bottom.addWidget(self.format_box)
        self.folder_note = QLabel(str(self.destination))
        self.folder_note.setObjectName('folderNote')
        bottom.addWidget(self.folder_note, 1)
        self.open_button = QPushButton('Buka hasil')
        attach(self.open_button, 'external', size=15, color='#161616')
        self.open_button.setObjectName('primaryButton')
        self.open_button.clicked.connect(self.open_folder)
        bottom.addWidget(self.open_button)
        file_layout.addLayout(bottom)
        self.note = QLabel('Semua konversi diproses di laptop. Tidak ada unggahan file.')
        self.note.setObjectName('statusText')
        file_layout.addWidget(self.note)
        assistant_layout.addStretch(1)
        file_layout.addStretch(1)

        self.carousel = IslandCarousel(self.panel)
        self.feature_pages = (
            ("Music", "#FAFAFC"),
            ("Lyrics", "#FAFAFC"),
            ("Focus Timer", "#FAFAFC"),
            ("Water Reminder", "#FAFAFC"),
        )
        for (label, accent), height in zip(self.feature_pages, (145, 198, 158, 230)):
            page = self.quick.pages.widget(0)
            if page is None:
                raise RuntimeError("Quick feature widget is missing")
            self.quick.pages.removeWidget(page)
            self.carousel.add_page(page, label, accent, content_height=height)
        self.carousel.add_page(self.file_page, "File Studio", "#FAFAFC",
                               content_height=238)
        self.carousel.add_page(self.assistant_page, "Assistant", "#FAFAFC",
                               content_height=186)
        self.carousel.page_changed.connect(self._page_selected)
        panel_layout.addWidget(self.carousel)
        self.quick.hide()

        self.panel.hide()

        self._animation = QPropertyAnimation(self, b'geometry', self)
        self._animation.setDuration(385)
        self._animation.setEasingCurve(QEasingCurve.Type.OutQuart)
        self._animation.finished.connect(self._on_morph_finished)
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self._auto_collapse)
        self._set_geometry(self.COMPACT_W, self.COMPACT_H)
        self._setup_tray()
        self._recovery_hotkey = RecoveryHotkey(self)
        self._recovery_hotkey.activated.connect(self.force_expand)
        self._recovery_hotkey.unavailable.connect(self._notify)
        self._recovery_hotkey.start()
        self._recoverable = self.tray is not None  # never hide without tray fallback
        self.visibility_timer = QTimer(self)
        self.visibility_timer.timeout.connect(self._sync_desktop_visibility)
        self.visibility_timer.start(45)  # detect ordinary external mouse clicks (~22 Hz)
        self._set_idle_eye()
        self._island_pulse = QTimer(self)
        self._island_pulse.setInterval(1000)
        self._island_pulse.timeout.connect(self._refresh_island_status)
        self._island_pulse.start()
        # Mic worker starts by itself, without opening a panel or needing a click.
        QTimer.singleShot(900, self.start_voice)

    def _style(self):
        """Quiet, monochrome interface: bright-white type on deep graphite."""
        return """
        QWidget {
            color: #FAFAFC; font-family: 'Segoe UI Variable', 'Segoe UI', Arial;
            font-size: 11px;
        }
        #dropHeader, #panel, #musicPage, #lyricsPage, #focusPage,
        #waterPage, #filePage, #assistantPage, #toolsScroller {
            background: transparent; border: none;
        }
        #carouselViewport {
            background: #0C0C0F; border: 1px solid #242428; border-radius: 13px;
        }
        #carouselArrow {
            background: #19191D; border: 1px solid #2B2B30; border-radius: 10px;
            color: #FAFAFC; font-size: 16px;
        }
        #carouselArrow:hover { background: #29292D; border-color: #4D4D52; }
        #carouselArrow:disabled { background: #121215; color: #5A5A62; }
        #carouselIndex { color: #B7B7BD; font-size: 10px; font-weight: 550; }
        #islandStatus { color: #FAFAFC; font-size: 12px; font-weight: 650; }
        #quickTrack { color: #FBFBFD; font-size: 12px; font-weight: 650; }
        #quickClock { color: #FFFFFF; font-size: 33px; font-weight: 700; }
        #quickHint { color: #ABABB2; font-size: 10px; }
        #lyricLeft {
            background: #141418; border: 1px solid #303035; border-radius: 11px;
        }
        #lyricLive { color: #FFFFFF; font-size: 12px; font-weight: 600; }
        #quickLyrics {
            background: #101013; color: #FAFAFC; border: 1px solid #29292E;
            border-radius: 9px;
        }
        #quickLyrics::item:selected { background: #35353C; color: #FFFFFF; }
        #quickButton, #secondaryButton {
            background: #202024; color: #F5F5F7; border: 1px solid #343439;
            border-radius: 9px;
        }
        #quickButton:hover, #secondaryButton:hover {
            background: #313135; border-color: #53535A;
        }
        #quickPrimary, #primaryButton {
            background: #F5F5F7; color: #111114; border: 1px solid #F5F5F7;
            border-radius: 9px; font-weight: 650;
        }
        #quickPrimary:hover, #primaryButton:hover { background: #E2E2E6; }
        QProgressBar {
            background: #1D1D21; color: #FFFFFF; border: 1px solid #333338;
            border-radius: 7px; text-align: center;
        }
        QProgressBar::chunk { background: #F6F6F8; border-radius: 7px; }
        #sectionLabel { color: #DADAE0; font-size: 10px; font-weight: 650; }
        #assistantTitle { color: #FCFCFD; font-size: 15px; font-weight: 700; }
        #assistantStatus { color: #D6D6DC; font-size: 10px; font-weight: 550; }
        #assistantResponse {
            background: #18181C; border: 1px solid #33333A; border-radius: 10px;
            color: #F1F1F4; font-size: 11px; padding: 9px;
        }
        #toolsScroller QScrollBar:vertical { background: #151519; width: 5px; }
        #toolsScroller QScrollBar::handle:vertical {
            background: #66666C; border-radius: 2px;
        }
        #toolTile {
            background: #17171A; border: 1px solid #2C2C32; border-radius: 9px;
        }
        #toolTile:hover, #toolTile[selected='true'] {
            background: #27272D; border: 1px solid #BDBDC5;
        }
        #toolTile[available='false'] { background: #111114; border-color: #242429; }
        #toolTile[available='false'] QLabel { color: #777780; }
        #toolIcon { background: transparent; border: none; }
        #toolTitle { color: #FAFAFC; font-size: 11px; font-weight: 650; }
        #toolSubtitle { color: #A6A6AF; font-size: 9px; }
        #selectedFile { color: #EDEDF0; font-size: 10px; }
        #folderNote { color: #A1A1AA; font-size: 9px; }
        #statusText { color: #B5B5BD; font-size: 10px; }
        QComboBox, QSpinBox {
            color: #FFFFFF; background: #1C1C21;
            border: 1px solid #44444C; padding: 4px; border-radius: 7px;
            selection-background-color: #44444C;
        }
        QSlider::groove:horizontal {
            background: #34343B; border: none; height: 3px; border-radius: 1px;
        }
        QSlider::handle:horizontal {
            background: #F7F7F9; width: 10px; margin: -4px 0; border-radius: 5px;
        }
        QPushButton {
            font-family: 'Segoe UI Variable', 'Segoe UI';
            padding: 6px 8px; font-size: 10px; font-weight: 600;
            border-radius: 8px;
        }
        #voiceButton {
            background: #222227; border: 1px solid #3F3F46;
            color: #F7F7F8; border-radius: 9px;
        }
        QMenu { background: #1B1B20; color: #FFFFFF; border: 1px solid #42424A; }
        QMenu::item:selected { background: #34343A; }
        """

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        asset = Path(__file__).resolve().parent.parent / 'assets' / 'mobius.ico'
        self.tray = QSystemTrayIcon(QIcon(str(asset)), self)
        self.tray.setToolTip('Mobius • selalu mendengarkan saat aktif')
        menu = QMenu()
        menu.addAction('Tampilkan Mobius  ·  Ctrl+Alt+M', self.force_expand)
        self.pin_action = menu.addAction('Indikator tipis saat aplikasi aktif')
        self.pin_action.setCheckable(True)
        self.pin_action.setChecked(self._show_over_apps)
        self.pin_action.toggled.connect(self.set_show_over_apps)
        self.mic_action = menu.addAction('Mikrofon aktif')
        self.mic_action.setCheckable(True)
        self.mic_action.setChecked(True)
        self.mic_action.toggled.connect(self.set_listening)
        menu.addAction('Uji perintah manual (opsional)', self.manual_command)
        menu.addAction('Buka folder hasil', self.open_folder)
        if sys.platform == 'win32':
            startup = menu.addAction('Jalankan saat login')
            startup.setCheckable(True)
            startup.setChecked(self._is_startup_enabled())
            startup.toggled.connect(self._set_startup_enabled)
        menu.addSeparator()
        menu.addAction('Keluar', QApplication.instance().quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.force_expand() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def set_show_over_apps(self, enabled):
        """Optional compact overlay; never force-enable it on startup."""
        self._show_over_apps = bool(enabled)
        # Apply the current foreground policy immediately.
        self._sync_desktop_visibility()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction('Buka Mobius', self.force_expand)
        pin = menu.addAction('Indikator tipis saat aplikasi aktif')
        pin.setCheckable(True)
        pin.setChecked(self._show_over_apps)
        pin.toggled.connect(self.set_show_over_apps)
        menu.addAction('Aktif/nonaktif mikrofon', self.toggle_mic)
        menu.addAction('Keluar', QApplication.instance().quit)
        menu.exec(QCursor.pos())

    def _startup_command(self):
        from pathlib import Path
        if getattr(sys, 'frozen', False):
            return f'"{sys.executable}"'
        script = Path(__file__).resolve().parent.parent / 'app.py'
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        return f'"{pythonw if pythonw.exists() else sys.executable}" "{script}"'

    def _is_startup_enabled(self):
        if sys.platform != 'win32':
            return False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as k:
                winreg.QueryValueEx(k, 'MobiusOffline')
                return True
        except OSError:
            return False

    def _set_startup_enabled(self, enabled):
        if sys.platform != 'win32':
            return
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE) as k:
                if enabled:
                    winreg.SetValueEx(k, 'MobiusOffline', 0, winreg.REG_SZ, self._startup_command())
                else:
                    try: winreg.DeleteValue(k, 'MobiusOffline')
                    except FileNotFoundError: pass
        except OSError as exc:
            self._notify(str(exc))

    def _screen(self):
        return QApplication.primaryScreen().availableGeometry()

    def _rect(self, width, height):
        screen = self._screen()
        width = min(width, screen.width() - 24)
        height = min(height, screen.height() - 18)
        return QRect(screen.x() + (screen.width() - width)//2, screen.y(), width, height)

    def _set_geometry(self, width, height):
        self.setGeometry(self._rect(width, height))

    def resizeEvent(self, event):
        self.header.setGeometry(4, 0, max(1, self.width()-8), 34)
        self.panel.setGeometry(7, 35, max(1, self.width()-14), max(0, self.height()-41))
        super().resizeEvent(event)

    def paintEvent(self, event):
        """Seamless graphite island: no neon glow or visible gradient band."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        radius = 20 if self._expanded else 17
        shape = QPainterPath()
        shape.moveTo(0, 0)
        shape.lineTo(w, 0)
        shape.lineTo(w, h-radius)
        shape.quadTo(w, h, w-radius, h)
        shape.lineTo(radius, h)
        shape.quadTo(0, h, 0, h-radius)
        shape.closeSubpath()
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor("#050507"))
        grad.setColorAt(1, QColor("#111114"))
        p.fillPath(shape, QBrush(grad))
        p.setPen(QPen(QColor(255, 255, 255, 15), 1))
        p.drawPath(shape)
        p.end()

    def _refresh_island_status(self, *_):
        """Cycle eyes → 10-second glance → eyes, without constant music text."""
        now = time.monotonic()
        power = read_windows_power()
        battery_and_time = f"{power.label}  {clock_label().split('  ·  ')[0]}"
        if (self._last_power is not None and power.plugged is not None
                and self._last_power.plugged is not None
                and power.plugged != self._last_power.plugged):
            # Charger plugged/unplugged takes priority over the periodic cycle.
            self._glance.show("battery", battery_and_time, now, power.accent)
        self._last_power = power

        options = [("clock", clock_label().split("  ·  ")[0], "#FAFAFC")]
        if power.percent is not None:
            options.append(("battery", battery_and_time, power.accent))

        focus = self.quick.store.focus
        if focus.deadline is not None:
            remain = focus.remaining()
            options.append(("focus", f"{remain // 60:02d}:{remain % 60:02d}  Focus", "#FAFAFC"))

        media = self.quick.current_media
        if media.get("available") and media.get("status") == "playing":
            line = ""
            if self.quick.lyrics:
                from .lyrics import active_line
                index = active_line(self.quick.lyrics, self.quick.estimated_position())
                if 0 <= index < len(self.quick.lyrics):
                    line = self.quick.lyrics[index][1]
            if not line:
                line = media.get("title") or "Playing music"
            options.append(("music", line, "#FAFAFC"))

        # Refresh text during the same 10-second glimpse without extending it:
        # the focus countdown and synchronized lyrics should remain live.
        if self._glance.kind not in ("eyes", "event") and now < self._glance.until:
            for kind, message, accent in options:
                if kind == self._glance.kind:
                    self._glance.message = message
                    self._glance.accent = accent
                    break
        self._glance.tick(now, options)
        glance_visible = bool(self._glance.message)
        line = self._glance.message
        # Fit the message rather than expanding every glance to a fixed width.
        display = self.island_status.fontMetrics().elidedText(
            line, Qt.TextElideMode.ElideRight, 174)
        self.island_status.setText(display)
        self.island_status.setStyleSheet(
            "color: #FAFAFC; font-family: 'Segoe UI Variable', 'Segoe UI'; "
            "font-size: 12px; font-weight: 650; background: transparent;"
        )
        if glance_visible:
            name = {
                "battery": "charging" if power.plugged else "battery",
                "clock": "clock", "focus": "timer", "music": "music",
                "event": "clock",
            }.get(self._glance.kind, "clock")
            self.island_glance_icon.setPixmap(icon(name, 15).pixmap(15, 15))
        self.island_glance_icon.setVisible(glance_visible)
        self.eyes.setVisible(self._expanded or not glance_visible)
        self.island_status.setVisible(glance_visible)

        text_width = self.island_status.fontMetrics().horizontalAdvance(display)
        target_width = min(240, max(150, text_width + 46)) if glance_visible else self.COMPACT_W
        if target_width != self._compact_width:
            self._compact_width = target_width
            if not self._expanded:
                self._animation.stop()
                self._animation.setStartValue(self.geometry())
                self._animation.setEndValue(self._rect(target_width, self.COMPACT_H))
                self._animation.start()

    def _expanded_target_height(self) -> int:
        # Header + carousel title/indicators + narrow internal margins.
        return 87 + self.carousel.current_height

    def _page_selected(self, index: int, title: str):
        """Smoothly adapt island height when a different carousel page opens."""
        if not self._expanded:
            return
        self._animation.stop()
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(
            self._rect(self.OPEN_W, self._expanded_target_height()))
        self._animation.start()

    def _quick_changed(self, opened: bool):
        # Compatibility with legacy QuickDeck signals; the carousel owns
        # expansion and page sizing in v0.8.
        if self._expanded:
            self._page_selected(self.carousel.current_index, "")

    def _spoken_media_success(self, message: str):
        action = self._voice_media_pending
        self._voice_media_pending = None
        if action:
            descriptions = {
                'play': 'Okay, music is playing.',
                'pause': 'Okay, music has been paused.',
                'toggle': 'Okay, playback has been toggled.',
                'next': 'Okay, next track.',
                'previous': 'Okay, previous track.',
            }
            self.feedback.speak(descriptions.get(action, "Okay, media updated."))

    def _spoken_media_error(self, message: str):
        if self._voice_media_pending:
            self._voice_media_pending = None
            self._notify(message, mood='warning')

    def _quick_alert(self, message: str):
        accent = "#FAFAFC"
        self._glance.show("event", message[:38], time.monotonic(), accent)
        self._refresh_island_status()
        self.eyes.set_mode('happy', temporary_ms=2200)
        self._notify(message)
        if self.tray is not None:
            self.tray.showMessage('Mobius', message[:170],
                                  QSystemTrayIcon.MessageIcon.Information, 3500)

    def _on_morph_finished(self):
        if self._hide_animating:
            self._hide_animating = False
            self.hide()
            self._animation.setDuration(285)
            self._animation.setEasingCurve(QEasingCurve.Type.OutQuart)

    def _start_hide_morph(self):
        """Shrink the compact island to the top edge before hiding entirely."""
        if self._hide_animating or not self.isVisible():
            return
        self._tip_mode = False
        self._hide_animating = True
        self._animation.stop()
        self._animation.setDuration(235)
        self._animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(self._rect(36, 6))
        self._animation.start()

    def _start_tip_morph(self):
        """Opt-in: leave a 36x6 hint, never a bar over Chrome's tabs."""
        if self._tip_mode and not self._hide_animating:
            return
        self._animation.stop()
        self._hide_animating = False
        self._tip_mode = True
        if not self.isVisible():
            self.setGeometry(self._rect(36, 6))
            self.show()
            return
        self._animation.setDuration(235)
        self._animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(self._rect(36, 6))
        self._animation.start()

    def _start_reveal_morph(self):
        """Reveal the compact eyes smoothly, including from the optional tip."""
        if self._expanded:
            self._hide_animating = False
            self._tip_mode = False
            self.show()
            return
        if self.isVisible() and not self._hide_animating and not self._tip_mode:
            return
        was_hidden = not self.isVisible()
        self._animation.stop()
        self._hide_animating = False
        self._tip_mode = False
        self._animation.setDuration(285)
        self._animation.setEasingCurve(QEasingCurve.Type.OutQuart)
        if was_hidden:
            self.setGeometry(self._rect(36, 6))
            self.show()
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(self._rect(self._compact_width, self.COMPACT_H))
        self._animation.start()

    def _dismiss_outside_click(self, cursor: QPoint, pressed: bool, now: float):
        """Poll global Windows left-button press; don't swallow the user's click."""
        fresh_press = pressed and not self._last_left_down
        self._last_left_down = pressed
        if not fresh_press or not self._expanded:
            return False
        if now - self._expanded_at < 0.25:
            return False
        if self.geometry().contains(cursor) or self._drag_active:
            return False
        # File dialogs and confirmation windows must stay interactive.
        if QApplication.activeModalWidget() is not None or QApplication.activePopupWidget() is not None:
            return False
        self._manual_override = False
        self._temporary_until = 0.0
        self.set_expanded(False)
        return True

    def set_expanded(self, expanded):
        if (self._expanded == expanded
                and self._animation.state() != QPropertyAnimation.State.Running):
            return
        self._expanded = expanded
        if expanded:
            self._expanded_at = time.monotonic()
        self._hide_animating = False
        self._tip_mode = False
        self._animation.stop()
        self._animation.setDuration(285)
        self._animation.setEasingCurve(QEasingCurve.Type.OutQuart)
        self.panel.setVisible(expanded)
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(
            self._rect(self.OPEN_W if expanded else self._compact_width,
                       self._expanded_target_height() if expanded else self.COMPACT_H))
        self._animation.start()
        self.update()

    def toggle(self):
        # Once opened intentionally, do not auto-hide it under the mouse.
        new_state = not self._expanded
        self._manual_override = new_state
        self._temporary_until = time.monotonic() + (3 if not new_state else 10)
        self.show()
        self.set_expanded(new_state)

    def force_expand(self):
        # Invoked via tray or Ctrl+Alt+M even while another app is active.
        self._manual_override = True
        self._temporary_until = time.monotonic() + 10
        self.show()
        self.set_expanded(True)
        self.raise_()
        self.activateWindow()

    def _sync_desktop_visibility(self):
        if sys.platform != 'win32':
            return
        now = time.monotonic()
        cls = foreground_class()
        desktop = cls.casefold() in DESKTOP_CLASSES
        screen = self._screen()
        cursor = QCursor.pos()
        pressed = left_mouse_down()
        own_window = bool(self.isActiveWindow())

        self._dismiss_outside_click(cursor, pressed, now)

        # A file picker or confirmation dialog is deliberate interaction.
        # Never hide its parent while the native/Qt modal is in use.
        if (QApplication.activeModalWidget() is not None
                or QApplication.activePopupWidget() is not None):
            self._last_foreground_class = cls
            return

        # Alt+Tab or switching to a new foreground application must clear
        # previously opened panels. An old panel_open flag is not permission
        # to cover browser tabs indefinitely.
        changed_foreground = (self._last_foreground_class is not None
                              and self._last_foreground_class != cls)
        self._last_foreground_class = cls
        if changed_foreground and not desktop and not own_window:
            if self._expanded and QApplication.activeModalWidget() is None:
                self._manual_override = False
                self._temporary_until = 0.0
                self.set_expanded(False)
            self._suppress_hover_until_leave = self.geometry().contains(cursor)

        if not self.geometry().contains(cursor):
            self._suppress_hover_until_leave = False

        top_edge = (abs(cursor.x() - (screen.x() + screen.width() / 2)) <= 105
                    and screen.y() <= cursor.y() <= screen.y() + 6)
        is_near_top = (abs(cursor.x() - (screen.x() + screen.width()/2)) < 155
                       and screen.y() <= cursor.y() <= screen.y()+70)
        if (top_edge and not pressed and not self._expanded
                and (not self.isVisible() or self._tip_mode)):
            if self._edge_hover_since is None:
                self._edge_hover_since = now
            elif now - self._edge_hover_since >= 0.7:
                self._temporary_until = now + 4.0
                self._edge_hover_since = None
                self._suppress_hover_until_leave = False
        else:
            self._edge_hover_since = None

        if pressed:
            if self._mouse_press_start is None:
                self._mouse_press_start = cursor
            moved = (abs(cursor.x() - self._mouse_press_start.x()) +
                     abs(cursor.y() - self._mouse_press_start.y())) > 26
            if is_near_top and moved and (not self.isVisible() or self._tip_mode):
                if self._drag_armed_at is None:
                    self._drag_armed_at = now
                elif now - self._drag_armed_at >= 0.26:
                    self._temporary_until = now + 2.4
            else:
                self._drag_armed_at = None
        else:
            self._drag_armed_at = None
            self._mouse_press_start = None
        if self._drag_active and pressed:
            self._temporary_until = now + 2.0

        pointer_interacting = (self.isVisible() and self.underMouse()
                               and not self._tip_mode
                               and not self._suppress_hover_until_leave)
        mode = visibility_mode(
            cls,
            temporary=(now < self._temporary_until),
            dragging_near_top=self._drag_active,
            own_foreground=own_window,
            panel_open=self._expanded,
            recovery_available=self._recoverable,
            pointer_over_island=pointer_interacting,
            pinned=self._show_over_apps,
        )

        if mode in ('hidden', 'tip'):
            if self._expanded and QApplication.activeModalWidget() is None:
                self._manual_override = False
                self._temporary_until = 0.0
                self.set_expanded(False)
            if mode == 'tip':
                self._start_tip_morph()
            elif self.isVisible():
                self._start_hide_morph()
        elif mode == 'compact':
            if self._expanded and not self._drag_active:
                self._manual_override = False
                self.set_expanded(False)
            if not self.isVisible() or self._tip_mode or self._hide_animating:
                self._start_reveal_morph()
        elif mode == 'expanded' and not self.isVisible():
            # Only explicit hover/shortcut/interaction can bring this forward.
            self._start_reveal_morph()

    def dragEnterEvent(self, event):
        self._drag_enter(event)

    def dragMoveEvent(self, event):
        self._drag_enter(event)

    def dragLeaveEvent(self, event):
        self._drag_active = False
        self._collapse_timer.start(1300)
        super().dragLeaveEvent(event)

    def _drag_enter(self, event):
        paths = _paths(event)
        if paths and all(p.suffix.lower() in PDF | WORD | IMAGES for p in paths):
            event.acceptProposedAction()
            self.carousel.go_to(4, animated=False)
            self._drag_active = True
            self._temporary_until = time.monotonic() + 8
            if not self._expanded:
                self.set_expanded(True)
        else:
            event.ignore()

    def dropEvent(self, event):
        self._drop(event, None)

    def _drop(self, event, action):
        paths = _paths(event)
        self._drag_active = False
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self.pending = paths
        self.carousel.go_to(4, animated=False)
        self._set_file_summary()
        self._temporary_until = time.monotonic() + 25
        self.set_expanded(True)
        if action:
            self.request_operation(action)
        else:
            self.note.setText('File diterima. Pilih alat konversi yang sesuai.')

    def _set_file_summary(self):
        self.selected_file.setText(self.pending[0].name[:36] if len(self.pending)==1 else
                                   (f'{len(self.pending)} file dipilih' if self.pending else 'Belum ada file'))
        for spec in OPERATIONS:
            self.tiles[spec.key].set_available(not self.pending or
                all(p.suffix.lower() in spec.extensions for p in self.pending))

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Folder hasil Mobius', str(self.destination))
        if folder:
            self.destination = Path(folder)
            self.folder_note.setText(str(self.destination))

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.destination)))

    def request_operation(self, key):
        if self._busy:
            self._notify('Konversi lain masih berjalan.')
            return
        spec = BY_KEY[key]
        paths = self.pending
        if not supported(paths, key):
            filt = ('PDF (*.pdf)' if spec.extensions == frozenset(PDF) else
                    'Word (*.docx *.doc)' if spec.extensions == frozenset(WORD) else
                    'Gambar (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)')
            chosen, _ = QFileDialog.getOpenFileNames(self, f'Pilih file untuk {spec.label}', str(Path.home()), filt)
            if not chosen:
                return
            paths = [Path(p) for p in chosen]
            self.pending = paths
            self._set_file_summary()
            if not supported(paths, key):
                self._notify('Format file tidak cocok atau jumlah file kurang.')
                return
        self._busy = True
        self.eyes.set_mode('thinking')
        self._notify(f'Memproses {len(paths)} file secara offline...')
        self.thread = QThread(self)
        self.worker = ConvertWorker(key, list(paths), self.destination, self.format_box.currentText())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress)
        self.worker.success.connect(self._success)
        self.worker.failure.connect(self._failure)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._finished)
        self.thread.start()

    def _progress(self, msg):
        self.note.setText(msg[:170])

    def _success(self, result):
        self._last_results = result
        self._notify(f'Selesai! {len(result.files)} file tersimpan di {self.destination}', mood='happy')
        if result.files:
            self.feedback.speak("Okay, your file conversion is complete.")

    def _failure(self, msg):
        self._notify('Gagal: ' + msg[:180], mood='warning')

    def _finished(self):
        self._busy = False
        self.thread = self.worker = None
        self._set_idle_eye()

    def _auto_collapse(self):
        if not self._manual_override and not self._drag_active and not self._busy and not self.underMouse():
            self.set_expanded(False)

    def _notify(self, message, mood: str | None = None):
        self.assistant_response.setText(message)
        self.note.setText(message[:145])
        if mood:
            self.eyes.set_mode(mood, temporary_ms=1800)
        if self.tray is not None and not self.isVisible():
            self.tray.showMessage('Mobius', message[:190], QSystemTrayIcon.MessageIcon.Information, 2700)

    def _set_idle_eye(self):
        if not self.listening_enabled:
            self.eyes.set_mode('sleepy')
        elif self._busy:
            self.eyes.set_mode('thinking')
        else:
            self.eyes.set_mode('listening')

    def manual_command(self):
        self.force_expand()
        command, ok = QInputDialog.getText(self, 'Uji Mobius', 'Perintah (opsional):')
        if ok and command.strip():
            self.on_phrase(command.strip(), require_wake=False)

    def on_phrase(self, phrase, *, require_wake=True):
        """Voice dispatch; no mouse interaction or AI tab required."""
        if require_wake:
            wake = re.match(r'^\s*(?:(?:hey|hei|hai|halo|oke)\s+)?(?:mobius|mobi\s+us)\b[,.:]?\s*', phrase, re.IGNORECASE)
            if not wake:
                return  # Ignore nearby conversations and TV audio.
        if self._interpret_thread is not None:
            return
        self.assistant_status.setText('Memahami perintah...')
        self.assistant_response.setText('Terdengar: ' + phrase[:190])
        self.eyes.set_mode('thinking')
        self._interpret_thread = QThread(self)
        self._interpret_worker = InterpretWorker(phrase)
        self._interpret_worker.moveToThread(self._interpret_thread)
        self._interpret_thread.started.connect(self._interpret_worker.run)
        self._interpret_worker.ready.connect(self._dispatch_intent)
        self._interpret_worker.done.connect(self._interpret_thread.quit)
        self._interpret_worker.done.connect(self._interpret_worker.deleteLater)
        self._interpret_thread.finished.connect(self._interpret_thread.deleteLater)
        self._interpret_thread.finished.connect(self._interpret_finished)
        self._interpret_thread.start()

    def _dispatch_intent(self, intent):
        if intent.kind == 'media':
            action = intent.args.get('action', '')
            if action not in ('play','pause','toggle','next','previous'):
                return
            self._voice_media_pending = action
            self.quick.media.control(action)
            self._notify('Mengirim perintah ke pemutar media Windows...')
            return
        if intent.kind == 'quick' and intent.args.get('page') == 'lyrics':
            self.force_expand()
            self.carousel.go_to(1)
            self._notify('Panel lirik dibuka. Pilih .lrc atau cari lirik online.')
            return
        if intent.kind == 'focus':
            action = intent.args.get('action')
            timer = self.quick.store.focus
            if action == 'start':
                minutes = intent.args.get('minutes')
                if minutes is not None and timer.deadline is None:
                    self.quick.focus_minutes.setValue(minutes)
                if timer.deadline is None:
                    timer.start()
                self.quick._render_focus()
                self._notify('Timer fokus berjalan.')
                self.feedback.speak('Okay, your focus timer has started.')
            elif action == 'pause':
                timer.pause()
                self.quick._render_focus()
                self._notify('Timer fokus dijeda.')
                self.feedback.speak('Okay, your focus timer is paused.')
            elif action == 'reset':
                timer.reset()
                self.quick._render_focus()
                self._notify('Timer fokus direset.')
                self.feedback.speak('Okay, focus timer reset.')
            self.quick.store.save()
            return
        if intent.kind == 'water':
            try:
                total = self.quick.store.water.add(intent.args.get('ml'))
                self.quick.store.save()
                self.quick._render_water()
                self._notify(f'Air tercatat. Total hari ini: {total} ml.')
                self.feedback.speak('Okay, your water intake has been logged.')
            except (ValueError, TypeError) as exc:
                self._notify(str(exc), mood='warning')
            return
        if intent.dangerous:
            self.force_expand()  # dangerous actions must have a visible confirmation
            answer = QMessageBox.question(self, 'Konfirmasi shutdown Windows',
                f'{intent.detail}\n\nSimpan dokumenmu sebelum melanjutkan. Eksekusi hanya setelah kamu menekan Ya.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                self._notify('Shutdown tidak dijadwalkan.')
                return
        if intent.kind == 'convert':
            if self._busy:
                self._notify('Konversi lain masih berjalan.')
                return
            try:
                path = resolve_document(intent.args['filename'], list(self.pending))
                if not supported([path], intent.args['operation']):
                    self._notify('File tidak cocok dengan format konversi.')
                    return
                self.pending = [path]
                self._set_file_summary()
                self.request_operation(intent.args['operation'])
            except Exception as exc:
                self._notify(str(exc))
            return
        if intent.kind == 'chat':
            self._notify(intent.detail)
            return
        try:
            result = execute(intent, dropped=list(self.pending), output=self.destination)
        except Exception as exc:
            self._notify(f'Perintah gagal: {exc}', mood='warning')
            return
        self._notify(result)
        spoken = english_confirmation(intent, result)
        if spoken:
            self.eyes.set_mode('happy', temporary_ms=1800)
            self.feedback.speak(spoken)

    def _interpret_finished(self):
        self._interpret_thread = self._interpret_worker = None
        self.assistant_status.setText('Mendengarkan' if self.listening_enabled else 'Mikrofon nonaktif')
        self._set_idle_eye()

    def set_listening(self, enabled):
        self.listening_enabled = enabled
        self.voice_button.setText('Matikan mikrofon' if enabled else 'Nyalakan mikrofon')
        if self.tray is not None and self.mic_action.isChecked() != enabled:
            self.mic_action.blockSignals(True)
            self.mic_action.setChecked(enabled)
            self.mic_action.blockSignals(False)
        if not enabled and self.voice_worker is not None:
            self.voice_worker.stop()
            self.assistant_status.setText('Mikrofon nonaktif')
        self._set_idle_eye()
        if enabled and self.voice_thread is None:
            self.start_voice()

    def toggle_mic(self):
        self.set_listening(not self.listening_enabled)

    def start_voice(self):
        if not self.listening_enabled or self.voice_thread is not None:
            return
        from .voice import VoiceWorker
        self.assistant_status.setText('Mendengarkan')
        self._voice_failed = False
        self.eyes.set_mode('listening')
        self.voice_thread = QThread(self)
        self.voice_worker = VoiceWorker(continuous=True, suppress_event=self.feedback.playing)
        self.voice_worker.moveToThread(self.voice_thread)
        self.voice_thread.started.connect(self.voice_worker.run)
        self.voice_worker.success.connect(self._voice_success)
        self.voice_worker.status.connect(self._voice_status)
        self.voice_worker.failure.connect(self._voice_failure)
        self.voice_worker.finished.connect(self.voice_thread.quit)
        self.voice_worker.finished.connect(self.voice_worker.deleteLater)
        self.voice_thread.finished.connect(self.voice_thread.deleteLater)
        self.voice_thread.finished.connect(self._voice_finished)
        self.voice_thread.start()

    def _voice_status(self, message):
        if self._interpret_thread is None:
            self.assistant_status.setText(message[:115])

    def _voice_success(self, phrase):
        # Never require "Mobius" before a spoken instruction. Ignore stray
        # ambient speech and repeated Whisper segments from the same utterance.
        if not should_handle_utterance(phrase):
            return
        normalized = normalized_utterance(phrase)
        now = time.monotonic()
        if normalized == self._last_voice_phrase and now - self._last_voice_at < 3.5:
            return
        self._last_voice_phrase = normalized
        self._last_voice_at = now
        self.on_phrase(phrase, require_wake=False)

    def _voice_failure(self, message):
        self._voice_failed = True
        self.assistant_status.setText('Setup suara diperlukan')
        self._notify(message, mood='warning')

    def _voice_finished(self):
        self.voice_thread = self.voice_worker = None
        if not self.listening_enabled:
            self.assistant_status.setText('Mikrofon nonaktif')
            self._set_idle_eye()
        elif not self._voice_failed:
            self._set_idle_eye()
            # A rapid OFF -> ON toggle must not permanently stop listening.
            QTimer.singleShot(400, self.start_voice)

    def stop_voice(self):
        self._island_pulse.stop()
        self.carousel.stop()
        self.quick.stop()
        self.feedback.stop()
        self._recovery_hotkey.stop()
        self.listening_enabled = False
        if self.voice_worker is not None:
            self.voice_worker.stop()
        if self.voice_thread is not None and self.voice_thread.isRunning():
            self.voice_thread.quit()
            self.voice_thread.wait(9000)
        if self._interpret_thread is not None and self._interpret_thread.isRunning():
            self._interpret_thread.quit()
            self._interpret_thread.wait(33000)

    def closeEvent(self, event):
        if self.tray is not None:
            self.hide()
            event.ignore()
        else:
            event.accept()


def start():
    # This sequence distinguishes a Qt-native hang from a hidden desktop overlay.
    from .startup_trace import trace_startup
    trace_startup('Before QApplication constructor')
    app = QApplication(sys.argv)
    trace_startup('QApplication constructed')
    app.setApplicationName('Mobius')
    app.setOrganizationName('Mobius')
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont('Urbanist', 10))
    trace_startup('Before MobiusWindow constructor')
    window = MobiusWindow()
    trace_startup('MobiusWindow constructed')
    window.show()
    trace_startup('Window.show() called')
    if os.environ.get('MOBIUS_DEBUG_VISIBLE') == '1':
        QTimer.singleShot(350, window.force_expand)
    app.aboutToQuit.connect(window.stop_voice)
    trace_startup('Entering Qt event loop')
    sys.exit(app.exec())
