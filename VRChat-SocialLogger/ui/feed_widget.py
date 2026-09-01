"""
ui/feed_widget.py
────────────────────
A simple append-only scrolling feed list, shared by the Friends Feed tab
and the Current Instance Log tab so both look and behave identically.
Not part of the shared suite-wide theme files — local to this tool.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
)

from ui import theme

_KIND_COLOUR = {
    "location": "ACCENT2",
    "status": "YELLOW",
    "avatar": "CYAN",
    "world_join": "GREEN",
    "world_name": "GREEN",
    "player_join": "GREEN",
    "player_left": "RED",
    "avatar_change": "CYAN",
    "instance_left": "RED",
}

_KIND_TEXT = {
    "location": "moved",
    "status": "status",
    "avatar": "avatar",
    "world_join": "joined world",
    "world_name": "world",
    "player_join": "joined instance",
    "player_left": "left instance",
    "avatar_change": "changed avatar",
    "instance_left": "left instance",
}


def _describe(event: dict) -> str:
    kind = event.get("kind", "")
    name = event.get("display_name") or event.get("world_name") or ""
    detail = event.get("detail", "")
    if kind == "world_join":
        return f"Joined {event.get('world_id', '')}:{event.get('instance_id', '')}"
    if kind == "world_name":
        return f"Instance world: {event.get('world_name', '')}"
    if kind in ("player_join", "player_left"):
        return f"{name} {_KIND_TEXT.get(kind, kind)}"
    if kind == "avatar_change":
        avatar = (event.get("extra") or {}).get("avatar", "")
        return f"Avatar changed to {avatar}" if avatar else "Avatar changed"
    if kind == "instance_left":
        return "Left the instance"
    if kind in ("location", "status", "avatar"):
        return f"{name} — {detail}" if detail else f"{name} — {_KIND_TEXT.get(kind, kind)}"
    return detail or kind


class FeedList(QWidget):
    """Scrollable, append-friendly list of feed rows. Call add_event()
    for each new event (oldest-first for initial backfill, then one at
    a time as they arrive) — the on-disk log keeps everything
    regardless of how many rows are kept visible here."""

    def __init__(self, empty_text: str = "No activity yet.", max_rows: int = 400, parent=None):
        super().__init__(parent)
        self._max_rows = max_rows
        self._rows: list[QFrame] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent; border: none;")

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setSpacing(3)
        self._inner_layout.setContentsMargins(2, 2, 2, 2)

        self._empty_lbl = QLabel(empty_text)
        self._empty_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        self._empty_lbl.setFont(theme.qt_font(9))
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._inner_layout.addWidget(self._empty_lbl)
        self._inner_layout.addStretch(1)

        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)

    def add_event(self, event: dict):
        self._empty_lbl.hide()

        kind = event.get("kind", "")
        colour_key = _KIND_COLOUR.get(kind, "TEXT")
        colour = getattr(theme, colour_key, theme.TEXT)

        row = QFrame()
        row.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 4, 8, 4)

        ts_lbl = QLabel(event.get("timestamp", ""))
        ts_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        ts_lbl.setFont(theme.qt_font(8))
        ts_lbl.setFixedWidth(130)
        row_layout.addWidget(ts_lbl)

        text_lbl = QLabel(_describe(event))
        text_lbl.setStyleSheet(f"color: {colour}; background: transparent; border: none;")
        text_lbl.setFont(theme.qt_font(9))
        text_lbl.setWordWrap(True)
        row_layout.addWidget(text_lbl, 1)

        # Insert above the trailing stretch, so the feed reads
        # top-to-bottom oldest-to-newest without re-sorting.
        insert_at = self._inner_layout.count() - 1
        self._inner_layout.insertWidget(insert_at, row)
        self._rows.append(row)

        if len(self._rows) > self._max_rows:
            oldest = self._rows.pop(0)
            self._inner_layout.removeWidget(oldest)
            oldest.deleteLater()

        # Auto-scroll to the newest entry.
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def clear(self):
        for row in self._rows:
            self._inner_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._empty_lbl.show()
