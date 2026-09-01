"""
ui/pad_card.py
──────────────
PadCard: one pad's config row (name, host, port, style, connect)
plus its active pad area (NES / Joystick).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QButtonGroup,
)

from core.pad_state import PadState
from ui import theme
from ui.widgets import NESPad, JoystickPad


class PadCard(QFrame):
    def __init__(self, index: int, on_remove, host="127.0.0.1", port="9000",
                 style="nes", name="", parent=None):
        super().__init__(parent)
        self.index     = index
        self.on_remove = on_remove
        self.state: PadState | None = None

        self._default_host  = host
        self._default_port  = str(port)
        self._default_style = style
        self._default_name  = name or f"Pad {index}"
        self._connected     = False

        self.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()

        icon = QLabel("◈")
        icon.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
        icon.setFont(theme.qt_font(10, bold=True))
        hdr.addWidget(icon)

        self._name_entry = QLineEdit(self._default_name)
        self._name_entry.setFixedWidth(160)
        self._name_entry.setFont(theme.qt_font(10, bold=True))
        self._name_entry.setStyleSheet(
            f"QLineEdit {{ background-color: {theme.PANEL}; color: {theme.ACCENT2}; "
            f"border: none; padding: 1px 4px; }}"
        )
        hdr.addWidget(self._name_entry)
        hdr.addStretch(1)

        rm_btn = QLabel("✕")
        rm_btn.setCursor(Qt.PointingHandCursor)
        rm_btn.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        rm_btn.setFont(theme.qt_font(10))
        rm_btn.mousePressEvent = lambda _e: self.on_remove(self)
        hdr.addWidget(rm_btn)

        outer.addLayout(hdr)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
        outer.addWidget(divider)

        # ── Config row ────────────────────────────────────────────────────────
        cfg_row = QHBoxLayout()

        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
            l.setFont(theme.qt_font(8))
            cfg_row.addWidget(l)

        def entry(default, width):
            e = QLineEdit(default)
            e.setFixedWidth(width)
            e.setFont(theme.qt_font(9))
            e.setStyleSheet(theme.line_edit_qss())
            cfg_row.addWidget(e)
            return e

        lbl("Host:")
        self._host = entry(self._default_host, 100)
        cfg_row.addSpacing(6)
        lbl("Port:")
        self._port = entry(self._default_port, 50)
        cfg_row.addSpacing(6)

        self._style_group = QButtonGroup(self)
        self._style_buttons = {}
        for val, txt in (("nes", "NES"), ("joy", "Joystick")):
            rb = QRadioButton(txt)
            rb.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
            rb.setFont(theme.qt_font(8))
            rb.setCursor(Qt.PointingHandCursor)
            rb.setChecked(val == self._default_style)
            rb.toggled.connect(lambda checked, v=val: self._rebuild_pad() if checked else None)
            self._style_group.addButton(rb)
            self._style_buttons[val] = rb
            cfg_row.addWidget(rb)

        cfg_row.addSpacing(8)

        self._conn_btn = QPushButton("Connect")
        self._conn_btn.setCursor(Qt.PointingHandCursor)
        self._conn_btn.setFont(theme.qt_font(8, bold=True))
        self._set_connect_style(connected=False)
        self._conn_btn.clicked.connect(self._toggle_connect)
        cfg_row.addWidget(self._conn_btn)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        self._status_dot.setFont(theme.qt_font(10))
        cfg_row.addWidget(self._status_dot)
        cfg_row.addStretch(1)

        outer.addLayout(cfg_row)

        # ── Pad area ──────────────────────────────────────────────────────────
        self._pad_area = QVBoxLayout()
        self._pad_area.setContentsMargins(4, 0, 4, 8)
        outer.addLayout(self._pad_area)
        self._pad_widget = None
        self._show_placeholder()

    # ── Style helpers ─────────────────────────────────────────────────────────

    def _set_connect_style(self, connected: bool):
        if connected:
            self._conn_btn.setText("Disconnect")
            self._conn_btn.setStyleSheet(
                f"QPushButton {{ background-color: {theme.RED}; color: {theme.BG}; border: none; padding: 3px 8px; }}"
            )
        else:
            self._conn_btn.setText("Connect")
            self._conn_btn.setStyleSheet(
                f"QPushButton {{ background-color: {theme.ACCENT}; color: {theme.BG}; border: none; padding: 3px 8px; }}"
                f"QPushButton:hover {{ background-color: {theme.ACCENT2}; }}"
            )

    def _clear_pad_area(self):
        while self._pad_area.count():
            item = self._pad_area.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._pad_widget = None

    def _show_placeholder(self):
        self._clear_pad_area()
        placeholder = QLabel("Press Connect to activate")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        placeholder.setFont(theme.qt_font(8))
        placeholder.setContentsMargins(0, 16, 0, 16)
        self._pad_area.addWidget(placeholder)

    # ── Connection ────────────────────────────────────────────────────────────

    def _toggle_connect(self):
        self._disconnect() if self._connected else self._connect()

    def _connect(self):
        host = self._host.text().strip()
        try:
            port = int(self._port.text().strip())
        except ValueError:
            self._status_dot.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
            return

        if self.state:
            self.state.stop()

        self.state = PadState(host, port)
        self._connected = True
        self._status_dot.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
        self._set_connect_style(connected=True)
        self._rebuild_pad()

    def _disconnect(self):
        if self.state:
            self.state.stop()
            self.state = None
        self._connected = False
        self._status_dot.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        self._set_connect_style(connected=False)
        self._show_placeholder()

    def _rebuild_pad(self):
        if not self.state:
            return
        self._clear_pad_area()
        style = "nes" if self._style_buttons["nes"].isChecked() else "joy"
        cls = NESPad if style == "nes" else JoystickPad
        self._pad_widget = cls(self.state)
        self._pad_area.addWidget(self._pad_widget)
        # Adding a widget to an already-materialized layout queues a
        # layout/show pass for the next event loop iteration — pump it now
        # so the pad controls appear immediately rather than needing an
        # extra redraw before becoming visible.
        from PySide6.QtWidgets import QApplication
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.processEvents()

    # ── Config I/O ────────────────────────────────────────────────────────────

    def get_config(self) -> dict:
        style = "nes" if self._style_buttons["nes"].isChecked() else "joy"
        return {
            "host":  self._host.text().strip(),
            "port":  self._port.text().strip(),
            "style": style,
            "name":  self._name_entry.text().strip(),
        }

    def destroy_state(self):
        if self.state:
            self.state.stop()