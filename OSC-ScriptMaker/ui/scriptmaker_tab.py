"""
ui/scriptmaker_tab.py
────────────────────────
Scripts tab: a status bar (Start/Stop/Restart automation — no host/port
here, every OSC trigger and every OSC-sending action sets its own), a
live fire-log, a toolbar (+ Add Script / Help / Settings), then a
scrollable list of ScriptCards.
"""

from PySide6.QtCore import Qt, QObject, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QPlainTextEdit,
)

from core.models import Script, default_script
from core.script_engine import ScriptEngine
from ui import theme
from ui.theme import StripeBackground
from ui.script_card import ScriptCard

MAX_LOG_LINES = 200


class _Bridge(QObject):
    """Background threads (listeners / timer loop / firing script threads)
    never touch widgets directly — they emit here, and this signal is
    connected to a main-thread slot, per the porting guide's
    thread-safety rule (Qt auto-queues cross-thread signal emits)."""
    log_line = Signal(str)


class ScriptMakerTab(StripeBackground):
    def __init__(self, cfg: dict, save_cb, help_cb, settings_cb, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._save_cb = save_cb
        self._help_cb = help_cb
        self._settings_cb = settings_cb

        self.cards: list[ScriptCard] = []
        self._uid_counter = 0

        self._bridge = _Bridge()
        self._bridge.log_line.connect(self._append_log)

        self.engine = ScriptEngine(
            get_scripts_cb=self._collect_scripts_for_engine,
            log_cb=lambda msg: self._bridge.log_line.emit(msg),
        )

        self._build()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        self._build_status_bar(outer)
        self._build_toolbar(outer)
        self._build_log(outer)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("background: transparent; border: none;")

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 4, 0)
        self._inner_layout.setSpacing(6)
        self._inner_layout.addStretch(1)

        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)

    def _build_status_bar(self, outer):
        frame = QWidget()
        frame.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 6, 10, 6)

        status_caption = QLabel("Status:")
        status_caption.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        status_caption.setFont(theme.qt_font(9))
        row.addWidget(status_caption)

        self._status_label = QLabel("Stopped")
        self._status_label.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        self._status_label.setFont(theme.qt_font(9, bold=True))
        row.addWidget(self._status_label)
        row.addStretch(1)

        outer.addWidget(frame)

    def _build_toolbar(self, outer):
        # ── Control buttons (Start / Stop / Restart / Help / Settings) ─────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 4)

        for text, cmd in (
                ("▶  Start",   self.start_engine),
                ("■  Stop",    self.stop_engine),
                ("↺  Restart", self.restart_engine),
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
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.clicked.connect(self._help_cb)
        btn_row.addWidget(help_btn)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setStyleSheet(theme.subtle_button_qss())
        settings_btn.setFont(theme.qt_font(9))
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.clicked.connect(self._settings_cb)
        btn_row.addWidget(settings_btn)

        outer.addLayout(btn_row)

        # ── Add Script (ScriptMaker-specific, Chatbox has no equivalent) ───────
        add_row = QHBoxLayout()
        add_row.setContentsMargins(0, 0, 0, 4)

        add_btn = QPushButton("＋  Add Script")
        add_btn.setFont(theme.qt_font(10, bold=True))
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setMinimumWidth(130)
        add_btn.clicked.connect(self._add_script)
        add_row.addWidget(add_btn)
        add_row.addStretch(1)

        outer.addLayout(add_row)

    def _build_log(self, outer):
        cap = QLabel("ACTIVITY")
        cap.setStyleSheet(theme.section_caption_qss())
        cap.setFont(theme.qt_font(8, bold=True))
        outer.addWidget(cap)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(70)
        self._log.setFont(theme.qt_font(8))
        self._log.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {theme.PANEL}; color: {theme.SUBTEXT}; "
            f"border: 1px solid {theme.BORDER}; }}"
        )
        outer.addWidget(self._log)

    def _append_log(self, msg: str):
        self._log.appendPlainText(msg)
        doc = self._log.document()
        if doc.blockCount() > MAX_LOG_LINES:
            cursor = self._log.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor,
                                doc.blockCount() - MAX_LOG_LINES)
            cursor.removeSelectedText()

    # ── Engine start/stop/restart ────────────────────────────────────────
    # No host/port here — every OSC trigger listens on its own address and
    # every OSC-sending action sends to its own address. These just flip
    # automation on/off; the engine syncs its listener pool to whatever
    # enabled scripts currently need, automatically.

    def _set_status(self, running: bool):
        if running:
            self._status_label.setText("Running")
            self._status_label.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
        else:
            self._status_label.setText("Stopped")
            self._status_label.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")

    def start_engine(self):
        if self.engine.is_running:
            return
        self.engine.start()
        self._set_status(True)
        self._append_log("Automation started")

    def stop_engine(self):
        self.engine.stop()
        self._set_status(False)
        self._append_log("Automation stopped")

    def restart_engine(self):
        self._append_log("Restarting automation\u2026")
        self.stop_engine()
        QTimer.singleShot(1200, self.start_engine)

    # ── Scripts ──────────────────────────────────────────────────────────

    def load_scripts(self):
        saved = self._cfg.get("scripts", [])
        if saved:
            for sd in saved:
                s = Script.from_dict(sd)
                self._uid_counter = max(self._uid_counter, s.uid)
                self._add_script_card(s)
        else:
            self._add_script()
        if self._cfg.get("auto_start"):
            self.start_engine()

    def _add_script(self):
        self._uid_counter += 1
        s = default_script(self._uid_counter)
        self._add_script_card(s)
        self._save_cb()

    def _add_script_card(self, script: Script):
        card = ScriptCard(script, on_remove=self._remove_script)
        self._inner_layout.insertWidget(self._inner_layout.count() - 1, card)
        self.cards.append(card)

    def _remove_script(self, card: ScriptCard):
        self._inner_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        self.cards.remove(card)
        self._save_cb()

    def _collect_scripts_for_engine(self) -> list[Script]:
        return [c.get_config() for c in self.cards]

    # ── Config I/O ────────────────────────────────────────────────────────

    def collect_scripts(self) -> list[dict]:
        return [c.get_config().to_dict() for c in self.cards]

    def destroy_all(self):
        self.engine.shutdown()