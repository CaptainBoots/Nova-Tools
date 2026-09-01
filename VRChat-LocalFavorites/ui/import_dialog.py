"""
ui/import_dialog.py
───────────────────────
Optional import of the person's existing official VRChat favorites
(worlds, avatars, friends) into local groups named after VRChat's own
favorite-group tags. Fetching each item's display name means one extra
API call per favorite, so this can take a little while for a large
favorites list — it's an explicit, infrequent action (first launch, or
manually from Settings), not something that runs automatically, so
that trade-off is fine.

There's no official "instance favorites" type in VRChat's API, so the
Instances category is never part of this import — nothing to map it
from.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
)

from ui.worker_utils import run_worker, stop_worker, install_busy_close_guard
from ui import theme

_TYPE_TO_CATEGORY = {"world": "worlds", "avatar": "avatars", "friend": "players"}


def _fetch_and_map_names(api):
    """Runs entirely on the background thread. Returns
    {category: {group_name: [item_dict, ...]}}."""
    groups_meta = api.get_favorite_groups()
    tag_to_name = {g.get("name"): g.get("displayName") or g.get("name") for g in groups_meta}

    result: dict[str, dict[str, list[dict]]] = {"worlds": {}, "avatars": {}, "players": {}}

    for fav_type, category in _TYPE_TO_CATEGORY.items():
        favorites = api.get_all_favorites(fav_type=fav_type)
        for fav in favorites:
            target_id = fav.get("favoriteId")
            if not target_id:
                continue
            tag = (fav.get("tags") or [None])[0]
            group_name = tag_to_name.get(tag, tag or "Imported")

            name = target_id
            try:
                if category == "worlds":
                    name = api.get_world(target_id).get("name", target_id)
                elif category == "avatars":
                    name = api.get_avatar(target_id).get("name", target_id)
                elif category == "players":
                    name = api.get_user(target_id).get("displayName", target_id)
            except Exception:
                pass  # deleted/private item, etc. — keep the ID as the name rather than failing the whole import

            result[category].setdefault(group_name, []).append({"id": target_id, "name": name})

    return result


def open_import_dialog(parent, api, store, on_done=None):
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"{theme.TITLE_PREFIX} Import VRChat Favorites")
    dlg.setMinimumWidth(380)
    dlg.setModal(True)

    state = {"thread": None, "worker": None, "relay": None, "busy": False}
    install_busy_close_guard(dlg, state)

    root = QVBoxLayout(dlg)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(10)

    title = QLabel("Import your existing VRChat favorites?")
    title.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    title.setFont(theme.qt_font(12, bold=True))
    title.setWordWrap(True)
    root.addWidget(title)

    note = QLabel(
        "This copies your official VRChat world, avatar, and friend "
        "favorites into local groups here, named after your existing "
        "favorite groups. Your real VRChat favorites are left untouched — "
        "this only adds local copies. Duplicates are skipped automatically."
    )
    note.setWordWrap(True)
    note.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    note.setFont(theme.qt_font(8))
    root.addWidget(note)

    worlds_cb = QCheckBox("Worlds")
    worlds_cb.setChecked(True)
    avatars_cb = QCheckBox("Avatars")
    avatars_cb.setChecked(True)
    players_cb = QCheckBox("Players (friends)")
    players_cb.setChecked(True)
    for cb in (worlds_cb, avatars_cb, players_cb):
        cb.setStyleSheet(f"color: {theme.TEXT};")
        root.addWidget(cb)

    status_lbl = QLabel("")
    status_lbl.setWordWrap(True)
    status_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    status_lbl.setFont(theme.qt_font(8))
    root.addWidget(status_lbl)

    btn_row = QHBoxLayout()
    skip_btn = QPushButton("Skip")
    skip_btn.setStyleSheet(theme.subtle_button_qss())
    btn_row.addWidget(skip_btn)
    btn_row.addStretch(1)
    import_btn = QPushButton("Import")
    import_btn.setStyleSheet(theme.accent_button_qss())
    import_btn.setFont(theme.qt_font(9, bold=True))
    btn_row.addWidget(import_btn)
    root.addLayout(btn_row)

    def _set_busy(busy: bool):
        state["busy"] = busy
        import_btn.setEnabled(not busy)
        skip_btn.setEnabled(not busy)
        worlds_cb.setEnabled(not busy)
        avatars_cb.setEnabled(not busy)
        players_cb.setEnabled(not busy)
        status_lbl.setText("Fetching your favorites — this can take a moment..." if busy else "")

    def _on_success(result: dict):
        stop_worker(state)
        _set_busy(False)
        selected = {
            "worlds": worlds_cb.isChecked(),
            "avatars": avatars_cb.isChecked(),
            "players": players_cb.isChecked(),
        }
        added = 0
        for category, group_map in result.items():
            if not selected.get(category):
                continue
            for group_name, items in group_map.items():
                safe = store.create_group(category, group_name)
                for item in items:
                    if store.add_item(category, safe, item):
                        added += 1
        status_lbl.setText(f"Imported {added} favorite(s).")
        status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
        skip_btn.setText("Close")
        import_btn.setText("Import Again")
        if on_done is not None:
            on_done()

    def _on_failed(msg: str):
        stop_worker(state)
        _set_busy(False)
        status_lbl.setText(f"Import failed: {msg}")
        status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")

    def _do_import():
        _set_busy(True)
        run_worker(dlg, lambda: _fetch_and_map_names(api), _on_success, _on_failed, state)

    def _skip():
        dlg.reject()

    import_btn.clicked.connect(_do_import)
    skip_btn.clicked.connect(_skip)

    dlg.exec()
