"""
ui/browser_tab.py
──────────────────
Main content tab: connection config, filter/inject controls, live
parameter table, and footer status bar.
"""

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)

from core.osc_bridge import ParamListener, make_client, send_osc
from ui import theme
from ui.theme import StripeBackground


class _ListenerBridge(QObject):
    """Re-emits ParamListener's callbacks (which fire from a background
    thread) as Qt signals, landing safely on the UI thread."""
    param_signal = Signal(str, object, str, str)
    error_signal = Signal(str)


class BrowserTab(StripeBackground):
    def __init__(self, cfg: dict, save_cb, help_cb, settings_cb, parent=None):
        super().__init__(parent)
        self._cfg         = cfg
        self._save_cb     = save_cb
        self._help_cb     = help_cb
        self._settings_cb = settings_cb

        self._params: dict[str, tuple] = {}
        self._listener: ParamListener | None = None
        self._bridge = _ListenerBridge()
        self._bridge.param_signal.connect(self._on_param)
        self._bridge.error_signal.connect(self._on_error)
        self._chips = []  # TextChip labels — see set_bg_alpha override below

        self._build()

    def set_bg_alpha(self, alpha: float):
        """Propagate background transparency to every TextChip label too,
        same pattern as ChatboxTab — otherwise they'd stay permanently
        opaque while the rest of the background fades."""
        super().set_bg_alpha(alpha)
        for chip in self._chips:
            chip.set_bg_alpha(alpha)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 0)
        outer.setSpacing(6)

        # ── Config row (connection fields) ───────────────────────────────────
        cfg_row = QHBoxLayout()

        def lbl(text):
            l = theme.TextChip(text, fg=theme.SUBTEXT, padding="2px 6px")
            l.setFont(theme.qt_font(9))
            cfg_row.addWidget(l)
            self._chips.append(l)
            return l

        def entry(default, width):
            e = QLineEdit(default)
            e.setFixedWidth(width)
            e.setFont(theme.qt_font(9))
            e.setStyleSheet(theme.line_edit_qss())
            cfg_row.addWidget(e)
            return e

        lbl("Target IP:")
        self._ip_entry = entry(self._cfg.get("target_ip", "127.0.0.1"), 100)
        cfg_row.addSpacing(6)
        lbl("Send Port:")
        self._sport_entry = entry(str(self._cfg.get("send_port", 9000)), 55)
        cfg_row.addSpacing(6)
        lbl("Listen Port:")
        self._lport_entry = entry(str(self._cfg.get("listen_port", 9001)), 55)

        for e in (self._ip_entry, self._sport_entry, self._lport_entry):
            e.editingFinished.connect(self._save_conn_settings)

        cfg_row.addSpacing(12)
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        self._dot.setFont(theme.qt_font(11))
        cfg_row.addWidget(self._dot)
        cfg_row.addStretch(1)

        outer.addLayout(cfg_row)

        # ── Button row (actions + Help/Settings) ─────────────────────────────
        # Matching the other tools exactly: Start / Stop / Restart using the
        # app-wide default QPushButton style (no per-button background
        # override), Help/Settings right-aligned on the same row.
        btn_row = QHBoxLayout()

        for text, cmd in (
                ("▶  Start",   self._start),
                ("■  Stop",    self._stop),
                ("↺  Restart", self._restart),
        ):
            b = QPushButton(text)
            b.setFont(theme.qt_font(10, bold=True))
            b.setMinimumWidth(110)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(cmd)
            btn_row.addWidget(b)

        clear_btn = QPushButton("Clear Data")
        clear_btn.setStyleSheet(theme.subtle_button_qss())
        clear_btn.setFont(theme.qt_font(10))
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(clear_btn)

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

        # ── Filter / Injector controls ───────────────────────────────────────
        controls = QFrame()
        controls.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(10, 8, 10, 8)
        controls_layout.setSpacing(6)

        filter_row = QHBoxLayout()
        filter_cap = QLabel("Filter Address:")
        filter_cap.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        filter_cap.setFont(theme.qt_font(9))
        filter_row.addWidget(filter_cap)

        self._filter_entry = QLineEdit()
        self._filter_entry.setFont(theme.qt_font(9))
        self._filter_entry.setStyleSheet(theme.line_edit_qss())
        self._filter_entry.textChanged.connect(self._refresh)
        filter_row.addWidget(self._filter_entry, 1)
        controls_layout.addLayout(filter_row)

        inject_row = QHBoxLayout()
        inject_cap = QLabel("Inject Address:")
        inject_cap.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        inject_cap.setFont(theme.qt_font(9))
        inject_row.addWidget(inject_cap)

        self._addr_entry = QLineEdit(self._cfg.get("inject_addr", "/avatar/parameters/"))
        self._addr_entry.setFont(theme.qt_font(9))
        self._addr_entry.setStyleSheet(theme.line_edit_qss())
        inject_row.addWidget(self._addr_entry, 1)

        val_cap = QLabel("Val:")
        val_cap.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        val_cap.setFont(theme.qt_font(9))
        inject_row.addWidget(val_cap)

        self._val_entry = QLineEdit("0")
        self._val_entry.setFixedWidth(70)
        self._val_entry.setFont(theme.qt_font(9))
        self._val_entry.setStyleSheet(theme.line_edit_qss())
        inject_row.addWidget(self._val_entry)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["float", "int", "bool", "string"])
        self._type_combo.setFont(theme.qt_font(9))
        self._type_combo.setStyleSheet(
            f"QComboBox {{ background-color: {theme.BG}; color: {theme.TEXT}; border: 1px solid {theme.BORDER}; "
            f"padding: 2px 6px; }}"
            f"QComboBox QAbstractItemView {{ background-color: {theme.PANEL}; color: {theme.TEXT}; "
            f"selection-background-color: {theme.ACCENT}; border: 1px solid {theme.BORDER}; }}"
        )
        inject_row.addWidget(self._type_combo)

        send_btn = QPushButton("Send Packet")
        send_btn.setStyleSheet(
            f"QPushButton {{ background-color: {theme.ACCENT}; color: {theme.TEXT}; border: none; padding: 3px 10px; }}"
            f"QPushButton:hover {{ background-color: {theme.ACCENT2}; }}"
        )
        send_btn.setFont(theme.qt_font(9))
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.clicked.connect(self._send)
        inject_row.addWidget(send_btn)

        controls_layout.addLayout(inject_row)
        outer.addWidget(controls)

        # ── Parameter table ──────────────────────────────────────────────────
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Path", "Value", "Type", "Ts"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setFont(theme.qt_font(9))
        self._table.setStyleSheet(
            f"QTableWidget {{ background-color: {theme.PANEL}; color: {theme.TEXT}; border: none; "
            f"gridline-color: {theme.BORDER}; }}"
            f"QTableWidget::item {{ padding: 2px 6px; border: none; }}"
            f"QTableWidget::item:selected {{ background-color: {theme.ACCENT2}; color: {theme.BG}; }}"
            f"QHeaderView::section {{ background-color: {theme.PANEL}; color: {theme.ACCENT}; "
            f"padding: 4px 6px; border: none; font-weight: bold; }}"
        )
        self._table.cellDoubleClicked.connect(self._on_row_double_click)
        outer.addWidget(self._table, 1)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 6, 12, 6)

        self._status_lbl = QLabel("Status: IDLE")
        self._status_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        self._status_lbl.setFont(theme.qt_font(9))
        footer_layout.addWidget(self._status_lbl)
        footer_layout.addStretch(1)

        outer.addWidget(footer)

    # ── Connection settings persistence ─────────────────────────────────────

    def _save_conn_settings(self):
        self._cfg["target_ip"] = self._ip_entry.text().strip()
        try:
            self._cfg["send_port"] = int(self._sport_entry.text())
        except ValueError:
            pass
        try:
            self._cfg["listen_port"] = int(self._lport_entry.text())
        except ValueError:
            pass
        self._save_cb()

    # ── Listener control ─────────────────────────────────────────────────────

    def _start(self):
        if self._listener is not None and self._listener.running:
            return
        try:
            port = int(self._lport_entry.text())
        except ValueError:
            self._status_lbl.setText("Status: Invalid Listen Port.")
            self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
            return

        self._save_conn_settings()

        self._listener = ParamListener(
            port,
            on_param=lambda addr, val, typ, ts: self._bridge.param_signal.emit(addr, val, typ, ts),
            on_error=lambda msg: self._bridge.error_signal.emit(msg),
        )
        self._listener.start()
        self._dot.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
        self._status_lbl.setText(f"Status: Listening on port {port}...")
        self._status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")

    def _stop(self):
        if self._listener is not None:
            self._listener.stop()
        self._dot.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        self._status_lbl.setText("Status: Stopped")
        self._status_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")

    def _restart(self):
        self._status_lbl.setText("Status: Restarting...")
        self._status_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        self._stop()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1200, self._start)

    def _clear(self):
        self._params.clear()
        self._refresh()

    # ── Listener callbacks (already marshalled to UI thread via bridge) ────

    def _on_param(self, addr, val, typ, ts):
        self._params[addr] = (val, typ, ts)
        self._refresh()

    def _on_error(self, message):
        self._status_lbl.setText(message)
        self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        self._dot.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")

    # ── Table ─────────────────────────────────────────────────────────────────

    def _refresh(self):
        filt = self._filter_entry.text().lower()
        rows = [
            (path, val, typ, ts)
            for path, (val, typ, ts) in sorted(self._params.items())
            if not filt or filt in path.lower()
        ]
        self._table.setRowCount(len(rows))
        for r, (path, val, typ, ts) in enumerate(rows):
            for c, text in enumerate((path, str(val), typ, ts)):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._table.setItem(r, c, item)

    def _on_row_double_click(self, row: int, _col: int):
        path_item = self._table.item(row, 0)
        val_item  = self._table.item(row, 1)
        typ_item  = self._table.item(row, 2)
        if not path_item:
            return
        self._addr_entry.setText(path_item.text())
        self._val_entry.setText(val_item.text() if val_item else "")
        if typ_item:
            idx = self._type_combo.findText(typ_item.text())
            if idx >= 0:
                self._type_combo.setCurrentIndex(idx)

    # ── Send / inject ─────────────────────────────────────────────────────────

    def _send(self):
        from core.osc_bridge import PYTHON_OSC
        if not PYTHON_OSC:
            self._status_lbl.setText("Status: python-osc package missing.")
            self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
            return

        ip = self._ip_entry.text().strip()
        try:
            port = int(self._sport_entry.text().strip())
        except ValueError:
            self._status_lbl.setText("Status: Invalid Send Port.")
            self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
            return

        client = make_client(ip, port)
        addr = self._addr_entry.text().strip()
        raw  = self._val_entry.text().strip()
        vt   = self._type_combo.currentText()

        try:
            if vt == "float":
                val = float(raw)
            elif vt == "int":
                val = int(raw)
            elif vt == "bool":
                val = raw.lower() in ("true", "1", "yes")
            else:
                val = raw
        except ValueError:
            self._status_lbl.setText("Status: Typing format value error!")
            self._status_lbl.setStyleSheet(f"color: {theme.YELLOW}; background: transparent; border: none;")
            return

        self._cfg["inject_addr"] = addr
        self._save_cb()

        if send_osc(client, addr, val):
            self._status_lbl.setText(f"Status: Injected {addr} -> {val}")
            self._status_lbl.setStyleSheet(f"color: {theme.CYAN}; background: transparent; border: none;")
        else:
            self._status_lbl.setText("Status: Packet network injection failed")
            self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def destroy_listener(self):
        if self._listener is not None:
            self._listener.stop()

    # ── State export/import (for live theme rebuilds in app.py) ────────────

    def export_state(self) -> dict:
        """Snapshot of everything that shouldn't be lost across a rebuild:
        captured parameter data and (if running) the live listener itself —
        not stopped, just handed off so its socket stays bound and its
        background thread keeps receiving packets the whole time."""
        return {
            "params":   dict(self._params),
            "listener": self._listener,
        }

    def import_state(self, state: dict):
        """Restore a previous instance's captured data and, if it was
        listening, re-point the still-running listener's callbacks at
        this instance's bridge and reflect that in the status/dot."""
        self._params = dict(state.get("params", {}))

        listener = state.get("listener")
        if listener is not None and listener.running:
            listener._on_param = lambda addr, val, typ, ts: self._bridge.param_signal.emit(addr, val, typ, ts)
            listener._on_error = lambda msg: self._bridge.error_signal.emit(msg)
            self._listener = listener
            self._dot.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
            self._status_lbl.setText(f"Status: Listening on port {listener.port}...")
            self._status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")

        self._refresh()