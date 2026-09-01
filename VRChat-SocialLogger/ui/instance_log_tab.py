"""
ui/instance_log_tab.py
──────────────────────────
Tab 3: "Current Instance Log". Same feed-style view as the Friends Feed
tab, scoped to whatever instance the user is currently in, sourced from
core.vrlog_tail via the shared engine. The engine's Start/Stop control
lives on the Friends Feed tab (§8.8's single-engine variant) since both
tabs are fed by the one background engine App owns — this tab just
displays its stream and reflects the same status.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from core.log_writer import RotatingDirLogWriter
from ui.feed_widget import FeedList
from ui import theme


class InstanceLogTab(theme.StripeBackground):
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

        self._bridge.instance_event.connect(self._feed.add_event, Qt.QueuedConnection)
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

        hint_lbl = QLabel("(controlled from the Friends Feed tab)")
        hint_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        hint_lbl.setFont(theme.qt_font(8))
        status_layout.addWidget(hint_lbl)

        outer.addWidget(status_frame)

        self._feed = FeedList(empty_text="No instance activity logged yet.")
        outer.addWidget(self._feed, 1)

        footer = QFrame()
        footer.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 6, 12, 6)
        footer_layout.addStretch(1)

        help_btn = QPushButton("? Help")
        help_btn.setStyleSheet(theme.subtle_button_qss())
        help_btn.clicked.connect(self._help_cb)
        footer_layout.addWidget(help_btn)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setStyleSheet(theme.subtle_button_qss())
        settings_btn.clicked.connect(self._settings_cb)
        footer_layout.addWidget(settings_btn)

        outer.addWidget(footer)

    def _load_history(self):
        writer = RotatingDirLogWriter(
            self._cfg.get("log_dir"), "instance_log", self._cfg.get("instance_log_cap_bytes", 0),
        )
        for event in writer.read_recent(limit=200):
            self._feed.add_event(event)

    def _set_status(self, running: bool):
        if running:
            self._status_lbl.setText("Running")
            self._status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
        else:
            self._status_lbl.setText("Stopped")
            self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")

    def destroy_all(self):
        pass