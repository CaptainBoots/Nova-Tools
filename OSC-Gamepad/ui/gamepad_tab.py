"""
ui/gamepad_tab.py
─────────────────
Pads tab: toolbar with + Add Pad / ? Help / ⚙ Settings, then a
scrollable list of PadCards.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
)

from ui import theme
from ui.theme import StripeBackground
from ui.pad_card import PadCard


class GamepadTab(StripeBackground):
    def __init__(self, cfg: dict, save_cb, help_cb, settings_cb, parent=None):
        super().__init__(parent)
        self._cfg         = cfg
        self._save_cb     = save_cb
        self._help_cb     = help_cb
        self._settings_cb = settings_cb

        self.cards: list[PadCard] = []
        self._pad_counter = 0

        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

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

        self._pad_count_lbl = QLabel("0 pads")
        self._pad_count_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
        self._pad_count_lbl.setFont(theme.qt_font(9, bold=True))
        status_layout.addWidget(self._pad_count_lbl)
        status_layout.addStretch(1)

        outer.addWidget(status_frame)

        # ── Button row ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 4)

        add_btn = QPushButton("＋  Add Pad")
        add_btn.setFont(theme.qt_font(10, bold=True))
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setMinimumWidth(110)
        add_btn.clicked.connect(self._add_pad)
        btn_row.addWidget(add_btn)
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

        # ── Scrollable pad list ───────────────────────────────────────────────
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

    # ── Pads ──────────────────────────────────────────────────────────────────

    def load_pads(self):
        saved = self._cfg.get("pads", [])
        if saved:
            for pad_cfg in saved:
                self.add_pad(
                    host=pad_cfg.get("host", "127.0.0.1"),
                    port=pad_cfg.get("port", "9000"),
                    style=pad_cfg.get("style", "nes"),
                    name=pad_cfg.get("name", ""),
                )
        else:
            self.add_pad()

    def add_pad(self, host="127.0.0.1", port="9000", style="nes", name=""):
        self._pad_counter += 1
        card = PadCard(self._pad_counter, self._remove_pad,
                       host=host, port=str(port), style=style, name=name)
        # Insert before the trailing stretch item
        self._inner_layout.insertWidget(self._inner_layout.count() - 1, card)
        self.cards.append(card)
        self._update_count()

    def _add_pad(self):
        self.add_pad()
        self._save_cb()

    def _remove_pad(self, card: PadCard):
        card.destroy_state()
        self._inner_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        self.cards.remove(card)
        self._update_count()
        self._save_cb()

    def _update_count(self):
        n = len(self.cards)
        self._pad_count_lbl.setText(f"{n} pad{'s' if n != 1 else ''}")

    # ── Config I/O ────────────────────────────────────────────────────────────

    def collect_pads(self) -> list[dict]:
        return [c.get_config() for c in self.cards]

    def destroy_all(self):
        for c in self.cards:
            c.destroy_state()