"""
ui/chatbox_tab.py
─────────────────────
Qt replacement for ui/chatbox_tab.py. Same layout and behaviour:
  - Status bar + Start/Stop/Restart/Settings/Help buttons
  - Live chatbox preview
  - Config fields (OSC IP/Port, interface, LHM URL, location)
  - Forced text override
  - Bottom bar: Discord button (bottom-left), rotating banner (bottom-centre),
    GitHub button (bottom-right) — pinned to the window edges like the Tk
    version's `.place()` calls, sitting directly on the StripeBackground so
    flag-theme stripes show in the gaps around them.
"""

import glob
import os
import webbrowser

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QPlainTextEdit, QSizePolicy, QFrame,
)

from ui import theme
from ui.theme import StripeBackground, TextChip

BANNER_DIR = "assets/banners"
BANNER_HOLD_MS = 15000
BANNER_SLIDE_MS = 500

BANNER_WIDTH  = 600
BANNER_HEIGHT = 100
ICON_SIZE = 50


def _hline(parent_layout):
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
    parent_layout.addWidget(line)


class _IconButton(QPushButton):
    """Square image button (Discord/GitHub), same footprint as the Tk version."""
    def __init__(self, icon_path: str, bg: str, hover_bg: str, url: str, size=ICON_SIZE):
        super().__init__()
        self.setFixedSize(size + 12, size + 12)
        self.setCursor(Qt.PointingHandCursor)
        if os.path.isfile(icon_path):
            self.setIcon(QIcon(QPixmap(icon_path)))
            self.setIconSize(self.size() - self.size() / 6)
        else:
            self.setText("?")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
        """)
        self.clicked.connect(lambda: webbrowser.open(url))


class _BannerRotator(QWidget):
    """Rotates through PNGs in assets/banners with a horizontal slide,
    mirroring the Tk canvas-based slide animation."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(BANNER_WIDTH, BANNER_HEIGHT)
        self.setStyleSheet(f"background-color: {theme.BG}; border: none;")

        self._paths = sorted(glob.glob(f"{BANNER_DIR}/*.png"))
        self._index = 0

        self._current = QLabel(self)
        self._current.setAlignment(Qt.AlignCenter)
        self._current.setGeometry(0, 0, BANNER_WIDTH, BANNER_HEIGHT)

        self._incoming = QLabel(self)
        self._incoming.setAlignment(Qt.AlignCenter)
        self._incoming.setGeometry(BANNER_WIDTH, 0, BANNER_WIDTH, BANNER_HEIGHT)
        self._incoming.hide()

        if not self._paths:
            self._current.setText("(no banners found in assets/banners)")
            self._current.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
            self._current.setFont(theme.qt_font(8))
        else:
            self._show_pixmap(self._current, self._paths[0])
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._advance)
            self._timer.start(BANNER_HOLD_MS)

    def _show_pixmap(self, label: QLabel, path: str):
        pix = QPixmap(path)
        if pix.isNull():
            return
        scaled = pix.scaled(BANNER_WIDTH, BANNER_HEIGHT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled)

    def _advance(self):
        if not self._paths:
            return
        self._index = (self._index + 1) % len(self._paths)
        self._show_pixmap(self._incoming, self._paths[self._index])
        self._incoming.setGeometry(BANNER_WIDTH, 0, BANNER_WIDTH, BANNER_HEIGHT)
        self._incoming.show()

        anim_cur = QPropertyAnimation(self._current, b"geometry", self)
        anim_cur.setDuration(BANNER_SLIDE_MS)
        anim_cur.setStartValue(QRect(0, 0, BANNER_WIDTH, BANNER_HEIGHT))
        anim_cur.setEndValue(QRect(-BANNER_WIDTH, 0, BANNER_WIDTH, BANNER_HEIGHT))
        anim_cur.setEasingCurve(QEasingCurve.InOutCubic)

        anim_in = QPropertyAnimation(self._incoming, b"geometry", self)
        anim_in.setDuration(BANNER_SLIDE_MS)
        anim_in.setStartValue(QRect(BANNER_WIDTH, 0, BANNER_WIDTH, BANNER_HEIGHT))
        anim_in.setEndValue(QRect(0, 0, BANNER_WIDTH, BANNER_HEIGHT))
        anim_in.setEasingCurve(QEasingCurve.InOutCubic)

        def _finish():
            self._current.setPixmap(self._incoming.pixmap())
            self._current.setGeometry(0, 0, BANNER_WIDTH, BANNER_HEIGHT)
            self._incoming.hide()

        anim_in.finished.connect(_finish)
        anim_cur.start()
        anim_in.start()
        # Keep references alive for the duration of the animation
        self._anim_cur, self._anim_in = anim_cur, anim_in


class ChatboxTab(StripeBackground):
    def __init__(self, cfg: dict, state, save_cb, start_cb, stop_cb,
                 restart_cb, settings_cb, help_cb):
        super().__init__()
        self._cfg         = cfg
        self._state       = state
        self._save_cb     = save_cb
        self._start_cb    = start_cb
        self._stop_cb     = stop_cb
        self._restart_cb  = restart_cb
        self._settings_cb = settings_cb
        self._help_cb     = help_cb
        self._entries     = {}
        self._chips       = []  # TextChip captions/labels — see set_bg_alpha override below

        self._build()

    def set_bg_alpha(self, alpha: float):
        """Override StripeBackground.set_bg_alpha to also propagate to
        every TextChip caption/label, so they fade along with the rest
        of the background instead of staying permanently opaque."""
        super().set_bg_alpha(alpha)
        for chip in self._chips:
            chip.set_bg_alpha(alpha)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        # ── Status bar ────────────────────────────────────────────────────────
        status_frame = QWidget()
        status_frame.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 6, 10, 6)

        status_caption = QLabel("Status:")
        status_caption.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        status_caption.setFont(theme.qt_font(9))
        status_layout.addWidget(status_caption)

        self._status_lbl = QLabel("Stopped")
        self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        self._status_lbl.setFont(theme.qt_font(9, bold=True))
        status_layout.addWidget(self._status_lbl)
        status_layout.addStretch(1)

        outer.addWidget(status_frame)

        # ── Control buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 4)

        for text, cmd in (
                ("▶  Start",   self._start_cb),
                ("■  Stop",    self._stop_cb),
                ("↺  Restart", self._restart_cb),
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
        _hline(outer)

        # ── Live preview ──────────────────────────────────────────────────────
        preview_caption = TextChip("Live Chatbox Preview")
        preview_caption.setFont(theme.qt_font(9, bold=True))
        outer.addWidget(preview_caption, alignment=Qt.AlignLeft)
        self._chips.append(preview_caption)

        preview_frame = QFrame()
        preview_frame.setStyleSheet(
            f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};"
        )
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFixedHeight(150)
        self._preview.setFont(theme.qt_font(10))
        # QPlainTextEdit is QFrame-derived and draws its own native frame
        # decoration (frameShape/lineWidth) as a SEPARATE mechanism from the
        # CSS "border" property — setting border:none in the stylesheet
        # doesn't fully suppress it, which left a mis-sized inner border box
        # alongside the intended outer one on preview_frame. NoFrame kills it.
        self._preview.setFrameShape(QFrame.NoFrame)
        self._preview.setStyleSheet(
            f"background-color: {theme.PANEL}; color: {theme.TEXT}; border: none; padding: 8px;"
        )
        preview_layout.addWidget(self._preview)

        self._page_lbl = QLabel("")
        self._page_lbl.setAlignment(Qt.AlignRight)
        self._page_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; padding: 0 8px 4px 0; border: none;")
        self._page_lbl.setFont(theme.qt_font(8))
        preview_layout.addWidget(self._page_lbl)

        outer.addWidget(preview_frame)
        outer.addSpacing(8)  # preview_frame's own border already separates this section — an
        # adjacent _hline() here just created a visible double-border line

        # ── Config fields ─────────────────────────────────────────────────────
        cfg_caption = TextChip("Configuration")
        cfg_caption.setFont(theme.qt_font(9, bold=True))
        outer.addWidget(cfg_caption, alignment=Qt.AlignLeft)
        self._chips.append(cfg_caption)

        cfg_grid = QGridLayout()
        cfg_grid.setContentsMargins(4, 4, 4, 4)
        cfg_grid.setColumnStretch(1, 1)
        cfg_grid.setColumnStretch(3, 1)

        fields = [
            ("OSC IP",        "osc_ip",     0, 0, 1),
            ("OSC Port",      "osc_port",   0, 2, 3),
            ("Interface",     "interface",  1, 0, 1),
            ("useless block", "temp_var1",  1, 2, 3),
            ("LHM URL",       "lhm_api",    2, 0, 1),
            ("Location",      "location",   2, 2, 3),
        ]

        for label, key, r, cl, ce in fields:
            lbl = TextChip(label, fg=theme.SUBTEXT, padding="2px 6px")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl.setFont(theme.qt_font(9))
            cfg_grid.addWidget(lbl, r, cl)
            self._chips.append(lbl)

            entry = QLineEdit(str(self._cfg.get(key, "")))
            entry.setFont(theme.qt_font(9))
            cfg_grid.addWidget(entry, r, ce)
            self._entries[key] = entry

            def _on_change(k=key, e=entry):
                self._cfg[k] = e.text()
                self._save_cb()

            entry.editingFinished.connect(_on_change)

        outer.addLayout(cfg_grid)
        _hline(outer)

        # ── Forced text ───────────────────────────────────────────────────────
        forced_caption = TextChip("Forced Text (overrides all pages)")
        forced_caption.setFont(theme.qt_font(9, bold=True))
        outer.addWidget(forced_caption, alignment=Qt.AlignLeft)
        self._chips.append(forced_caption)

        self._forced_entry = QLineEdit()
        self._forced_entry.setFont(theme.qt_font(10))
        outer.addWidget(self._forced_entry)

        hint = QLabel("Leave blank to use pages")
        hint.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        hint.setFont(theme.qt_font(8))
        outer.addWidget(hint)

        def _forced_changed(text):
            self._state.forced_text = text

        self._forced_entry.textChanged.connect(_forced_changed)

        outer.addStretch(1)

        # ── Bottom bar: pinned via absolute positioning (mirrors Tk .place) ────
        self._discord_btn = _IconButton(
            "assets/discord.png", theme.BG, theme.ACCENT2,
            "https://discord.gg/YDXpQPF6g9",
        )
        self._discord_btn.setParent(self)

        self._banner = _BannerRotator()
        self._banner.setParent(self)

        self._github_btn = _IconButton(
            "assets/github.png", theme.BG, theme.ACCENT2,
            "https://github.com/CaptainBoots/NovaCore-ToolBox",
        )
        self._github_btn.setParent(self)

        self._position_bottom_bar()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_bottom_bar()

    def _position_bottom_bar(self):
        w, h = self.width(), self.height()
        y = h - 20 - self._discord_btn.height()
        self._discord_btn.move(8, y)
        self._banner.move((w - self._banner.width()) // 2,
                          h - 20 - self._banner.height())
        self._github_btn.move(w - 8 - self._github_btn.width(), y)

    # ── Public update methods (mirrors the Tk version's API) ────────────────

    def set_status(self, text: str):
        colour = theme.GREEN if "running" in text.lower() else theme.RED
        self._status_lbl.setStyleSheet(f"color: {colour}; background: transparent; border: none;")
        self._status_lbl.setText(text)

    def set_preview(self, text: str):
        self._preview.setPlainText(text)

    def set_page_label(self, text: str):
        self._page_lbl.setText(text)

    def get_forced_text(self) -> str:
        return self._forced_entry.text()