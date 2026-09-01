"""
ui/dev_menu.py
──────────────
Developer menu modal: testing tools and internal diagnostics.

Structure mirrors settings_dialog.py — scrollable area with a fixed
header. Opened from the Settings dialog when Testing Mode is enabled.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame,
)

from core.state import AppState
from ui import theme
from ui.circle_toggle import CircleToggle
from ui.theme import qt_font, accent_button_qss


def open_dev_menu(parent, state: AppState, cfg: dict, save_cb):
    win = QDialog(parent)
    win.setWindowTitle("Dev Menu")
    win.setStyleSheet(f"background-color: {theme.BG}; border: none;")
    win.resize(parent.size())

    root = QVBoxLayout(win)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    # ── Header (fixed, outside scroll) ───────────────────────────────────────
    hdr = QWidget()
    hdr.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
    hdr_layout = QHBoxLayout(hdr)
    hdr_layout.setContentsMargins(16, 10, 16, 10)
    title = QLabel("Dev Menu")
    title.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    title.setFont(qt_font(12, bold=True))
    hdr_layout.addWidget(title)
    hdr_layout.addStretch(1)
    root.addWidget(hdr)

    divider = QFrame()
    divider.setFixedHeight(1)
    divider.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
    root.addWidget(divider)

    # ── Scrollable area ───────────────────────────────────────────────────────
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")

    inner = QWidget()
    inner.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
    inner_layout = QVBoxLayout(inner)
    inner_layout.setContentsMargins(0, 0, 0, 0)
    inner_layout.setSpacing(0)

    scroll.setWidget(inner)
    root.addWidget(scroll, 1)

    # ── Section helper ────────────────────────────────────────────────────────
    def section(label):
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {theme.ACCENT2}; background-color: {theme.BORDER}; padding: 3px 10px; border-radius: 3px;")
        lbl.setFont(qt_font(10, bold=True))
        lbl.setAlignment(Qt.AlignHCenter)
        inner_layout.addSpacing(16)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(lbl)
        row.addStretch(1)
        inner_layout.addLayout(row)

    # ══════════════════════════════════════════════════════════════════════════
    # Dev sections go here
    # ══════════════════════════════════════════════════════════════════════════

    section("Fake Data Mode")

    fake_frame = QWidget()
    fake_frame.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
    fake_layout = QHBoxLayout(fake_frame)
    fake_layout.setContentsMargins(24, 4, 24, 4)

    fake_label = QLabel("Broadcast fake hardware/VR/VRChat/media data")
    fake_label.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
    fake_label.setFont(qt_font(9))
    fake_layout.addWidget(fake_label)
    fake_layout.addStretch(1)

    fake_toggle = CircleToggle(enabled=bool(getattr(state, "fake_data", False)), color=theme.ACCENT2)

    def _fake_data_changed(checked):
        state.fake_data = bool(checked)
        # Deliberately no save_cb() here — this is session-only, same as
        # Testing Mode, so it can't accidentally stay on for a real session
        # after the app restarts.

    fake_toggle.toggled.connect(_fake_data_changed)
    fake_layout.addWidget(fake_toggle)
    inner_layout.addWidget(fake_frame)

    fake_hint = QLabel(
        "Replaces every live reading — CPU/GPU temps, load, power, VRAM, "
        "SteamVR telemetry, VRChat world/player/avatar, media track, "
        "weather, and network throughput — with smoothly oscillating fake "
        "values. Useful for testing pages/layouts without real hardware, a "
        "headset, or VRChat running.\n\n"
        "Takes effect on the very next tick while the loop is already "
        "running. CPU/GPU names only refresh on Stop \u2192 Start, same as "
        "real detection normally would."
    )
    fake_hint.setWordWrap(True)
    fake_hint.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    fake_hint.setFont(qt_font(8))
    fake_hint.setContentsMargins(24, 0, 24, 8)
    inner_layout.addWidget(fake_hint)

    section("Developer Tools")

    placeholder = QLabel("More dev tools and diagnostics will appear here.")
    placeholder.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    placeholder.setFont(qt_font(9))
    placeholder.setContentsMargins(24, 0, 24, 8)
    inner_layout.addWidget(placeholder)

    # ── Action buttons ────────────────────────────────────────────────────────
    section("Actions")

    btn_frame = QWidget()
    btn_frame.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
    btn_layout = QHBoxLayout(btn_frame)
    btn_layout.setContentsMargins(16, 12, 16, 12)
    btn_layout.addStretch(1)

    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(accent_button_qss())
    close_btn.setFont(qt_font(9, bold=True))
    close_btn.clicked.connect(win.close)
    btn_layout.addWidget(close_btn)

    inner_layout.addWidget(btn_frame)
    inner_layout.addStretch(1)

    win.exec()