"""Mobius desktop interface: an animated top-of-screen drag-and-drop island."""
from __future__ import annotations

import math
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
                                QSystemTrayIcon, QVBoxLayout, QWidget, QTabWidget, QLineEdit, QMessageBox)
from PySide6.QtCore import QUrl

from .engine import BY_KEY, OPERATIONS, IMAGES, PDF, WORD, Result, convert, supported
from .assistant_core import parse_command, execute, resolve_document
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
    """Two subtle, cursor-following eyes with a short occasional blink."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(47, 35)
        self._begin = time.monotonic()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(50)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#292C22'))
        p.drawRoundedRect(0, 1, 47, 32, 14, 14)
        elapsed = (time.monotonic() - self._begin) % 5.7
        blink = max(0.09, min(1.0, abs(elapsed - 4.65) / .12))
        cursor = self.mapFromGlobal(QCursor.pos())
        dx = max(-3.0, min(3.0, (cursor.x() - 23) / 60))
        dy = max(-2.4, min(2.4, (cursor.y() - 17) / 65))
        for cx in (17.2, 30.0):
            gradient = QRadialGradient(cx, 15, 15)
            gradient.setColorAt(0, QColor('#EAFFB3'))
            gradient.setColorAt(1, QColor('#C7FF10'))
            p.setBrush(QBrush(gradient))
            p.drawEllipse(QRect(int(cx - 5), int(15 - 6 * blink), 10, max(2, int(12 * blink))))
            if blink > .33:
                p.setBrush(QColor('#141414'))
                p.drawEllipse(QRect(int(cx - 2 + dx), int(13 + dy), 4, max(2, int(5 * blink))))
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


class IntentWorker(QObject):
    ready = Signal(object)
    done = Signal()
    def __init__(self, phrase):
        super().__init__()
        self.phrase = phrase
    def run(self):
        try:
            self.ready.emit(interpret(self.phrase))
        except Exception as exc:
            from .assistant_core import Intent
            self.ready.emit(Intent('error', str(exc)))
        finally:
            self.done.emit()

class MobiusWindow(QWidget):
    COMPACT_W = 238
    COMPACT_H = 54
    OPEN_W = 868
    OPEN_H = 610

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Mobius • Offline Desktop Assistant')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._expanded = False
        self._busy = False
        self._drag_active = False
        self.pending: list[Path] = []
        self.thread = None
        self.worker = None
        self.destination = Path.home() / 'Documents' / 'Mobius'
        self.destination.mkdir(parents=True, exist_ok=True)
        self._last_results: Result | None = None
        self.setStyleSheet(self._style())

        self.header = DropHeader(self)
        self.header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.header.customContextMenuRequested.connect(self._show_context_menu)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(18, 6, 17, 5)
        header_layout.setSpacing(9)
        self.eyes = Eyes(self.header)
        self.eyes.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        header_layout.addWidget(self.eyes)
        text_stack = QVBoxLayout()
        text_stack.setSpacing(1)
        self.brand = QLabel('M O B I U S')
        self.brand.setObjectName('brand')
        self.brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.under_brand = QLabel('OFFLINE  /  DESKTOP ASSISTANT')
        self.under_brand.setObjectName('underBrand')
        self.under_brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_stack.addWidget(self.brand)
        text_stack.addWidget(self.under_brand)
        header_layout.addLayout(text_stack)
        self.top_help = QLabel('FILE STUDIO     /     AI-FREE ASSISTANT')
        self.top_help.setObjectName('topHelp')
        self.top_help.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.top_help.hide()
        header_layout.addWidget(self.top_help)
        header_layout.addStretch(1)
        self.status_dot = QLabel('●')
        self.status_dot.setObjectName('statusDot')
        self.status_dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        header_layout.addWidget(self.status_dot)
        self.chevron = QLabel('⌄')
        self.chevron.setObjectName('chevron')
        self.chevron.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        header_layout.addWidget(self.chevron)

        self.panel = QFrame(self)
        self.panel.setObjectName('panel')
        self.panel.setAcceptDrops(True)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(15, 0, 15, 10)
        panel_layout.setSpacing(8)

        self.tabs = QTabWidget(self.panel)
        self.tabs.setObjectName('mainTabs')
        panel_layout.addWidget(self.tabs)

        self.studio_tab = QWidget()
        self.studio_tab.setObjectName('studioTab')
        self.tabs.addTab(self.studio_tab, '▦  FILE STUDIO')
        studio = QVBoxLayout(self.studio_tab)
        studio.setContentsMargins(5, 12, 5, 5)
        studio.setSpacing(11)
        caption = QHBoxLayout()
        self.selection = QLabel('DROP FILE KE ALAT YANG DIBUTUHKAN')
        self.selection.setObjectName('sectionLabel')
        caption.addWidget(self.selection)
        caption.addStretch()
        self.selected_file = QLabel('Belum ada file')
        self.selected_file.setObjectName('selectedFile')
        caption.addWidget(self.selected_file)
        studio.addLayout(caption)

        grid = QGridLayout()
        grid.setSpacing(9)
        self.tiles = {}
        for i, spec in enumerate(OPERATIONS):
            tile = ToolTile(self, spec.key, i)
            self.tiles[spec.key] = tile
            grid.addWidget(tile, i // 3, i % 3)
        studio.addLayout(grid)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        self.format_label = QLabel('FORMAT OUTPUT')
        self.format_label.setObjectName('footerLabel')
        foot.addWidget(self.format_label)
        self.format_box = QComboBox()
        self.format_box.addItems(['PNG', 'JPG', 'WEBP'])
        self.format_box.setToolTip('Format untuk PDF → Gambar dan Ubah Format')
        self.format_box.setFixedWidth(78)
        foot.addWidget(self.format_box)
        self.folder_button = QPushButton('▤  Folder output')
        self.folder_button.setObjectName('secondaryButton')
        self.folder_button.clicked.connect(self.choose_folder)
        foot.addWidget(self.folder_button)
        self.folder_note = QLabel(str(self.destination))
        self.folder_note.setObjectName('folderNote')
        self.folder_note.setToolTip(str(self.destination))
        foot.addWidget(self.folder_note, 1)
        self.open_button = QPushButton('↗  Buka hasil')
        self.open_button.setObjectName('primaryButton')
        self.open_button.clicked.connect(self.open_folder)
        foot.addWidget(self.open_button)
        studio.addLayout(foot)
        self.note = QLabel('Siap · semua file diproses secara lokal, tanpa upload.')
        self.note.setObjectName('statusText')
        self.note.setWordWrap(False)
        studio.addWidget(self.note)
        studio.addStretch(1)

        self.assistant_tab = QWidget()
        self.assistant_tab.setObjectName('assistantTab')
        self.tabs.addTab(self.assistant_tab, '✦  MOBIUS ASSISTANT')
        self.tabs.tabBar().hide()
        assistant = QVBoxLayout(self.assistant_tab)
        assistant.setContentsMargins(14, 12, 14, 10)
        assistant.setSpacing(12)

        intro = QLabel('Your laptop, one command away.')
        intro.setObjectName('assistantTitle')
        assistant.addWidget(intro)
        tagline = QLabel('Ketik perintah atau gunakan mikrofon. Semua perintah diproses di laptopmu.')
        tagline.setObjectName('assistantSubtitle')
        assistant.addWidget(tagline)

        command_row = QHBoxLayout()
        command_row.setSpacing(9)
        self.command_input = QLineEdit()
        self.command_input.setObjectName('commandInput')
        self.command_input.setPlaceholderText('Mobius, tolong buka notepad dan kalkulator…')
        self.command_input.returnPressed.connect(self.handle_command)
        command_row.addWidget(self.command_input, 1)
        self.command_button = QPushButton('↗  Jalankan')
        self.command_button.setObjectName('primaryButton')
        self.command_button.clicked.connect(self.handle_command)
        command_row.addWidget(self.command_button)
        self.voice_button = QPushButton('◉  Bicara (7s)')
        self.voice_button.setObjectName('voiceButton')
        self.voice_button.setToolTip('Mulai merekam satu perintah selama 7 detik. Offline setelah model suara diinstal.')
        self.voice_button.clicked.connect(self.start_voice)
        command_row.addWidget(self.voice_button)
        self.handsfree_button = QPushButton('◎  Hands-free OFF')
        self.handsfree_button.setObjectName('voiceButton')
        self.handsfree_button.setToolTip('Aktifkan mikrofon lokal terus-menerus. Hanya perintah yang diawali Mobius akan dijalankan.')
        self.handsfree_button.clicked.connect(self.toggle_handsfree)
        command_row.addWidget(self.handsfree_button)
        assistant.addLayout(command_row)

        self.assistant_status = QLabel('●  SIAP MENERIMA PERINTAH')
        self.assistant_status.setObjectName('assistantStatus')
        assistant.addWidget(self.assistant_status)
        prompt_title = QLabel('COBA PERINTAH')
        prompt_title.setObjectName('sectionLabel')
        assistant.addWidget(prompt_title)
        prompts = [
            'Mobius buka notepad dan kalkulator',
            'Mobius ubah PDF laporan menjadi img',
            'Mobius matikan laptop dalam 10 menit',
            'Mobius batalkan shutdown',
            'Mobius putar musik acak',
            'Mobius buka browser dan cari tutorial Python',
        ]
        examples = QGridLayout()
        examples.setSpacing(8)
        for i, prompt in enumerate(prompts):
            b = QPushButton(('0' + str(i + 1) + '   ') + prompt.removeprefix('Mobius '))
            b.setObjectName('exampleButton')
            b.setToolTip(prompt)
            b.clicked.connect(lambda _=False, q=prompt: self.fill_command(q))
            examples.addWidget(b, i // 2, i % 2)
        assistant.addLayout(examples)
        assistant.addStretch(1)
        self.assistant_response = QLabel('Mobius siap. Perintah shutdown selalu meminta konfirmasi.')
        self.assistant_response.setWordWrap(True)
        self.assistant_response.setObjectName('assistantResponse')
        self.assistant_response.setMinimumHeight(45)
        assistant.addWidget(self.assistant_response)
        hint = QLabel('VOICE SETUP  ·  Jalankan install-voice-windows.bat satu kali, lalu bisa offline.')
        hint.setObjectName('voiceHint')
        assistant.addWidget(hint)
        # One unified visible panel: the assistant status and controls join file tools.
        studio.insertWidget(0, self.assistant_status)
        studio.insertWidget(1, self.assistant_response)
        studio.insertWidget(2, self.handsfree_button)
        self.tabs.setCurrentWidget(self.studio_tab)

        self.voice_thread = None
        self.voice_worker = None
        self.handsfree_active = False
        self._intent_thread = None
        self._intent_worker = None
        self._reveal_until = time.monotonic() + 8  # startup preview
        self._drag_origin = None
        self._manual_override = False
        self.panel.hide()

        self._animation = QPropertyAnimation(self, b'geometry', self)
        self._animation.setDuration(280)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._animation_done)
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self._auto_collapse)
        self._set_geometry(self.COMPACT_W, self.COMPACT_H)
        self._setup_tray()
        self._recovery_hotkey = RecoveryHotkey(self)
        self._recovery_hotkey.activated.connect(self.force_expand)
        self._recovery_hotkey.start()
        self._desktop_timer = QTimer(self)
        self._desktop_timer.timeout.connect(self._sync_visibility)
        self._desktop_timer.start(250)
        QTimer.singleShot(1100, self.toggle_handsfree)  # always listen after startup

    def _sync_visibility(self):
        if sys.platform != 'win32':
            return
        now = time.monotonic()
        screen = QApplication.primaryScreen().availableGeometry()
        pos = QCursor.pos()
        held = left_mouse_down()
        near_top = abs(pos.x() - screen.center().x()) < 155 and screen.y() <= pos.y() < screen.y()+75
        if held:
            if self._drag_origin is None:
                self._drag_origin = pos
            moved = abs(pos.x()-self._drag_origin.x()) + abs(pos.y()-self._drag_origin.y()) > 28
            if moved and near_top:
                self._reveal_until = now + 2.5
        else:
            self._drag_origin = None
        if self._drag_active and held:
            self._reveal_until = now + 3
        show = should_show(foreground_class(), temporary=now < self._reveal_until,
                           dragging_near_top=self._drag_active,
                           own_foreground=self.isActiveWindow(),
                           panel_open=self._expanded or self._manual_override,
                           recovery_available=self.tray is not None or sys.platform == 'win32')
        if show and not self.isVisible():
            self.show()
        elif not show and self.isVisible():
            self.hide()  # expanded panels never disappear without user action

    def _style(self):
        return """
        QWidget { color: #FBF8EF; font-family: 'Urbanist', 'Segoe UI', Arial; }
        #dropHeader, #panel, #studioTab, #assistantTab { background: transparent; }
        #brand { font-size: 14px; font-weight: 800; color: #FBF8EF; }
        #underBrand { font-size: 8px; font-weight: 700; color: #C7FF10; }
        #topHelp { font-size: 10px; color: #B7BBAA; margin-left: 12px; }
        #statusDot { font-size: 11px; color: #C7FF10; }
        #chevron { font-size: 18px; color: #C7FF10; padding-left: 3px; }
        #sectionLabel { font-size: 10px; font-weight: 800; color: #C7FF10; }
        #selectedFile { font-size: 11px; color: #FBF8EF; }
        #toolTile { background: #222322; border: 1px solid #41433C; border-radius: 16px; }
        #toolTile:hover, #toolTile[selected='true'] { background: #303625; border: 1px solid #C7FF10; }
        #toolTile[available='false'] { background: #171817; border-color: #2B2E28; }
        #toolTile[available='false'] QLabel { color: #737870; }
        #toolIcon { background: #373E28; border-radius: 10px; font-size: 22px; font-weight: bold; color: #C7FF10; }
        #toolTitle { font-weight: 750; font-size: 13px; color: #F5F5F8; }
        #toolSubtitle { font-size: 10px; color: #ADB5A1; }
        #footerLabel { font-size: 10px; font-weight: 750; color: #B5BCAA; }
        #folderNote { color: #A0A795; font-size: 10px; }
        #statusText { color: #C7FF10; font-size: 11px; }
        QComboBox { background: #252724; border: 1px solid #444840; padding: 8px; border-radius: 9px; color: white; font-size: 11px; }
        QComboBox QAbstractItemView { background: #242624; color: #F5F5F8; }
        QPushButton { padding: 9px 12px; font-size: 11px; font-weight: 700; border-radius: 10px; }
        #secondaryButton { background: #2A3025; border: 1px solid #525C43; color: #F5F5F8; }
        #secondaryButton:hover { background: #3E4634; }
        #primaryButton { background: #C7FF10; border: 1px solid #C7FF10; color: #141414; }
        #primaryButton:hover { background: #D7FE03; }
        QTabWidget::pane { border: none; }
        QTabBar::tab { background: #222322; color: #B8BBAE; padding: 10px 18px; margin-right: 6px; border-radius: 11px; font-weight: 750; }
        QTabBar::tab:selected { background: #C7FF10; color: #141414; }
        #assistantTitle { font-size: 25px; font-weight: 800; color: #F5F5F8; }
        #assistantSubtitle { font-size: 12px; color: #B7BEAB; }
        #commandInput { background: #FBF8EF; color: #141414; border: 2px solid #C7FF10; border-radius: 11px; padding: 13px; font-size: 12px; selection-background-color: #83AF3B; }
        #voiceButton { background: #353C2B; border: 1px solid #83AF3B; color: #C7FF10; }
        #voiceButton:hover { background: #414D2A; }
        #assistantStatus { font-size: 11px; color: #C7FF10; font-weight: bold; padding-top: 4px; }
        #exampleButton { background: #242624; border: 1px solid #41433C; color: #F5F5F8; text-align: left; padding: 14px; }
        #exampleButton:hover { border-color: #C7FF10; }
        #assistantResponse { background: #2D3426; border: 1px solid #668B35; border-radius: 12px; font-size: 12px; color: #F5F5F8; padding: 12px; }
        #voiceHint { color: #8FA280; font-size: 10px; }
        QMenu { background: #222322; color: #FBF8EF; border: 1px solid #515C35; }
        QMenu::item:selected { background: #465329; }
        """

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        icon_path = Path(__file__).resolve().parent.parent / 'assets' / 'mobius.ico'
        icon = QIcon(str(icon_path))
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip('Mobius • Offline Desktop Assistant')
        menu = QMenu()
        open_action = menu.addAction('Buka Mobius')
        open_action.triggered.connect(self.force_expand)
        folder_action = menu.addAction('Buka folder output')
        folder_action.triggered.connect(self.open_folder)
        if sys.platform == 'win32':
            startup = menu.addAction('Buka otomatis saat login Windows')
            startup.setCheckable(True)
            startup.setChecked(self._is_startup_enabled())
            startup.toggled.connect(self._set_startup_enabled)
        menu.addAction('Tampilkan Mobius', self.force_expand)
        menu.addSeparator()
        quit_action = menu.addAction('Keluar dari Mobius')
        quit_action.triggered.connect(QApplication.instance().quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.force_expand() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction('Buka Mobius', self.force_expand)
        menu.addAction('Folder hasil', self.open_folder)
        menu.addAction('Buka Assistant', self.open_assistant)
        menu.addSeparator()
        menu.addAction('Keluar', QApplication.instance().quit)
        sender = self.sender()
        if isinstance(sender, QWidget):
            menu.exec(sender.mapToGlobal(pos))
        else:
            menu.exec(self.mapToGlobal(pos))

    def _startup_command(self):
        if getattr(sys, 'frozen', False):
            return f'"{sys.executable}"'
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        interpreter = pythonw if pythonw.exists() else Path(sys.executable)
        app_path = Path(__file__).resolve().parent.parent / 'app.py'
        return f'"{interpreter}" "{app_path}"'

    def _is_startup_enabled(self):
        if sys.platform != 'win32':
            return False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
                current, _ = winreg.QueryValueEx(key, 'MobiusOffline')
                return current == self._startup_command()
        except (OSError, ImportError):
            return False

    def _set_startup_enabled(self, enabled):
        if sys.platform != 'win32':
            return
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Software\Microsoft\Windows\CurrentVersion\Run',
                                0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, 'MobiusOffline', 0, winreg.REG_SZ, self._startup_command())
                else:
                    try: winreg.DeleteValue(key, 'MobiusOffline')
                    except FileNotFoundError: pass
            self.note.setText('Pengaturan startup Windows berhasil diperbarui.')
        except OSError as exc:
            self.note.setText(f'Tidak dapat mengubah startup Windows: {exc}')

    def _screen(self):
        return QApplication.primaryScreen().availableGeometry()

    def _rect(self, width, height):
        screen = self._screen()
        width = min(width, screen.width() - 24)
        height = min(height, screen.height() - 14)
        return QRect(screen.x() + (screen.width() - width) // 2, screen.y() + 6, width, height)

    def _set_geometry(self, width, height):
        self.setGeometry(self._rect(width, height))

    def resizeEvent(self, event):
        self.header.setGeometry(6, 5, self.width() - 12, 50)
        self.panel.setGeometry(11, 61, self.width() - 22, max(0, self.height() - 74))
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(4, 3, -4, -4)
        # Soft shadow and violet / cyan trace are drawn inside the transparent window.
        shadow = QPainterPath()
        shadow.addRoundedRect(r.adjusted(-2, -1, 2, 2), 22, 22)
        p.fillPath(shadow, QColor(0, 0, 0, 74))
        body = QPainterPath()
        body.addRoundedRect(r, 19 if not self._expanded else 22, 19 if not self._expanded else 22)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0, QColor('#181A17'))
        grad.setColorAt(.65, QColor('#141414'))
        grad.setColorAt(1, QColor('#20231B'))
        p.fillPath(body, QBrush(grad))
        pen_grad = QLinearGradient(0, 0, self.width(), 0)
        pen_grad.setColorAt(0, QColor('#83AF3B'))
        pen_grad.setColorAt(.55, QColor('#43552A'))
        pen_grad.setColorAt(1, QColor('#C7FF10'))
        p.setPen(QPen(QBrush(pen_grad), 1.3))
        p.drawPath(body)
        if self._expanded:
            p.setPen(QPen(QColor('#3E462E'), 1))
            p.drawLine(24, 59, self.width() - 24, 59)
        p.end()

    def set_expanded(self, expanded: bool):
        if expanded == self._expanded and self._animation.state() != QPropertyAnimation.State.Running:
            return
        self._expanded = expanded
        self._collapse_timer.stop()
        self._animation.stop()
        if expanded:
            self.panel.show()
            self.top_help.show()
            self.chevron.setText('⌃')
        else:
            self.panel.hide()
            self.top_help.hide()
            self.chevron.setText('⌄')
        target = self._rect(self.OPEN_W if expanded else self.COMPACT_W,
                            self.OPEN_H if expanded else self.COMPACT_H)
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(target)
        self._animation.start()
        self.raise_()
        self.update()

    def _animation_done(self):
        self.update()

    def toggle(self):
        expanded = not self._expanded
        self._manual_override = expanded
        self._reveal_until = time.monotonic() + (10 if expanded else 3)
        self.show()
        self.set_expanded(expanded)

    def force_expand(self):
        self._manual_override = True
        self._reveal_until = time.monotonic() + 10
        self.show()
        self.set_expanded(True)
        self.raise_()
        self.activateWindow()

    def dragEnterEvent(self, event):
        self._drag_enter(event)

    def dragMoveEvent(self, event):
        self._drag_enter(event)

    def dragLeaveEvent(self, event):
        self._drag_active = False
        self._collapse_timer.start(1600)
        super().dragLeaveEvent(event)

    def _drag_enter(self, event):
        paths = _paths(event)
        if paths and all(p.suffix.lower() in (PDF | WORD | IMAGES) for p in paths):
            event.acceptProposedAction()
            self._drag_active = True
            self._reveal_until = time.monotonic() + 15
            self._collapse_timer.stop()
            if not self._expanded:
                self.set_expanded(True)
        else:
            event.ignore()

    def dropEvent(self, event):
        self._drop(event, None)

    def _drop(self, event, action: str | None):
        files = _paths(event)
        self._drag_active = False
        if not files:
            event.ignore()
            return
        event.acceptProposedAction()
        self.pending = files
        self.tabs.setCurrentWidget(self.studio_tab)
        self._set_file_summary()
        self.set_expanded(True)
        self._auto_select()
        if action:
            self.request_operation(action)
        else:
            self.note.setText('File diterima. Pilih salah satu kartu untuk mulai konversi.')

    def _set_file_summary(self):
        if not self.pending:
            self.selected_file.setText('Tidak ada file dipilih')
        elif len(self.pending) == 1:
            name = self.pending[0].name
            self.selected_file.setText((name[:33] + '…') if len(name) > 34 else name)
        else:
            self.selected_file.setText(f'{len(self.pending)} file dipilih')
        for spec in OPERATIONS:
            # For merge, single PDF can be completed through the file selection dialog.
            can_use = bool(self.pending) and all(p.suffix.lower() in spec.extensions for p in self.pending)
            self.tiles[spec.key].set_available(not self.pending or can_use)

    def _auto_select(self):
        if not self.pending:
            return
        first = self.pending[0].suffix.lower()
        if first in IMAGES:
            self.note.setText('Gambar terdeteksi. Drop di “Gambar → PDF” atau “Ubah Format”.')
        elif first in WORD:
            self.note.setText('Dokumen Word terdeteksi. Drop di “Word → PDF”.')
        elif first in PDF:
            self.note.setText('PDF terdeteksi. Pilih alat PDF yang ingin kamu pakai.')

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Pilih folder hasil Mobius', str(self.destination))
        if folder:
            self.destination = Path(folder)
            self.folder_note.setText(str(self.destination))
            self.folder_note.setToolTip(str(self.destination))

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.destination)))

    def request_operation(self, key: str):
        if self._busy:
            self.note.setText('Masih memproses file. Selesaikan proses ini terlebih dahulu.')
            return
        spec = BY_KEY[key]
        paths = self.pending
        if not supported(paths, key):
            filter_text = ('PDF (*.pdf)' if spec.extensions == frozenset(PDF) else
                           'Word (*.docx *.doc)' if spec.extensions == frozenset(WORD) else
                           'Gambar (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)')
            title = ('Pilih minimal dua PDF untuk digabung' if key == 'merge_pdf' else
                     f'Pilih file untuk {spec.label}')
            chosen, _ = QFileDialog.getOpenFileNames(self, title, str(Path.home()), filter_text)
            if not chosen:
                self.note.setText('Tidak ada file dipilih. Drag file atau pilih lewat dialog.')
                return
            paths = [Path(p) for p in chosen]
            self.pending = paths
            self._set_file_summary()
            if not supported(paths, key):
                self.note.setText('Format tidak cocok atau perlu minimal dua file PDF.')
                return
        self._busy = True
        self.note.setText('Memulai konversi offline…')
        self.status_dot.setStyleSheet('color: #83AF3B')
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

    def _progress(self, message):
        self.note.setText('⟳  ' + message[:118])

    def _success(self, result: Result):
        self._last_results = result
        msg = f'✓  Selesai! {len(result.files)} file disimpan di folder output.'
        if result.warnings:
            msg += '  Catatan: ' + result.warnings[0][:95]
        self.note.setText(msg)
        self.assistant_response.setText(msg)
        if self.tray is not None:
            self.tray.showMessage('Mobius • Selesai',
                                  f'{len(result.files)} file berhasil dibuat secara offline.',
                                  QSystemTrayIcon.MessageIcon.Information, 3200)

    def _failure(self, message):
        self.note.setText('Gagal: ' + message[:160])
        self.assistant_response.setText('Gagal: ' + message[:160])
        if self.tray is not None:
            self.tray.showMessage('Mobius • Gagal', message[:175],
                                  QSystemTrayIcon.MessageIcon.Warning, 3900)

    def _finished(self):
        self._busy = False
        self.status_dot.setStyleSheet('')
        self.thread = None
        self.worker = None

    def _auto_collapse(self):
        # The panel intentionally remains open following a successful drop.
        if self._drag_active:
            return
        if not self._manual_override and not self._busy and not self.underMouse() and self._expanded and not self.pending:
            self.set_expanded(False)

    def open_assistant(self):
        self.force_expand()
        self.tabs.setCurrentWidget(self.studio_tab)

    def fill_command(self, command: str):
        self.command_input.setText(command)
        self.command_input.setFocus()

    def handle_command(self):
        phrase = self.command_input.text().strip()
        if not phrase or self._intent_thread is not None:
            return
        self.assistant_status.setText('●  Memahami perintah lokal...')
        self._intent_thread = QThread(self)
        self._intent_worker = IntentWorker(phrase)
        self._intent_worker.moveToThread(self._intent_thread)
        self._intent_thread.started.connect(self._intent_worker.run)
        self._intent_worker.ready.connect(self._handle_intent)
        self._intent_worker.done.connect(self._intent_thread.quit)
        self._intent_worker.done.connect(self._intent_worker.deleteLater)
        self._intent_thread.finished.connect(self._intent_thread.deleteLater)
        self._intent_thread.finished.connect(self._intent_done)
        self._intent_thread.start()

    def _intent_done(self):
        self._intent_thread = None
        self._intent_worker = None

    def _handle_intent(self, intent):
        self.assistant_status.setText('●  PERINTAH DIPROSES LOKAL')
        if intent.kind == 'chat':
            self.assistant_response.setText(intent.detail)
            return
        if intent.dangerous:
            self.force_expand()  # make the confirmation visible even if island was hidden
            seconds = intent.args['seconds']
            yes = QMessageBox.question(self, 'Konfirmasi shutdown Windows',
                f'{intent.detail}\n\nLaptop akan ditutup otomatis. Simpan pekerjaan terlebih dahulu.\n\nLanjutkan?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if yes != QMessageBox.StandardButton.Yes:
                self.assistant_response.setText('Shutdown dibatalkan sebelum dijadwalkan.')
                self.assistant_status.setText('●  MENUNGGU PERINTAH')
                return
        if intent.kind == 'convert':
            try:
                if self._busy:
                    self.assistant_response.setText('Konversi lain masih berjalan. Coba setelah selesai.')
                    return
                path = resolve_document(intent.args['filename'], list(self.pending))
                operation = intent.args['operation']
                if not supported([path], operation):
                    self.assistant_response.setText(f'Format file {path.suffix} tidak cocok untuk konversi tersebut.')
                    return
                self.pending = [path]
                self._set_file_summary()
                self.request_operation(operation)  # QThread: no frozen window
                self.assistant_response.setText(f'Memproses {path.name} secara offline…')
                self.command_input.clear()
            except Exception as exc:
                self.assistant_response.setText(f'Gagal: {exc}')
            return
        try:
            result = execute(intent, dropped=list(self.pending), output=self.destination)
        except Exception as exc:
            result = f'Gagal: {type(exc).__name__}: {exc}'
        self.assistant_response.setText(result)
        self.assistant_status.setText('●  MENUNGGU PERINTAH')
        self.command_input.clear()

    def toggle_handsfree(self):
        if self.handsfree_active and self.voice_worker is not None:
            self.voice_worker.stop()
            self.handsfree_button.setText('◎  Menghentikan…')
            return
        if self.voice_thread is not None:
            self.assistant_response.setText('Selesaikan rekaman yang sedang berjalan dahulu.')
            return
        self.handsfree_active = True
        self.handsfree_button.setText('●  Hands-free ON')
        self.start_voice()

    def stop_voice(self):
        self._recovery_hotkey.stop()
        if self.voice_worker is not None:
            self.voice_worker.stop()
        if self.voice_thread is not None and self.voice_thread.isRunning():
            self.voice_thread.quit()
            self.voice_thread.wait(9000)

    def start_voice(self):
        if self.voice_thread is not None:
            return
        from .voice import VoiceWorker
        # Listening never activates or expands the window.
        self.voice_button.setEnabled(False)
        self.voice_button.setText('●  Merekam…')
        self.assistant_status.setText('●  HANDS-FREE LOKAL AKTIF' if self.handsfree_active else '●  MENDENGARKAN 7 DETIK (LOKAL)')
        self.voice_thread = QThread(self)
        self.voice_worker = VoiceWorker(continuous=self.handsfree_active)
        self.voice_worker.moveToThread(self.voice_thread)
        self.voice_thread.started.connect(self.voice_worker.run)
        self.voice_worker.success.connect(self._voice_success)
        self.voice_worker.failure.connect(self._voice_failure)
        self.voice_worker.finished.connect(self.voice_thread.quit)
        self.voice_worker.finished.connect(self.voice_worker.deleteLater)
        self.voice_thread.finished.connect(self.voice_thread.deleteLater)
        self.voice_thread.finished.connect(self._voice_finished)
        self.voice_thread.start()

    def _voice_success(self, phrase: str):
        self.command_input.setText(phrase)
        self.assistant_response.setText('Terdengar: ' + phrase)
        # Only dispatch when user explicitly speaks the wake word; no accidental
        # actions from unrecognised nearby conversation.
        if re.match(r'^(?:(?:hey|hei|hai|halo)\s+)?(?:mobius|mobi\s+us)\b', phrase.strip(), re.IGNORECASE):
            self.handle_command()
        else:
            self.assistant_response.setText('Terdengar: ' + phrase + ' — awali perintah dengan “Mobius” atau tekan Jalankan.')

    def _voice_failure(self, message: str):
        self.assistant_response.setText(message)

    def _voice_finished(self):
        self.voice_thread = None
        self.voice_worker = None
        self.voice_button.setEnabled(True)
        self.voice_button.setText('◉  Bicara (7s)')
        self.handsfree_active = False
        self.handsfree_button.setText('◎  Hands-free OFF')
        self.assistant_status.setText('●  MENUNGGU PERINTAH')

    def closeEvent(self, event):
        # Closing is reserved for tray Quit, so no accidental loss of the desktop island.
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