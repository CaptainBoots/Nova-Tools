"""
ui/settings_dialog.py
──────────────────────
Settings modal for OSC-Gamepad.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox,
)

from ui.circle_toggle import CircleToggle
from ui import theme
from ui.theme import THEMES, THEME_LABELS, colour_mode


def _section_label(parent_layout, text):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    lbl.setFont(theme.qt_font(10, bold=True))
    lbl.setAlignment(Qt.AlignHCenter)
    parent_layout.addSpacing(12)
    parent_layout.addWidget(lbl)


def open_settings(parent, cfg: dict, save_cb, reset_cb, theme_cb):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Settings")
    dlg.resize(parent.size())

    root = QVBoxLayout(dlg)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    # ── Header ────────────────────────────────────────────────────────────
    hdr = QWidget()
    hdr.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
    hdr_layout = QHBoxLayout(hdr)
    hdr_layout.setContentsMargins(16, 10, 16, 10)
    title = QLabel("Settings")
    title.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    title.setFont(theme.qt_font(12, bold=True))
    hdr_layout.addWidget(title)
    hdr_layout.addStretch(1)
    root.addWidget(hdr)

    divider = QFrame()
    divider.setFixedHeight(1)
    divider.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
    root.addWidget(divider)

    # ── Scroll area ───────────────────────────────────────────────────────
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
    inner = QWidget()
    inner.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
    inner_layout = QVBoxLayout(inner)
    inner_layout.setContentsMargins(20, 10, 20, 10)
    scroll.setWidget(inner)
    root.addWidget(scroll, 1)

    # ── Themes (collapsible, collapsed by default) ────────────────────────
    theme_header = QWidget()
    theme_header.setCursor(Qt.PointingHandCursor)
    theme_header_layout = QHBoxLayout(theme_header)
    theme_header_layout.setContentsMargins(0, 8, 0, 0)

    arrow_lbl = QLabel("▶")
    arrow_lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    arrow_lbl.setFont(theme.qt_font(12, bold=True))
    theme_header_layout.addWidget(arrow_lbl)

    themes_lbl = QLabel("  Themes")
    themes_lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    themes_lbl.setFont(theme.qt_font(12, bold=True))
    theme_header_layout.addWidget(themes_lbl)

    preview_lbl = QLabel(f"({THEME_LABELS.get(cfg.get('theme_mode', colour_mode), '')})")
    preview_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    preview_lbl.setFont(theme.qt_font(9))
    theme_header_layout.addWidget(preview_lbl)
    theme_header_layout.addStretch(1)

    inner_layout.addWidget(theme_header)

    restart_lbl = QLabel("Restart required to apply")
    restart_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    restart_lbl.setFont(theme.qt_font(8))
    inner_layout.addWidget(restart_lbl)
    restart_lbl.hide()

    theme_body = QWidget()
    theme_body_layout = QVBoxLayout(theme_body)
    theme_body_layout.setContentsMargins(20, 4, 0, 0)
    inner_layout.addWidget(theme_body)
    theme_body.hide()

    current_theme = cfg.get("theme_mode", colour_mode)
    theme_state = {"selected": current_theme}
    theme_rows = []

    def _refresh_theme_rows():
        for row_data in theme_rows:
            is_sel = row_data["mode"] == theme_state["selected"]
            row_data["toggle"].set(is_sel)
            row_data["label"].setStyleSheet(
                f"color: {theme.ACCENT2 if is_sel else theme.TEXT}; background: transparent; border: none;"
            )

    def _select_theme(mode):
        theme_state["selected"] = mode
        _refresh_theme_rows()
        preview_lbl.setText(f"({THEME_LABELS.get(mode, mode)})")
        theme_cb(mode)

    for mode, label_text in THEME_LABELS.items():
        row = QWidget()
        row.setCursor(Qt.PointingHandCursor)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 3, 0, 3)

        toggle = CircleToggle(enabled=(mode == current_theme), color=theme.ACCENT)
        row_layout.addWidget(toggle)

        lbl = QLabel(label_text)
        lbl.setFont(theme.qt_font(9))
        row_layout.addWidget(lbl)

        swatch = QWidget()
        swatch_layout = QHBoxLayout(swatch)
        swatch_layout.setContentsMargins(4, 0, 0, 0)
        swatch_layout.setSpacing(1)
        for colour_key in ("BG", "PANEL", "ACCENT", "ACCENT2"):
            sw = QFrame()
            sw.setFixedSize(14, 14)
            sw.setStyleSheet(
                f"background-color: {THEMES[mode][colour_key]}; border: 1px solid {theme.BORDER};"
            )
            swatch_layout.addWidget(sw)
        row_layout.addWidget(swatch)
        row_layout.addStretch(1)

        def _mk_click(m):
            def _handler(_evt):
                _select_theme(m)
            return _handler

        row.mousePressEvent = _mk_click(mode)
        toggle.toggled.connect(lambda _checked, m=mode: _select_theme(m))

        theme_rows.append({"mode": mode, "toggle": toggle, "label": lbl})
        theme_body_layout.addWidget(row)

    _refresh_theme_rows()

    _theme_open = {"value": False}

    def _toggle_theme_body(_evt=None):
        _theme_open["value"] = not _theme_open["value"]
        if _theme_open["value"]:
            arrow_lbl.setText("▼")
            restart_lbl.show()
            theme_body.show()
        else:
            arrow_lbl.setText("▶")
            restart_lbl.hide()
            theme_body.hide()

    theme_header.mousePressEvent = _toggle_theme_body

    # ── Config reset ──────────────────────────────────────────────────────
    _section_label(inner_layout, "Config")
    reset_row = QHBoxLayout()
    reset_row.addStretch(1)
    reset_btn = QPushButton("Reset to Defaults")
    reset_btn.setStyleSheet(theme.subtle_button_qss())
    reset_btn.setFont(theme.qt_font(9, bold=True))

    def _do_reset_confirm():
        if QMessageBox.question(dlg, "Reset", "Reset all settings to defaults?") == QMessageBox.Yes:
            reset_cb()

    reset_btn.clicked.connect(_do_reset_confirm)
    reset_row.addWidget(reset_btn)
    reset_row.addStretch(1)
    inner_layout.addLayout(reset_row)

    # ── Actions ───────────────────────────────────────────────────────────
    _section_label(inner_layout, "Actions")

    def _trigger_reset():
        if QMessageBox.question(
                dlg, "Reset", "Are you sure you want to restore default values?"
        ) == QMessageBox.Yes:
            reset_cb()
            dlg.close()

    btn_row = QHBoxLayout()
    btn_row.setContentsMargins(0, 12, 0, 12)

    restore_btn = QPushButton("Restore Defaults")
    restore_btn.setFont(theme.qt_font(9))
    restore_btn.clicked.connect(_trigger_reset)
    btn_row.addWidget(restore_btn)
    btn_row.addStretch(1)

    close_btn = QPushButton("Close Settings")
    close_btn.setStyleSheet(theme.accent_button_qss())
    close_btn.setFont(theme.qt_font(9, bold=True))
    close_btn.clicked.connect(dlg.close)
    btn_row.addWidget(close_btn)

    inner_layout.addLayout(btn_row)
    inner_layout.addSpacing(20)

    dlg.exec()
