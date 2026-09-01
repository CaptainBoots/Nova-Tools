"""
ui/media_priority_section.py
───────────────────────────────
The "Player Priority" list inside Settings -> Media — a drag-reorderable
QListWidget seeded from core/media_registry.py, showing which media
source wins when more than one is playing at once. Split out of
settings_dialog.py to keep that file from ballooning, same reasoning as
ui/dev_menu.py being its own module.

Reordering takes effect immediately (monitors.media.set_priority_order()
is called on every drop, not just on dialog close) and is persisted to
cfg["media_priority_order"] as a flat list of registry keys — so a
saved order surviving a future update that adds new registry entries
just appends the new ones at the end rather than losing them (see
monitors.media.set_priority_order()'s merge logic).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from core import media_registry
from monitors import media as media_mod
from ui import theme


def build_priority_list(parent_layout: QVBoxLayout, cfg: dict, save_cb):
    hint = QLabel(
        "Drag to reorder. When more than one thing is playing at once, "
        "whichever is highest in this list wins."
    )
    hint.setWordWrap(True)
    hint.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    hint.setFont(theme.qt_font(8))
    parent_layout.addWidget(hint)

    list_widget = QListWidget()
    list_widget.setDragDropMode(QAbstractItemView.InternalMove)
    list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
    list_widget.setFixedHeight(220)
    list_widget.setStyleSheet(f"""
        QListWidget {{
            background-color: {theme.BG};
            color: {theme.TEXT};
            border: 1px solid {theme.BORDER};
        }}
        QListWidget::item {{
            padding: 4px 6px;
        }}
        QListWidget::item:selected {{
            background-color: {theme.ACCENT};
            color: {theme.BG};
        }}
    """)
    list_widget.setFont(theme.qt_font(9))
    parent_layout.addWidget(list_widget)

    saved_order = cfg.get("media_priority_order") or media_registry.default_order()
    known = set(media_registry.default_order())
    ordered_keys = [k for k in saved_order if k in known]
    ordered_keys += [k for k in media_registry.default_order() if k not in ordered_keys]

    label_map = media_registry.labels()
    for key in ordered_keys:
        item = QListWidgetItem(label_map.get(key, key))
        item.setData(Qt.UserRole, key)
        list_widget.addItem(item)

    def _persist_current_order():
        order = [
            list_widget.item(i).data(Qt.UserRole)
            for i in range(list_widget.count())
        ]
        cfg["media_priority_order"] = order
        media_mod.set_priority_order(order)  # live — no restart needed
        save_cb()

    # rowsMoved fires on a completed drag-drop reorder; this is the one
    # signal that reliably reflects the widget's post-drop item order
    # (unlike currentRowChanged etc, which fire for selection, not order).
    list_widget.model().rowsMoved.connect(lambda *_: _persist_current_order())

    # Apply whatever was already saved (or the registry default) right
    # away, so the live loop matches what's shown here even before the
    # person drags anything this session.
    media_mod.set_priority_order(ordered_keys)

    return list_widget
