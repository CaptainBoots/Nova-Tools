"""
ui/friends_feed_tab.py
──────────────────────────
Tab 2: "Friends Feed". Live scrolling feed of friend status/location/
avatar changes (§8.8 Start/Stop control bar governs the shared engine,
owned by App per §5/§6.8 so it survives a theme rebuild).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from core.log_writer import RotatingDirLogWriter
from ui.feed_widget import FeedList
from ui import theme


class FriendsFeedTab(theme.StripeBackground):
    def __init__(self, cfg: dict, save_cb, help_cb, settings_cb, engine, bridge, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._save_cb = save_cb
        self._help_cb = help_cb
        self._settings_cb = settings_cb
        self._engine = engine
        self._bridge = bridge

        self._build()
        self._load_history()
        self._set_status(self._engine.is_running)

        self._bridge.friend_event.connect(self._feed.add_event, Qt.QueuedConnection)
        self._bridge.engine_status.connect(self._set_status, Qt.QueuedConnection)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 0)
        outer.setSpacing(6)

        status_frame = QFrame()
        status_frame.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 6, 10, 6)

        status_caption = QLabel("Engine:")
        status_caption.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        status_caption.setFont(theme.qt_font(9))
        status_layout.addWidget(status_caption)

        self._status_lbl = QLabel("Stopped")
        self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        self._status_lbl.setFont(theme.qt_font(9, bold=True))
        status_layout.addWidget(self._status_lbl)
        status_layout.addStretch(1)
        outer.addWidget(status_frame)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 4)
        for text, cmd in (
                ("▶  Start", self._start),
                ("■  Stop", lambda: self._stop()),
                ("↺  Restart", self._restart),
        ):
            b = QPushButton(text)
            b.setFont(theme.qt_font(10, bold=True))
            b.setMinimumWidth(110)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(cmd)
            btn_row.addWidget(b)
        btn_row.addStretch(1)

        help_btn = QPushButton("? Help")
        help_btn.setStyleSheet(theme.subtle_button_qss())
        help_btn.setFont(theme.qt_font(9))
        help_btn.clicked.connect(self._help_cb)
        btn_row.addWidget(help_btn)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setStyleSheet(theme.subtle_button_qss())
        settings_btn.setFont(theme.qt_font(9))
        settings_btn.clicked.connect(self._settings_cb)
        btn_row.addWidget(settings_btn)

        outer.addLayout(btn_row)

        self._feed = FeedList(empty_text="No friend activity logged yet.")
        outer.addWidget(self._feed, 1)

    def _load_history(self):
        writer = RotatingDirLogWriter(
            self._cfg.get("log_dir"), "friends_feed", self._cfg.get("friends_log_cap_bytes", 0),
        )
        for event in writer.read_recent(limit=200):
            self._feed.add_event(event)

    # ── Start/Stop/Restart (§8.8) — controls the SHARED engine, so
    # starting/stopping here affects tab 3 too; both tabs just reflect
    # the same engine_status signal. ──────────────────────────────────

    def _set_status(self, running: bool):
        if running:
            self._status_lbl.setText("Running")
            self._status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
        else:
            self._status_lbl.setText("Stopped")
            self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")

    def _start(self):
        if self._engine.is_running:
            return
        self._engine.start()
        self._bridge.engine_status.emit(True)

    def _stop(self):
        self._engine.stop()
        self._bridge.engine_status.emit(False)

    def _restart(self):
        from PySide6.QtCore import QTimer
        self._stop()
        QTimer.singleShot(1200, self._start)

    def destroy_all(self):
        pass