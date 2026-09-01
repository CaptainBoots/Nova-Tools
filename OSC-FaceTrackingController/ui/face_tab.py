"""
ui/face_tab.py
────────────────
Main content tab: connection config, action buttons, and category
sub-tabs of facial-parameter sliders.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSlider, QTabWidget, QScrollArea,
)

from core.face_params import FACE_PARAMS
from core.osc_face import OscFaceClient, PREFIX_PRESETS, DEFAULT_OSC_IP, DEFAULT_OSC_PORT, normalize_prefix
from ui import theme
from ui.theme import StripeBackground

SLIDER_STEPS = 1000


def _pos_for_value(value: float, lo: float, hi: float) -> int:
    if hi == lo:
        return 0
    return round((value - lo) / (hi - lo) * SLIDER_STEPS)


def _value_for_pos(pos: int, lo: float, hi: float) -> float:
    return lo + (pos / SLIDER_STEPS) * (hi - lo)


class FaceTab(StripeBackground):
    def __init__(self, cfg: dict, save_cb, help_cb, settings_cb, parent=None):
        super().__init__(parent)
        self._cfg         = cfg
        self._save_cb     = save_cb
        self._help_cb     = help_cb
        self._settings_cb = settings_cb

        self._client = OscFaceClient()
        self._sliders: dict[str, dict] = {}
        self._chips = []
        self._status_listeners = []

        self._build()
        self._set_stopped()

    def set_bg_alpha(self, alpha: float):
        super().set_bg_alpha(alpha)
        for chip in self._chips:
            chip.set_bg_alpha(alpha)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 0)
        outer.setSpacing(6)

        # ── Connection row ────────────────────────────────────────────────────
        conn_row = QHBoxLayout()

        def lbl(text):
            l = theme.TextChip(text, fg=theme.SUBTEXT, padding="2px 6px")
            l.setFont(theme.qt_font(9))
            conn_row.addWidget(l)
            self._chips.append(l)
            return l

        def entry(default, width):
            e = QLineEdit(default)
            e.setFixedWidth(width)
            e.setFont(theme.qt_font(9))
            e.setStyleSheet(theme.line_edit_qss())
            conn_row.addWidget(e)
            return e

        lbl("IP")
        self._ip_entry = entry(self._cfg.get("osc_ip", DEFAULT_OSC_IP), 100)
        conn_row.addSpacing(8)
        lbl("Port")
        self._port_entry = entry(str(self._cfg.get("osc_port", DEFAULT_OSC_PORT)), 55)
        conn_row.addSpacing(8)
        lbl("Prefix")
        self._prefix_entry = entry(self._cfg.get("osc_prefix", "/avatar/parameters/v2/"), 170)
        conn_row.addSpacing(8)

        self._preset_combo = QComboBox()
        self._preset_combo.addItems(list(PREFIX_PRESETS.keys()))
        self._preset_combo.setFont(theme.qt_font(8))
        self._preset_combo.setStyleSheet(
            f"QComboBox {{ background-color: {theme.PANEL}; color: {theme.SUBTEXT}; "
            f"border: none; padding: 3px 8px; }}"
            f"QComboBox QAbstractItemView {{ background-color: {theme.PANEL}; color: {theme.TEXT}; "
            f"selection-background-color: {theme.ACCENT}; border: 1px solid {theme.BORDER}; }}"
        )
        self._preset_combo.currentTextChanged.connect(self._on_preset_selected)
        conn_row.addWidget(self._preset_combo)
        conn_row.addStretch(1)

        outer.addLayout(conn_row)

        # ── Action row ────────────────────────────────────────────────────────
        # Start/Stop/Restart styled identically across the whole suite: the
        # app-wide default QPushButton look (no accent override), consistent
        # 110px minimum width, and the same ▶ ■ ↺ icon set as OSC-Chatbox.
        btn_row = QHBoxLayout()

        for text, cmd in (
                ("▶  Start",   self._start_connection),
                ("■  Stop",    lambda: self._stop_connection()),
                ("↺  Restart", self._restart_connection),
        ):
            b = QPushButton(text)
            b.setFont(theme.qt_font(10, bold=True))
            b.setMinimumWidth(110)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(cmd)
            btn_row.addWidget(b)

        self._start_btn = btn_row.itemAt(0).widget()
        self._stop_btn = btn_row.itemAt(1).widget()
        self._restart_btn = btn_row.itemAt(2).widget()

        reset_btn = QPushButton("Reset All")
        reset_btn.setStyleSheet(theme.accent_button_qss())
        reset_btn.setFont(theme.qt_font(9, bold=True))
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_all)
        btn_row.addWidget(reset_btn)

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

        # ── Category sub-tabs ─────────────────────────────────────────────────
        self._sub_tabs = QTabWidget()
        self._sub_tabs.setDocumentMode(True)
        self._sub_tabs.setStyleSheet(
            f"QTabBar::tab {{ background: {theme.PANEL}; color: {theme.SUBTEXT}; padding: 6px 12px; "
            f"border: none; font-weight: bold; }}"
            f"QTabBar::tab:selected {{ background: {theme.PANEL}; color: {theme.ACCENT2}; }}"
            f"QTabWidget::pane {{ border: none; background: {theme.BG}; }}"
        )
        for category, params in FACE_PARAMS.items():
            self._sub_tabs.addTab(self._build_category_tab(params), category)
        outer.addWidget(self._sub_tabs, 1)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 6, 12, 6)

        self._status_lbl = QLabel("Status: Stopped")
        self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        self._status_lbl.setFont(theme.qt_font(9))
        footer_layout.addWidget(self._status_lbl)
        footer_layout.addStretch(1)

        self._footer_detail = QLabel("Stopped")
        self._footer_detail.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        self._footer_detail.setFont(theme.qt_font(8))
        footer_layout.addWidget(self._footer_detail)

        outer.addWidget(footer)

    def _build_category_tab(self, params) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background-color: {theme.BG}; border: none;")

        inner = QWidget()
        inner.setStyleSheet(f"background-color: {theme.BG};")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(4, 6, 4, 6)
        inner_layout.setSpacing(0)

        for name, lo, hi, default in params:
            inner_layout.addWidget(self._build_slider_row(name, lo, hi, default))
            divider = QFrame()
            divider.setFixedHeight(1)
            divider.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
            inner_layout.addWidget(divider)

        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _build_slider_row(self, name: str, lo: float, hi: float, default: float) -> QWidget:
        row = QWidget()
        row.setStyleSheet(f"background-color: {theme.BG}; border: none;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 4, 10, 4)

        name_chip = theme.TextChip(name, fg=theme.TEXT, padding="2px 6px")
        name_chip.setFont(theme.qt_font(9))
        name_chip.setFixedWidth(180)
        row_layout.addWidget(name_chip)
        self._chips.append(name_chip)

        lo_lbl = QLabel(f"{lo:.1f}")
        lo_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        lo_lbl.setFont(theme.qt_font(8))
        lo_lbl.setFixedWidth(28)
        row_layout.addWidget(lo_lbl)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(SLIDER_STEPS)
        slider.setValue(_pos_for_value(default, lo, hi))
        slider.setFixedWidth(220)
        slider.setCursor(Qt.PointingHandCursor)
        slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ background: #252535; height: 4px; border: none; }}"
            f"QSlider::handle:horizontal {{ background: {theme.ACCENT2}; width: 14px; "
            f"margin: -6px 0; border-radius: 7px; border: none; }}"
        )
        row_layout.addWidget(slider)

        hi_lbl = QLabel(f"{hi:.1f}")
        hi_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        hi_lbl.setFont(theme.qt_font(8))
        hi_lbl.setFixedWidth(28)
        row_layout.addWidget(hi_lbl)

        val_lbl = QLabel(f"{default:.3f}")
        val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        val_lbl.setStyleSheet(
            f"color: {theme.ACCENT2}; background-color: {theme.PANEL}; padding: 1px 4px; border: none;"
        )
        val_lbl.setFont(theme.qt_font(9))
        val_lbl.setFixedWidth(55)
        row_layout.addWidget(val_lbl)

        reset_btn = QPushButton("↺")
        reset_btn.setStyleSheet(
            f"QPushButton {{ background-color: {theme.PANEL}; color: {theme.SUBTEXT}; "
            f"border: none; padding: 2px 6px; }}"
            f"QPushButton:hover {{ background-color: {theme.BORDER}; color: {theme.TEXT}; }}"
        )
        reset_btn.setFont(theme.qt_font(9, bold=True))
        reset_btn.setCursor(Qt.PointingHandCursor)
        row_layout.addWidget(reset_btn)

        row_layout.addStretch(1)

        def on_change(pos, n=name, l=lo, h=hi, vl=val_lbl):
            val = round(_value_for_pos(pos, l, h), 3)
            vl.setText(f"{val:.3f}")
            self._send(n, val)

        slider.valueChanged.connect(on_change)

        def do_reset(_checked=False, s=slider, l=lo, h=hi, d=default):
            s.setValue(_pos_for_value(d, l, h))

        reset_btn.clicked.connect(do_reset)

        self._sliders[name] = {"slider": slider, "lo": lo, "hi": hi, "default": default}
        return row

    # ── Preset / prefix ───────────────────────────────────────────────────────

    def _on_preset_selected(self, text: str):
        if text in PREFIX_PRESETS:
            self._prefix_entry.setText(PREFIX_PRESETS[text])

    # ── Connection ────────────────────────────────────────────────────────────

    def _start_connection(self):
        ip = self._ip_entry.text().strip() or DEFAULT_OSC_IP
        port_text = self._port_entry.text().strip() or DEFAULT_OSC_PORT
        prefix = normalize_prefix(self._prefix_entry.text())
        self._ip_entry.setText(ip)
        self._port_entry.setText(port_text)
        self._prefix_entry.setText(prefix)

        try:
            port = int(port_text)
            if not (1 <= port <= 65535):
                raise ValueError("Port must be between 1 and 65535")

            self._client.connect(ip, port)
            self._port_entry.setText(str(port))

            self._cfg["osc_ip"]     = ip
            self._cfg["osc_port"]   = str(port)
            self._cfg["osc_prefix"] = prefix
            self._save_cb()

            self._set_status(True, f"{ip}:{port}")
        except Exception as exc:
            self._client.disconnect()
            self._set_status(False, str(exc))

    def _stop_connection(self, set_status: bool = True):
        self._client.disconnect()
        if set_status:
            self._set_stopped()
        else:
            self._notify_status_listeners()

    def _restart_connection(self):
        self._stop_connection(set_status=False)
        QTimer.singleShot(1200, self._start_connection)

    def _send(self, param: str, value: float):
        self._client.send(self._prefix_entry.text(), param, value)

    def _set_status(self, ok: bool, detail: str = ""):
        if ok:
            self._status_lbl.setText("Status: Running")
            self._status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
            self._footer_detail.setText("Running")
        else:
            self._status_lbl.setText("Status: Error")
            self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
            self._footer_detail.setText(f"Error: {detail}" if detail else "Error")
        self._notify_status_listeners()

    def _set_stopped(self):
        self._status_lbl.setText("Status: Stopped")
        self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        self._footer_detail.setText("Stopped")
        self._notify_status_listeners()

    def _notify_status_listeners(self):
        """Start/Stop/Restart are always clickable — clicking Start while
        already connected, or Stop while already stopped, is a harmless
        no-op, same as every other tool in the suite. This just fans the
        status change out to listeners (the Stretch Face tab's chip)."""
        for listener in self._status_listeners:
            listener()

    def add_status_listener(self, callback):
        """Register a callback (no args) to be invoked whenever the
        connection status changes — used by the Stretch Face tab to
        keep its own "sending live" / "not connected" chip in sync."""
        self._status_listeners.append(callback)

    def _reset_all(self):
        for name, info in self._sliders.items():
            info["slider"].setValue(_pos_for_value(info["default"], info["lo"], info["hi"]))

    # ── Public API (used by StretchTab) ──────────────────────────────────────

    def is_connected(self) -> bool:
        return self._client.connected

    def send_param(self, param: str, value: float):
        """Send a single parameter through this tab's OSC connection.
        Used by StretchTab so dragging a face handle sends through the
        same client Start/Stop already controls, instead of opening a
        second one."""
        self._send(param, value)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def destroy_client(self):
        self._client.disconnect()