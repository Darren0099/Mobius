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
                                QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton,
                                QSystemTrayIcon, QVBoxLayout, QWidget, QTabWidget, QLineEdit, QMessageBox, QInputDialog)
from PySide6.QtCore import QUrl

from .engine import BY_KEY, OPERATIONS, IMAGES, PDF, WORD, Result, convert, supported
from .assistant_core import execute, resolve_document, Intent
from .local_ai import interpret
from .desktop_visibility import foreground_class, should_show, left_mouse_down
from .hotkey import RecoveryHotkey

COLORS = {
    'bg': '#141414', 'tile': '#222322', 'tile_hover': '#303328', 'line': '#454941',
    'text': '#FBF8EF', 'muted': '#B8BBAE', 'sky': '#C7FF10', 'accent': '#83AF3B'
}

ICONS = ['▧', '◫', '▤', '◨', '⊞', '◧', '◉', '↻', '◇']


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
    """Animated robot eyes: the only visual content on the compact island."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(118, 30)
        self._base_mood = 'listening'
        self._flash_mood = None
        self._hold_until = 0.0
        self._expression = 'open'
        self._next_refresh = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(70)

    def set_mode(self, mood: str, *, temporary_ms: int = 0):
        if temporary_ms:
            self._flash_mood = mood
            self._hold_until = time.monotonic() + temporary_ms / 1000.0
        else:
            self._base_mood = mood
        self._expression = self._choose(mood)
        self._next_refresh = time.monotonic() + 0.7
        self.update()

    def _choose(self, mood: str):
        pools = {
            'listening': ['open', 'open', 'curious', 'focus', 'blink'],
            'thinking': ['squint', 'focus', 'focus', 'wink'],
            'happy': ['smile', 'smile', 'open'],
            'warning': ['flat', 'squint', 'focus'],
            'sleepy': ['flat', 'flat', 'blink'],
            'idle': ['open', 'wink', 'curious', 'blink'],
        }
        return random.choice(pools.get(mood, pools['idle']))

    def _tick(self):
        now = time.monotonic()
        if self._flash_mood and now >= self._hold_until:
            self._flash_mood = None
            self._next_refresh = 0.0
        if now < self._next_refresh:
            return
        mood = self._flash_mood or self._base_mood
        self._expression = self._choose(mood)
        self._next_refresh = now + (0.18 if self._expression == 'blink' else 1.1 if mood == 'thinking' else 2.2)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        glow = QRadialGradient(self.width() / 2, self.height() / 2, self.width() / 1.2)
        glow.setColorAt(0.0, QColor(199, 255, 16, 18))
        glow.setColorAt(1.0, QColor(199, 255, 16, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawRoundedRect(self.rect().adjusted(2, 1, -2, -1), 14, 14)
        p.setPen(QPen(QColor('#D7FE03'), 4.0, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        left, right = (34, 15), (84, 15)

        def circle(center, radius=8):
            x, y = center
            p.drawEllipse(QRect(x-radius, y-radius, radius*2, radius*2))

        def flat(center):
            x, y = center
            p.drawLine(x-8, y, x+8, y)

        def angle(center, inward=True):
            x, y = center
            if inward:
                p.drawLine(x-8, y-7, x+3, y)
                p.drawLine(x-8, y+7, x+3, y)
            else:
                p.drawLine(x+8, y-7, x-3, y)
                p.drawLine(x+8, y+7, x-3, y)

        def letter_w(center):
            x, y = center
            p.drawLine(x-10, y-5, x-4, y+5)
            p.drawLine(x-4, y+5, x, y-1)
            p.drawLine(x, y-1, x+4, y+5)
            p.drawLine(x+4, y+5, x+10, y-5)

        expr = self._expression
        if expr == 'open':
            circle(left); circle(right)
        elif expr == 'blink' or expr == 'flat':
            flat(left); flat(right)
        elif expr == 'wink':
            circle(left, 7); angle(right, inward=False)
        elif expr == 'curious':
            circle(left, 6); circle(right, 9)
        elif expr == 'squint':
            angle(left, inward=True); angle(right, inward=False)
        elif expr == 'focus':
            circle(left, 6); angle(right, inward=False)
        elif expr == 'smile':
            letter_w(left); letter_w(right)
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
        self.setFixedHeight(74)
        self.setToolTip('Klik untuk memilih file, atau drop file langsung di sini')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 10, 10, 10)
        layout.setSpacing(12)
        self.icon = QLabel(ICONS[index])
        self.icon.setObjectName('toolIcon')
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.icon.setFixedSize(34, 40)
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
    COMPACT_W, COMPACT_H = 170, 46
    OPEN_W, OPEN_H = 838, 485

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
        self._temporary_until = time.monotonic() + 12.0  # brief first-run preview; not a permanent overlay
        self._drag_armed_at = None
        self._mouse_press_start = None
        self._voice_failed = False
        self._was_visible = True
        self._manual_override = False
        self._recoverable = False
        self._show_over_apps = False  # defaults to desktop-only as requested
        self._edge_hover_since = None
        self.pending: list[Path] = []
        self.destination = Path.home() / 'Documents' / 'Mobius'
        self.destination.mkdir(parents=True, exist_ok=True)
        self._last_results = None
        self.thread = self.worker = None
        self.voice_thread = self.voice_worker = None
        self._interpret_thread = self._interpret_worker = None
        self.listening_enabled = True  # explicitly requested always-on voice
        self.setStyleSheet(self._style())

        self.header = DropHeader(self)
        self.header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.header.customContextMenuRequested.connect(self._show_context_menu)
        bar = QHBoxLayout(self.header)
        bar.setContentsMargins(10, 6, 10, 6)
        bar.setSpacing(0)
        bar.addStretch(1)
        self.eyes = Eyes(self.header)
        self.eyes.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        bar.addWidget(self.eyes, 0, Qt.AlignmentFlag.AlignCenter)
        bar.addStretch(1)

        self.panel = QFrame(self)
        self.panel.setObjectName('panel')
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(18, 4, 18, 12)
        panel_layout.setSpacing(12)
        self.intro = QLabel('Satu Mobius. Semua dalam satu tempat.')
        self.intro.setObjectName('assistantTitle')
        panel_layout.addWidget(self.intro)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        self.assistant_status = QLabel('●  Menyiapkan mikrofon offline...')
        self.assistant_status.setObjectName('assistantStatus')
        top_row.addWidget(self.assistant_status, 1)
        self.voice_button = QPushButton('◉  Matikan mikrofon')
        self.voice_button.setObjectName('voiceButton')
        self.voice_button.clicked.connect(self.toggle_mic)
        top_row.addWidget(self.voice_button)
        self.folder_button = QPushButton('▤  Folder hasil')
        self.folder_button.setObjectName('secondaryButton')
        self.folder_button.clicked.connect(self.choose_folder)
        top_row.addWidget(self.folder_button)
        panel_layout.addLayout(top_row)

        self.assistant_response = QLabel('Cukup ucapkan “Mobius” diikuti perintahmu. Tidak perlu membuka mode apa pun.')
        self.assistant_response.setObjectName('assistantResponse')
        self.assistant_response.setWordWrap(True)
        self.assistant_response.setMinimumHeight(48)
        panel_layout.addWidget(self.assistant_response)
        title_row = QHBoxLayout()
        self.selection = QLabel('DROP FILE  /  PILIH KONVERSI')
        self.selection.setObjectName('sectionLabel')
        title_row.addWidget(self.selection)
        title_row.addStretch()
        self.selected_file = QLabel('Belum ada file')
        self.selected_file.setObjectName('selectedFile')
        title_row.addWidget(self.selected_file)
        panel_layout.addLayout(title_row)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.tiles = {}
        for i, spec in enumerate(OPERATIONS):
            tile = ToolTile(self, spec.key, i)
            self.tiles[spec.key] = tile
            grid.addWidget(tile, i // 3, i % 3)
        panel_layout.addLayout(grid)
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
        self.open_button = QPushButton('↗  Buka hasil')
        self.open_button.setObjectName('primaryButton')
        self.open_button.clicked.connect(self.open_folder)
        bottom.addWidget(self.open_button)
        panel_layout.addLayout(bottom)
        self.note = QLabel('Semua konversi diproses di laptop. Tidak ada unggahan file.')
        self.note.setObjectName('statusText')
        panel_layout.addWidget(self.note)
        self.panel.hide()

        self._animation = QPropertyAnimation(self, b'geometry', self)
        self._animation.setDuration(260)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
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
        self.visibility_timer.start(260)
        self._set_idle_eye()
        # Mic worker starts by itself, without opening a panel or needing a click.
        QTimer.singleShot(900, self.start_voice)

    def _style(self):
        return """
        QWidget { color: #FBF8EF; font-family: 'Urbanist', 'Segoe UI', Arial; }
        #dropHeader, #panel { background: transparent; }
        #sectionLabel { color: #C7FF10; font-weight: 800; }
        #assistantTitle { font-size: 20px; font-weight: 800; color: #F5F5F8; }
        #assistantStatus { font-size: 11px; color: #C7FF10; font-weight: 700; }
        #assistantResponse { background: #2D3426; border: 1px solid #668B35; border-radius: 12px; font-size: 12px; color: #F5F5F8; padding: 10px; }
        #toolTile { background: #222322; border: 1px solid #41433C; border-radius: 13px; }
        #toolTile:hover, #toolTile[selected='true'] { background: #303625; border: 1px solid #C7FF10; }
        #toolTile[available='false'] { background: #171817; border-color: #2B2E28; }
        #toolTile[available='false'] QLabel { color: #737870; }
        #toolIcon { background: #373E28; border-radius: 10px; font-size: 22px; font-weight: bold; color: #C7FF10; }
        #toolTitle { font-weight: 750; font-size: 12px; color: #F5F5F8; }
        #toolSubtitle { font-size: 10px; color: #ADB5A1; }
        #selectedFile { font-size: 11px; color: #FBF8EF; }
        #folderNote { color: #A0A795; font-size: 10px; }
        #statusText { color: #C7FF10; font-size: 11px; }
        QComboBox { background: #252724; border: 1px solid #444840; padding: 7px; border-radius: 9px; color: white; }
        QPushButton { padding: 8px 11px; font-size: 11px; font-weight: 700; border-radius: 10px; }
        #secondaryButton { background: #2A3025; border: 1px solid #525C43; color: #F5F5F8; }
        #primaryButton { background: #C7FF10; border: 1px solid #C7FF10; color: #141414; }
        #voiceButton { background: #353C2B; border: 1px solid #83AF3B; color: #C7FF10; }
        QMenu { background: #222322; color: #FBF8EF; border: 1px solid #515C35; }
        QMenu::item:selected { background: #465329; }
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
        self.pin_action = menu.addAction('Sematkan island di semua aplikasi')
        self.pin_action.setCheckable(True)
        self.pin_action.setChecked(False)
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
        if self._show_over_apps:
            self.show()
        else:
            self._sync_desktop_visibility()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction('Buka Mobius', self.force_expand)
        pin = menu.addAction('Sematkan island di semua aplikasi')
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
        self.header.setGeometry(6, 2, self.width()-12, 38)
        self.panel.setGeometry(10, 42, self.width()-20, max(0, self.height()-50))
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Negative top inset makes the compact island appear attached to the screen edge.
        r = self.rect().adjusted(3, -10, -3, -3)
        body = QPainterPath()
        body.addRoundedRect(r, 24 if self._expanded else 21, 24 if self._expanded else 21)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor('#161616'))
        grad.setColorAt(1, QColor('#090909'))
        p.fillPath(body, QBrush(grad))
        p.setPen(QPen(QColor(255, 255, 255, 22), 1.0))
        p.drawPath(body)
        p.end()

    def set_expanded(self, expanded):
        if self._expanded == expanded and self._animation.state() != QPropertyAnimation.State.Running:
            return
        self._expanded = expanded
        self._animation.stop()
        self.panel.setVisible(expanded)
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(self._rect(self.OPEN_W if expanded else self.COMPACT_W,
                                               self.OPEN_H if expanded else self.COMPACT_H))
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
        screen = self._screen()
        cursor = QCursor.pos()
        is_near_top = (abs(cursor.x() - (screen.x() + screen.width()/2)) < 155 and
                       screen.y() <= cursor.y() <= screen.y()+70)
        pressed = left_mouse_down()
        # Deliberate access when a browser is active: dwell at the very top
        # screen edge (not the normal tabs/title bar). Avoid instant popup.
        top_edge = (abs(cursor.x() - (screen.x() + screen.width() / 2)) <= 105
                    and screen.y() <= cursor.y() <= screen.y() + 6)
        if top_edge and not pressed and not self.isVisible():
            if self._edge_hover_since is None:
                self._edge_hover_since = now
            elif now - self._edge_hover_since >= 0.7:
                self._temporary_until = now + 5.0
                self._edge_hover_since = None
        else:
            self._edge_hover_since = None
        if pressed:
            if self._mouse_press_start is None:
                self._mouse_press_start = cursor
            moved = (abs(cursor.x() - self._mouse_press_start.x()) +
                     abs(cursor.y() - self._mouse_press_start.y())) > 26
            # Hold and move while dragging a file: reveal a temporary target.
            # A normal stationary click on a browser tab does not reveal Mobius.
            if is_near_top and moved and not self.isVisible():
                if self._drag_armed_at is None:
                    self._drag_armed_at = now
                elif now - self._drag_armed_at >= .26:
                    self._temporary_until = now + 2.4
            else:
                self._drag_armed_at = None
        else:
            self._drag_armed_at = None
            self._mouse_press_start = None
        if self._drag_active and pressed:
            self._temporary_until = now + 2
        own_window = bool(self.isActiveWindow())
        visible = should_show(cls, temporary=(now < self._temporary_until),
                              dragging_near_top=self._drag_active, own_foreground=own_window,
                              panel_open=self._expanded or self._manual_override,
                              recovery_available=self._recoverable,
                              pointer_over_island=(self.isVisible() and self.underMouse()),
                              pinned=self._show_over_apps)
        if visible and not self.isVisible():
            self.show()
        elif not visible and self.isVisible():
            self.hide()  # never collapse an intentionally opened panel here

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
        self.assistant_status.setText('●  MEMAHAMI PERINTAH...')
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
        self._notify(intent.detail if intent.kind == 'chat' else execute(intent, dropped=list(self.pending), output=self.destination))

    def _interpret_finished(self):
        self._interpret_thread = self._interpret_worker = None
        self.assistant_status.setText('●  MENDENGARKAN' if self.listening_enabled else '○  MIKROFON NONAKTIF')
        self._set_idle_eye()

    def set_listening(self, enabled):
        self.listening_enabled = enabled
        self.voice_button.setText('◉  Matikan mikrofon' if enabled else '◎  Nyalakan mikrofon')
        if self.tray is not None and self.mic_action.isChecked() != enabled:
            self.mic_action.blockSignals(True)
            self.mic_action.setChecked(enabled)
            self.mic_action.blockSignals(False)
        if not enabled and self.voice_worker is not None:
            self.voice_worker.stop()
            self.assistant_status.setText('○  MIKROFON NONAKTIF')
        self._set_idle_eye()
        if enabled and self.voice_thread is None:
            self.start_voice()

    def toggle_mic(self):
        self.set_listening(not self.listening_enabled)

    def start_voice(self):
        if not self.listening_enabled or self.voice_thread is not None:
            return
        from .voice import VoiceWorker
        self.assistant_status.setText('●  MENDENGARKAN · WAKE WORD: MOBIUS')
        self._voice_failed = False
        self.eyes.set_mode('listening')
        self.voice_thread = QThread(self)
        self.voice_worker = VoiceWorker(continuous=True)
        self.voice_worker.moveToThread(self.voice_thread)
        self.voice_thread.started.connect(self.voice_worker.run)
        self.voice_worker.success.connect(self._voice_success)
        self.voice_worker.failure.connect(self._voice_failure)
        self.voice_worker.finished.connect(self.voice_thread.quit)
        self.voice_worker.finished.connect(self.voice_worker.deleteLater)
        self.voice_thread.finished.connect(self.voice_thread.deleteLater)
        self.voice_thread.finished.connect(self._voice_finished)
        self.voice_thread.start()

    def _voice_success(self, phrase):
        self.on_phrase(phrase)

    def _voice_failure(self, message):
        self._voice_failed = True
        self.assistant_status.setText('●  SETUP SUARA DIPERLUKAN')
        self._notify(message, mood='warning')

    def _voice_finished(self):
        self.voice_thread = self.voice_worker = None
        if not self.listening_enabled:
            self.assistant_status.setText('○  MIKROFON NONAKTIF')
            self._set_idle_eye()
        elif not self._voice_failed:
            self._set_idle_eye()
            # A rapid OFF -> ON toggle must not permanently stop listening.
            QTimer.singleShot(400, self.start_voice)

    def stop_voice(self):
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
    app = QApplication(sys.argv)
    app.setApplicationName('Mobius')
    app.setOrganizationName('Mobius')
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont('Urbanist', 10))
    window = MobiusWindow()
    window.show()
    app.aboutToQuit.connect(window.stop_voice)
    sys.exit(app.exec())