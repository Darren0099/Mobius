"""Integrated Music, Lyrics, Focus and Water quick deck for Mobius.

The existing assistant/File Studio stays on the same screen; deck expansion is
temporary, using local state except optional user-requested lyrics lookup.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QProgressBar, QPushButton, QSlider,
    QSpinBox, QStackedWidget, QVBoxLayout, QWidget
)

from .lyrics import active_line, load_lrc, search_lrclib
from .vector_icons import attach, icon
from .arc_meter import ArcMeter
from .theme import ORANGE, CORAL
from .chime import play_soft_chime
from .media_bridge import MediaBridge
from .wellness import WellnessStore


class WaterBars(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bars = [0] * 24
        self.setMinimumHeight(36)
        self.setMaximumHeight(46)

    def set_hours(self, values):
        self.bars = values[:24]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = max(1, self.width() - 10)
        height = self.height() - 8
        top = max(250, max(self.bars, default=0))
        p.setPen(Qt.PenStyle.NoPen)
        for h in range(24):
            bar_w = width / 24 * .72
            x = 5 + h * width / 24
            size = self.bars[h] / top * height
            p.setBrush(QColor(CORAL if self.bars[h] else "#34323A"))
            p.drawRoundedRect(int(x), int(height - size + 3), max(2, int(bar_w)),
                              max(3, int(size)), 2, 2)
        p.end()


def button(label, callback, *, primary=False, glyph=None):
    b = QPushButton(label)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setObjectName("quickPrimary" if primary else "quickButton")
    if glyph:
        attach(b, glyph, size=15, color='#141416' if primary else '#FAFAFC')
    b.clicked.connect(callback)
    return b


class QuickDeck(QWidget):
    changed = Signal(bool)             # whether quick detail is expanded
    alert = Signal(str)                # reminder, state, or media problem
    lyric_ready = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store = WellnessStore()
        self.current_media = {"available": False}
        self._media_clock_at = time.monotonic()
        self.lyrics = []
        self._lyric_key = None
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="MobiusLyrics")
        self._active_page = -1
        self._build()
        self.media = MediaBridge(self)
        self.media.snapshot.connect(self._media_updated)
        self.media.error.connect(self._media_error)
        self.media.message.connect(self.alert.emit)
        self.lyric_ready.connect(self._on_lyrics_result)
        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick)
        self._clock.start()
        self._tick()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(5)
        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.nav = []
        for index, title in enumerate(("Music", "Lyrics", "Focus", "Water")):
            b = button(title, lambda _=False, page=index: self.toggle_page(page))
            b.setCheckable(True)
            nav.addWidget(b)
            self.nav.append(b)
        nav.addStretch(1)
        outer.addLayout(nav)
        self.pages = QStackedWidget()
        self.pages.setObjectName("quickPage")
        self.pages.addWidget(self._music_page())
        self.pages.addWidget(self._lyrics_page())
        self.pages.addWidget(self._focus_page())
        self.pages.addWidget(self._water_page())
        outer.addWidget(self.pages)
        self.pages.hide()

    def toggle_page(self, page):
        was_open = self._active_page >= 0
        self._active_page = -1 if self._active_page == page else page
        for index, btn in enumerate(self.nav):
            btn.setChecked(index == self._active_page)
        if self._active_page >= 0:
            self.pages.setCurrentIndex(self._active_page)
        self.pages.setVisible(self._active_page >= 0)
        if was_open != (self._active_page >= 0):
            self.changed.emit(self._active_page >= 0)

    def _music_page(self):
        """Tight player card: artwork mark, track, transport and thin seek."""
        widget = QFrame()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(9, 7, 9, 6)
        layout.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(10)
        cover = QLabel()
        cover.setObjectName("musicCover")
        cover.setFixedSize(51, 51)
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover.setPixmap(icon("music", 26).pixmap(26, 26))
        top.addWidget(cover)
        detail = QVBoxLayout()
        detail.setContentsMargins(0, 2, 0, 0)
        detail.setSpacing(2)
        self.track = QLabel("No player detected")
        self.track.setWordWrap(True)
        self.track.setObjectName("quickTrack")
        detail.addWidget(self.track)
        self.media_status = QLabel("Spotify, Apple Music or browser session")
        self.media_status.setObjectName("quickHint")
        detail.addWidget(self.media_status)
        top.addLayout(detail, 1)
        layout.addLayout(top)

        transport = QHBoxLayout()
        transport.setSpacing(5)
        for action, glyph, tip in (
            ("previous", "previous", "Previous track"),
            ("toggle", "play", "Pause or play"),
            ("next", "next", "Next track"),
        ):
            b = button("", lambda _=False, a=action: self.media.control(a), glyph=glyph)
            b.setFixedSize(38, 29)
            b.setToolTip(tip)
            transport.addWidget(b)
        transport.addStretch(1)
        layout.addLayout(transport)

        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.setToolTip("Seek playback position if supported")
        self.seek.sliderReleased.connect(self._seek_requested)
        layout.addWidget(self.seek)
        return widget

    def _lyrics_page(self):
        widget = QFrame()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(5)
        controls = QHBoxLayout()
        controls.setSpacing(5)
        controls.addWidget(button("Open LRC", self._open_lrc, glyph="folder"))
        controls.addWidget(button("Find lyrics", self._find_online, glyph="search"))
        controls.addStretch()
        layout.addLayout(controls)
        split = QHBoxLayout()
        split.setSpacing(6)
        left = QFrame()
        left.setObjectName("lyricLeft")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 6, 8, 6)
        left_layout.setSpacing(4)
        self.lyric_song = QLabel("Waiting for music")
        self.lyric_song.setObjectName("quickTrack")
        self.lyric_song.setWordWrap(True)
        left_layout.addWidget(self.lyric_song)
        self.lyric_live = QLabel("Timed lyrics appear here")
        self.lyric_live.setObjectName("lyricLive")
        self.lyric_live.setWordWrap(True)
        left_layout.addWidget(self.lyric_live, 1)
        split.addWidget(left, 2)
        self.lyric_list = QListWidget()
        self.lyric_list.setObjectName("quickLyrics")
        self.lyric_list.setMinimumHeight(90)
        self.lyric_list.setMaximumHeight(120)
        self.lyric_list.itemClicked.connect(self._lyric_clicked)
        split.addWidget(self.lyric_list, 3)
        layout.addLayout(split)
        self.lyric_hint = QLabel("LRC: offline  |  lookup: optional internet")
        self.lyric_hint.setWordWrap(True)
        self.lyric_hint.setObjectName("quickHint")
        layout.addWidget(self.lyric_hint)
        return widget

    def _focus_page(self):
        """Single-row Pomodoro ring and clock, short action buttons."""
        widget = QFrame()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(4)

        hero = QHBoxLayout()
        hero.setSpacing(11)
        self.focus_ring = ArcMeter("timer", 78)
        hero.addWidget(self.focus_ring)
        metrics = QVBoxLayout()
        metrics.setSpacing(0)
        self.focus_time = QLabel("25:00")
        self.focus_time.setObjectName("quickClock")
        metrics.addWidget(self.focus_time)
        self.focus_hint = QLabel("Focus · paused")
        self.focus_hint.setObjectName("quickHint")
        metrics.addWidget(self.focus_hint)
        hero.addLayout(metrics, 1)

        config = QVBoxLayout()
        config.setSpacing(2)
        row1 = QHBoxLayout()
        row1.setSpacing(3)
        row1.addWidget(QLabel("Focus"))
        self.focus_minutes = QSpinBox()
        self.focus_minutes.setRange(5, 120)
        self.focus_minutes.setValue(self.store.focus.work_minutes)
        self.focus_minutes.setFixedWidth(52)
        self.focus_minutes.valueChanged.connect(self._focus_options)
        row1.addWidget(self.focus_minutes)
        config.addLayout(row1)
        row2 = QHBoxLayout()
        row2.setSpacing(3)
        row2.addWidget(QLabel("Break"))
        self.break_minutes = QSpinBox()
        self.break_minutes.setRange(1, 45)
        self.break_minutes.setValue(self.store.focus.break_minutes)
        self.break_minutes.setFixedWidth(52)
        self.break_minutes.valueChanged.connect(self._focus_options)
        row2.addWidget(self.break_minutes)
        config.addLayout(row2)
        hero.addLayout(config)
        layout.addLayout(hero)

        actions = QHBoxLayout()
        actions.setSpacing(5)
        actions.addWidget(button("Start / Pause", self._toggle_focus,
                                 primary=True, glyph="play"))
        actions.addWidget(button("Reset", self._reset_focus, glyph="reset"))
        actions.addStretch()
        layout.addLayout(actions)
        return widget

    def _water_page(self):
        """Two compact faces: hydration summary and editable reminder settings."""
        widget = QFrame()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(8, 5, 8, 5)
        outer.setSpacing(0)
        self.water_stack = QStackedWidget(widget)
        outer.addWidget(self.water_stack)

        overview = QFrame()
        layout = QVBoxLayout(overview)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        hero = QHBoxLayout()
        hero.setSpacing(9)
        self.water_ring = ArcMeter("water", 66)
        self.water_ring.set_fraction(0)
        hero.addWidget(self.water_ring)
        info = QVBoxLayout()
        info.setSpacing(2)
        self.water_total = QLabel("0 / 2000 ml")
        self.water_total.setObjectName("waterTotal")
        info.addWidget(self.water_total)
        self.water_hint = QLabel("Daily hydration")
        self.water_hint.setObjectName("quickHint")
        info.addWidget(self.water_hint)
        hero.addLayout(info, 1)
        layout.addLayout(hero)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.addWidget(button("Add water", self._drink, primary=True, glyph="water"))
        actions.addWidget(button("Settings", lambda: self.water_stack.setCurrentIndex(1)))
        actions.addStretch(1)
        layout.addLayout(actions)
        self.water_progress = QProgressBar()
        self.water_progress.setRange(0, 100)
        self.water_progress.setFixedHeight(9)
        self.water_progress.setTextVisible(False)
        layout.addWidget(self.water_progress)
        self.water_chart = WaterBars()
        layout.addWidget(self.water_chart)
        self.water_stack.addWidget(overview)

        settings = QFrame()
        grid = QGridLayout(settings)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(5)
        grid.addWidget(QLabel("Bottle / ml"), 0, 0)
        self.bottle_size = QSpinBox()
        self.bottle_size.setRange(50, 1500)
        self.bottle_size.setSingleStep(50)
        self.bottle_size.setValue(self.store.water.bottle_ml)
        self.bottle_size.valueChanged.connect(self._water_options)
        grid.addWidget(self.bottle_size, 0, 1)
        grid.addWidget(QLabel("Goal / ml"), 0, 2)
        self.daily_goal = QSpinBox()
        self.daily_goal.setRange(250, 6000)
        self.daily_goal.setSingleStep(250)
        self.daily_goal.setValue(self.store.water.goal_ml)
        self.daily_goal.valueChanged.connect(self._water_options)
        grid.addWidget(self.daily_goal, 0, 3)

        grid.addWidget(QLabel("From"), 1, 0)
        self.water_start = QSpinBox()
        self.water_start.setRange(0, 22)
        self.water_start.setSuffix(":00")
        self.water_start.setValue(self.store.water.active_start_hour)
        self.water_start.valueChanged.connect(self._water_options)
        grid.addWidget(self.water_start, 1, 1)
        grid.addWidget(QLabel("Until"), 1, 2)
        self.water_end = QSpinBox()
        self.water_end.setRange(1, 24)
        self.water_end.setSuffix(":00")
        self.water_end.setValue(self.store.water.active_end_hour)
        self.water_end.valueChanged.connect(self._water_options)
        grid.addWidget(self.water_end, 1, 3)
        grid.addWidget(QLabel("Reminder every"), 2, 0, 1, 2)
        self.water_interval = QSpinBox()
        self.water_interval.setRange(15, 240)
        self.water_interval.setSingleStep(15)
        self.water_interval.setSuffix(" min")
        self.water_interval.setValue(self.store.water.interval_minutes)
        self.water_interval.valueChanged.connect(self._water_options)
        grid.addWidget(self.water_interval, 2, 2, 1, 2)
        done = button("Back to overview", lambda: self.water_stack.setCurrentIndex(0),
                      glyph="left")
        grid.addWidget(done, 3, 0, 1, 4)
        self.water_stack.addWidget(settings)
        self._render_water()
        return widget

    def _media_updated(self, current):
        self.current_media = current
        self._media_clock_at = time.monotonic()
        if not current.get("available"):
            self.track.setText("No active Windows media session")
            self.seek.setEnabled(False)
            return
        title = current.get("title") or "Unknown track"
        artist = current.get("artist") or "Unknown artist"
        self.track.setText(f"{title} — {artist}")
        self.lyric_song.setText(f"{title} — {artist}")
        self.seek.setEnabled(current.get("can_seek", False))
        if not self.seek.isSliderDown() and current.get("duration", 0) > 0:
            self.seek.setValue(int(min(1.0, current.get("position", 0) /
                                       current["duration"]) * 1000))
        self.media_status.setText(f"{current.get('status', 'Unknown')}  ·  "
                                  f"{int(current.get('position', 0))}s / "
                                  f"{int(current.get('duration', 0))}s")
        key = (title, artist)
        if key != self._lyric_key:
            self._lyric_key = key
            self.lyrics = []
            self.lyric_list.clear()
            self.lyric_hint.setText("Choose .lrc or Find lyrics online for this song")
        self._highlight_lyric()

    def _media_error(self, message):
        self.media_status.setText(message[:180])

    def _seek_requested(self):
        duration = self.current_media.get("duration", 0)
        if duration and self.current_media.get("can_seek"):
            self.media.control("seek", duration * self.seek.value() / 1000)

    def _open_lrc(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open synchronized lyrics",
                                                   str(Path.home() / "Music"), "LRC Lyrics (*.lrc)")
        if not filepath:
            return
        try:
            self._show_lyrics(load_lrc(Path(filepath)))
            self.lyric_hint.setText("Local LRC · no network used")
        except (ValueError, OSError) as exc:
            self.lyric_hint.setText(str(exc))

    def _find_online(self):
        media = self.current_media
        if not media.get("available") or not media.get("title"):
            self.lyric_hint.setText("Play a supported song before searching for lyrics")
            return
        self.lyric_hint.setText("Looking up synced lyrics (title and artist sent; duration checked locally)...")
        title, artist, seconds = media["title"], media.get("artist", ""), media.get("duration", 0)
        future = self._pool.submit(search_lrclib, title, artist, seconds)
        def done(f):
            try:
                self.lyric_ready.emit(f.result())
            except Exception as exc:
                self.lyric_ready.emit(exc)
        future.add_done_callback(done)

    def _on_lyrics_result(self, result):
        if isinstance(result, Exception):
            self.lyric_hint.setText("Lyrics lookup failed: " + str(result)[:110])
        elif result:
            self._show_lyrics(result)
            self.lyric_hint.setText("Synced lyrics found · click a line to seek (if supported)")
        else:
            self.lyric_hint.setText("No time-synced lyrics available for this song")

    def _show_lyrics(self, entries):
        self.lyrics = entries
        self.lyric_list.clear()
        for seconds, text in entries[:900]:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, seconds)
            self.lyric_list.addItem(item)
        self._highlight_lyric()

    def estimated_position(self):
        position = float(self.current_media.get("position", 0))
        if self.current_media.get("status") == "playing":
            position += max(0, time.monotonic() - self._media_clock_at)
        duration = float(self.current_media.get("duration", 0))
        return min(position, duration) if duration else position

    def _highlight_lyric(self):
        if not self.lyrics:
            self.lyric_live.setText("Select a synchronized lyric source")
            return
        idx = active_line(self.lyrics, self.estimated_position())
        self.lyric_live.setText(self.lyrics[idx][1] if idx >= 0 else "Waiting for next line")
        if 0 <= idx < self.lyric_list.count() and self.lyric_list.currentRow() != idx:
            self.lyric_list.setCurrentRow(idx)
            self.lyric_list.scrollToItem(self.lyric_list.item(idx))

    def _lyric_clicked(self, item):
        if self.current_media.get("can_seek"):
            self.media.control("seek", float(item.data(Qt.ItemDataRole.UserRole)))
        else:
            self.lyric_hint.setText("This player does not expose seeking to Windows")

    def _focus_options(self):
        focus = self.store.focus
        focus.work_minutes = self.focus_minutes.value()
        focus.break_minutes = self.break_minutes.value()
        if focus.deadline is None:
            focus.reset()
        self.store.save()
        self._render_focus()

    def _toggle_focus(self):
        timer = self.store.focus
        if timer.deadline is None:
            timer.start()
        else:
            timer.pause()
        self._render_focus()

    def _reset_focus(self):
        self.store.focus.reset()
        self._render_focus()

    def _render_focus(self):
        timer = self.store.focus
        remaining = timer.remaining()
        self.focus_time.setText(f"{remaining // 60:02d}:{remaining % 60:02d}")
        total = (timer.work_minutes if timer.mode == "focus" else timer.break_minutes) * 60
        self.focus_ring.set_fraction(remaining / max(1, total))
        mode = "Focus" if timer.mode == "focus" else "Break"
        running = "running" if timer.deadline is not None else "paused"
        self.focus_hint.setText(f"{mode}  ·  {running}  ·  {timer.completed_sessions} sessions")

    def _water_options(self):
        self.store.water.bottle_ml = self.bottle_size.value()
        self.store.water.goal_ml = self.daily_goal.value()
        start, end = self.water_start.value(), self.water_end.value()
        if start >= end:
            # Keep a valid reminder window without recursive widget updates.
            end = min(24, start + 1)
            self.water_end.blockSignals(True)
            self.water_end.setValue(end)
            self.water_end.blockSignals(False)
        self.store.water.active_start_hour = start
        self.store.water.active_end_hour = end
        self.store.water.interval_minutes = self.water_interval.value()
        self.water_hint.setText(f"Hourly intake chart · reminders {start:02d}:00–{end:02d}:00 every {self.store.water.interval_minutes} min")
        self.store.save()
        self._render_water()

    def _drink(self):
        self.store.water.add()
        self.store.save()
        self._render_water()

    def _render_water(self):
        water = self.store.water
        total = water.consumed()
        percent = int(100 * total / max(1, water.goal_ml))
        self.water_progress.setValue(min(100, percent))
        self.water_progress.setFormat(f"{total} / {water.goal_ml} ml · {percent}%")
        self.water_ring.set_fraction(min(1.0, total / max(1, water.goal_ml)))
        self.water_total.setText(f"{total:,} / {water.goal_ml:,} ml")
        self.water_chart.set_hours(water.hourly_chart())

    def _tick(self):
        focus = self.store.focus
        if focus.tick():
            self.store.save()
            play_soft_chime()
            self.alert.emit("Focus session finished. Time to switch mode.")
        self._render_focus()
        self._highlight_lyric()
        water = self.store.water
        before = water.day
        water.ensure_today()
        if before != water.day:
            self._render_water()
            self.store.save()
        # Water reminders check periodically, never outside user hours.
        if datetime.now().second < 2 and water.should_remind():
            water.mark_reminded()
            self.store.save()
            self.alert.emit("Water reminder: drink a glass and log it in Mobius.")

    def stop(self):
        self._clock.stop()
        self.media.stop()
        self._pool.shutdown(wait=False, cancel_futures=True)
        self.store.save()
