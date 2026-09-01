"""
ui/settings_dialog.py
──────────────────────────
Same sections, same order as the original Tk version:
  Themes (collapsible) → Background Transparency → Config reset →
  Progress Bar Characters → Features → Libre Hardware Monitor → Actions
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QCheckBox, QRadioButton, QSlider, QScrollArea,
    QMessageBox, QFrame, QButtonGroup,
)

from config import normalize_char
from core.state import SLOW_SLEEP, SPEED_SLEEP
from core.state import DEFAULT_PROGRESS_FILLED, DEFAULT_PROGRESS_BORDER, DEFAULT_PROGRESS_EMPTY
from ui.circle_toggle import CircleToggle
from ui.dev_menu import open_dev_menu
from ui.media_priority_section import build_priority_list
from ui.spotify_section import build_spotify_section
from ui import theme
from ui.theme import THEMES, THEME_LABELS, colour_mode


def _section_label(parent_layout, text):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    lbl.setFont(theme.qt_font(10, bold=True))
    lbl.setAlignment(Qt.AlignHCenter)
    parent_layout.addSpacing(12)
    parent_layout.addWidget(lbl)


def _hline(parent_layout):
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
    parent_layout.addWidget(line)


def open_settings(parent, state, cfg: dict, save_cb, reset_cb, theme_cb, opacity_cb, spotify_ctx):
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
    _hline(root)

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

    # ── Themes (collapsible) ─────────────────────────────────────────────
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
                f"color: {theme.ACCENT2 if is_sel else theme.TEXT}; background: transparent;"
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

    # ── Media (collapsible) ───────────────────────────────────────────────
    # Same collapsed-by-default pattern as Themes above — Player Priority
    # (reorderable list) and Spotify (connect/disconnect) both live inside
    # this one section since they're both "how media info gets picked",
    # not two separate concerns.
    media_header = QWidget()
    media_header.setCursor(Qt.PointingHandCursor)
    media_header_layout = QHBoxLayout(media_header)
    media_header_layout.setContentsMargins(0, 8, 0, 0)

    media_arrow_lbl = QLabel("▶")
    media_arrow_lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    media_arrow_lbl.setFont(theme.qt_font(12, bold=True))
    media_header_layout.addWidget(media_arrow_lbl)

    media_lbl = QLabel("  Media")
    media_lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    media_lbl.setFont(theme.qt_font(12, bold=True))
    media_header_layout.addWidget(media_lbl)
    media_header_layout.addStretch(1)

    inner_layout.addWidget(media_header)

    media_body = QWidget()
    media_body_layout = QVBoxLayout(media_body)
    media_body_layout.setContentsMargins(20, 4, 0, 0)
    inner_layout.addWidget(media_body)
    media_body.hide()

    priority_heading = QLabel("Player Priority")
    priority_heading.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
    priority_heading.setFont(theme.qt_font(9, bold=True))
    media_body_layout.addWidget(priority_heading)

    build_priority_list(media_body_layout, cfg, save_cb)

    media_body_layout.addSpacing(16)
    _hline(media_body_layout)
    media_body_layout.addSpacing(8)

    spotify_heading = QLabel("Spotify")
    spotify_heading.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
    spotify_heading.setFont(theme.qt_font(9, bold=True))
    media_body_layout.addWidget(spotify_heading)

    build_spotify_section(media_body_layout, dlg, cfg, save_cb, spotify_ctx)

    def _toggle_media_body(_evt=None):
        if media_body.isVisible():
            media_arrow_lbl.setText("▶")
            media_body.hide()
        else:
            media_arrow_lbl.setText("▼")
            media_body.show()

    media_header.mousePressEvent = _toggle_media_body

    # ── Background Transparency slider ───────────────────────────────────
    inner_layout.addSpacing(20)  # was a spacing-only _section_label("") call
    trans_label = QLabel("Background Brightness")
    trans_label.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
    trans_label.setFont(theme.qt_font(9, bold=True))
    inner_layout.addWidget(trans_label)

    trans_hint = QLabel("Only affects the chatbox and builder page.")
    trans_hint.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    trans_hint.setFont(theme.qt_font(8))
    trans_hint.setWordWrap(True)
    inner_layout.addWidget(trans_hint)

    current_alpha = cfg.get("transparency_opacity", 1.0)
    opacity_slider = QSlider(Qt.Horizontal)
    opacity_slider.setStyleSheet(f"""
        QSlider::groove:horizontal {{
            height: 6px;
            background: {theme.BORDER};
            border-radius: 3px;
        }}
        QSlider::sub-page:horizontal {{
            background: {theme.ACCENT2};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {theme.ACCENT};
            width: 14px;
            height: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }}
    """)
    opacity_slider.setMinimum(20)   # Qt can go lower than Tk's 30% floor safely —
    opacity_slider.setMaximum(100)  # widgets stay opaque/clickable at any level.
    opacity_slider.setValue(int(current_alpha * 100))

    def _on_slider_change(val):
        alpha_val = val / 100.0
        opacity_cb(alpha_val)

    opacity_slider.valueChanged.connect(_on_slider_change)
    inner_layout.addWidget(opacity_slider)

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

    # ── Progress bar characters ──────────────────────────────────────────
    _section_label(inner_layout, "Progress Bar Characters")
    chars_row = QHBoxLayout()
    chars_row.addStretch(1)
    chars_grid = QGridLayout()

    entries = []
    for col, (lbl_text, val) in enumerate((
            ("Filled", state.progress_filled),
            ("Border", state.progress_border),
            ("Empty",  state.progress_empty),
    )):
        cap = QLabel(lbl_text)
        cap.setAlignment(Qt.AlignHCenter)
        cap.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        cap.setFont(theme.qt_font(8))
        chars_grid.addWidget(cap, 0, col)

        e = QLineEdit(val)
        e.setFixedWidth(40)
        e.setAlignment(Qt.AlignHCenter)
        e.setFont(theme.qt_font(9))
        chars_grid.addWidget(e, 1, col)
        entries.append(e)

    chars_row.addLayout(chars_grid)
    chars_row.addStretch(1)
    inner_layout.addLayout(chars_row)

    preview_row = QHBoxLayout()
    preview_row.addStretch(1)
    previews = []
    for ch, color in (
            (state.progress_filled, theme.TEXT),
            (state.progress_border, theme.TEXT),
            (state.progress_empty,  theme.ACCENT2),
    ):
        p = QLabel(ch * 8)
        p.setStyleSheet(f"color: {color}; background-color: {theme.BORDER}; padding: 2px 4px; border: none;")
        p.setFont(theme.qt_font(10))
        preview_row.addWidget(p)
        previews.append(p)
    preview_row.addStretch(1)
    inner_layout.addLayout(preview_row)

    def _apply_chars():
        state.progress_filled = normalize_char(entries[0].text(), DEFAULT_PROGRESS_FILLED)
        state.progress_border = normalize_char(entries[1].text(), DEFAULT_PROGRESS_BORDER)
        state.progress_empty  = normalize_char(entries[2].text(), DEFAULT_PROGRESS_EMPTY)
        for entry, ch in zip(entries, (state.progress_filled, state.progress_border, state.progress_empty)):
            if entry.text() != ch:
                entry.setText(ch)
        for prev, ch in zip(previews, (state.progress_filled, state.progress_border, state.progress_empty)):
            prev.setText(ch * 8)
        save_cb()

    for e in entries:
        e.textChanged.connect(lambda _t: _apply_chars())
        e.editingFinished.connect(_apply_chars)

    # ── Feature flags ─────────────────────────────────────────────────────
    _section_label(inner_layout, "Features")

    flags = [
        ("Trim Media Titles", "media_title_trim", "Removes words like official, lyrics, video"),
        ("Slow Mode",         "slow_mode",        f"Sets update interval to {SLOW_SLEEP:.0f}s"),
        ("Speed Mode",        "speed_mode",       f"Sets update interval to {SPEED_SLEEP:.1f}s"),
        ("Testing Mode",      "testing",          "Enables dev testing"),
    ]

    def _refresh_dev_btn():
        pass  # reassigned below once dev_btn exists

    for label, attr, hint in flags:
        cb = QCheckBox(label)
        cb.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
        cb.setFont(theme.qt_font(9))
        cb.setChecked(bool(getattr(state, attr, False)))

        def _changed(checked, a=attr):
            setattr(state, a, bool(checked))
            save_cb()
            _refresh_dev_btn()

        cb.toggled.connect(_changed)
        inner_layout.addWidget(cb)

        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; margin-left: 20px; border: none;")
        hint_lbl.setFont(theme.qt_font(8))
        inner_layout.addWidget(hint_lbl)

    # ── LHM startup preference ───────────────────────────────────────────
    _section_label(inner_layout, "Libre Hardware Monitor")

    lhm_options = [
        ("always", "Always start LHM on launch"),
        ("ask",    "Ask every time"),
        ("never",  "Never start / don't ask"),
    ]
    lhm_group = QButtonGroup(dlg)
    current_lhm = cfg.get("lhm_prompt", "ask")

    def _lhm_changed(value):
        cfg["lhm_prompt"] = value
        save_cb()

    for value, label_text in lhm_options:
        rb = QRadioButton(label_text)
        rb.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
        rb.setFont(theme.qt_font(9))
        rb.setCursor(Qt.PointingHandCursor)
        rb.setChecked(value == current_lhm)
        rb.toggled.connect(lambda checked, v=value: _lhm_changed(v) if checked else None)
        lhm_group.addButton(rb)
        inner_layout.addWidget(rb)

    # ── Actions ───────────────────────────────────────────────────────────
    _section_label(inner_layout, "Actions")

    btn_row = QHBoxLayout()

    def _trigger_reset():
        if QMessageBox.question(
                dlg, "Reset", "Are you sure you want to restore default values?"
        ) == QMessageBox.Yes:
            reset_cb()
            dlg.close()

    restore_btn = QPushButton("Restore Defaults")
    restore_btn.setFont(theme.qt_font(9))
    restore_btn.clicked.connect(_trigger_reset)
    btn_row.addWidget(restore_btn)

    dev_btn = QPushButton("Dev Menu")
    dev_btn.setStyleSheet(f"color: {theme.ACCENT2}; font-weight: bold; border: none;")
    dev_btn.setFont(theme.qt_font(9, bold=True))
    dev_btn.clicked.connect(lambda: open_dev_menu(dlg, state, cfg, save_cb))

    def _refresh_dev_btn_impl():
        dev_btn.setVisible(bool(getattr(state, "testing", False)))

    _refresh_dev_btn = _refresh_dev_btn_impl
    _refresh_dev_btn()
    btn_row.addWidget(dev_btn)

    btn_row.addStretch(1)

    close_btn = QPushButton("Close Settings")
    close_btn.setStyleSheet(theme.accent_button_qss())
    close_btn.setFont(theme.qt_font(9, bold=True))
    close_btn.clicked.connect(dlg.close)
    btn_row.addWidget(close_btn)

    inner_layout.addLayout(btn_row)
    inner_layout.addSpacing(20)

    dlg.exec()