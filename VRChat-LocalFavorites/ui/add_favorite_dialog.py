"""
ui/add_favorite_dialog.py
─────────────────────────────
Search or fetch a single item to favorite, then choose which local
group(s) to save it into (creating a new group inline if needed).

Per category:
  worlds   — search by name (VRChat's own world search)
  avatars  — fetch by ID/URL only (VRChat's search API only returns
             your own or featured avatars, so search wouldn't find
             most avatars people actually want to favorite)
  players  — search by name (VRChat's own user search) or fetch by ID/URL
  instances — fetch by pasted instance link or "world_id:instance_id"
             (there's no search for instances — you have to already
             hold a link, e.g. one a friend sent you)

All network calls run through ui.worker_utils.run_worker (background
thread + relay), so the dialog never freezes and never risks the
close-while-busy crash class documented in worker_utils.py.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QWidget,
)

from core.id_parser import extract_world_id, extract_avatar_id, extract_user_id, extract_world_and_instance
from core.vrchat_api import VRChatAPIError, describe_instance_type
from ui.worker_utils import run_worker, stop_worker, install_busy_close_guard
from ui import theme

_CATEGORY_LABELS = {
    "worlds": "World",
    "avatars": "Avatar",
    "players": "Player",
    "instances": "Instance",
}

_SEARCH_PLACEHOLDER = {
    "worlds": "Search world names...",
    "avatars": "Avatar ID or vrchat.com/home/avatar/... link",
    "players": "Search usernames, or paste a usr_... ID/link",
    "instances": "Paste an instance link, or world_id:instance_id",
}


def open_add_favorite_dialog(parent, category: str, api, store, on_added=None):
    """on_added(), if given, is called after a successful save — the
    caller (favorites_tab.py) uses this to refresh its list instead of
    this dialog knowing anything about that widget."""
    dlg = QDialog(parent)
    label = _CATEGORY_LABELS.get(category, category.title())
    dlg.setWindowTitle(f"{theme.TITLE_PREFIX} Add {label} Favorite")
    dlg.setMinimumSize(420, 420)
    dlg.setModal(True)

    state = {"thread": None, "worker": None, "relay": None, "busy": False, "selected": None}
    install_busy_close_guard(dlg, state)

    root = QVBoxLayout(dlg)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(8)

    title = QLabel(f"Add a {label.lower()} favorite")
    title.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    title.setFont(theme.qt_font(12, bold=True))
    root.addWidget(title)

    search_row = QHBoxLayout()
    search_edit = QLineEdit()
    search_edit.setPlaceholderText(_SEARCH_PLACEHOLDER.get(category, "Search..."))
    search_edit.setStyleSheet(theme.line_edit_qss())
    search_row.addWidget(search_edit, 1)

    search_btn = QPushButton("Fetch" if category in ("avatars", "instances") else "Search")
    search_btn.setStyleSheet(theme.accent_button_qss())
    search_row.addWidget(search_btn)
    root.addLayout(search_row)

    status_lbl = QLabel("")
    status_lbl.setWordWrap(True)
    status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
    status_lbl.setFont(theme.qt_font(8))
    root.addWidget(status_lbl)

    results_list = QListWidget()
    results_list.setStyleSheet(
        f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER}; color: {theme.TEXT};"
    )
    root.addWidget(results_list, 1)

    group_lbl = QLabel("Save to group(s):")
    group_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    group_lbl.setFont(theme.qt_font(9))
    root.addWidget(group_lbl)

    groups_list = QListWidget()
    groups_list.setStyleSheet(
        f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER}; color: {theme.TEXT};"
    )
    groups_list.setMaximumHeight(110)
    for existing in store.list_groups(category):
        item = QListWidgetItem(existing)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)
        groups_list.addItem(item)
    root.addWidget(groups_list)

    new_group_row = QHBoxLayout()
    new_group_edit = QLineEdit()
    new_group_edit.setPlaceholderText("Or type a new group name...")
    new_group_edit.setStyleSheet(theme.line_edit_qss())
    new_group_row.addWidget(new_group_edit, 1)
    root.addLayout(new_group_row)

    btn_row = QHBoxLayout()
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setStyleSheet(theme.subtle_button_qss())
    btn_row.addWidget(cancel_btn)
    btn_row.addStretch(1)
    add_btn = QPushButton("Add Favorite")
    add_btn.setStyleSheet(theme.accent_button_qss())
    add_btn.setFont(theme.qt_font(9, bold=True))
    add_btn.setEnabled(False)
    btn_row.addWidget(add_btn)
    root.addLayout(btn_row)

    # Single source of truth for "is something selected to add" — fires
    # for every path (search results list OR the single fetched item
    # from _populate_result), rather than each success handler having
    # to remember to enable it individually.
    results_list.currentItemChanged.connect(lambda cur, _prev: add_btn.setEnabled(cur is not None))

    def _set_busy(busy: bool):
        state["busy"] = busy
        search_btn.setEnabled(not busy)
        cancel_btn.setEnabled(not busy)
        search_btn.setText("Working..." if busy else ("Fetch" if category in ("avatars", "instances") else "Search"))

    def _populate_result(item_id: str, name: str, extra: dict):
        results_list.clear()
        list_item = QListWidgetItem(f"{name}  ({item_id})")
        list_item.setData(Qt.UserRole, {"id": item_id, "name": name, **extra})
        results_list.addItem(list_item)
        results_list.setCurrentItem(list_item)
        add_btn.setEnabled(True)

    def _on_search_failed(msg: str):
        stop_worker(state)
        _set_busy(False)
        status_lbl.setText(msg)
        results_list.clear()
        add_btn.setEnabled(False)

    def _on_world_search_succeeded(results: list):
        stop_worker(state)
        _set_busy(False)
        results_list.clear()
        if not results:
            status_lbl.setText("No worlds found.")
            return
        status_lbl.setText("")
        for w in results:
            list_item = QListWidgetItem(f"{w.get('name', '?')}  ({w.get('id', '?')})")
            list_item.setData(Qt.UserRole, {
                "id": w.get("id"), "name": w.get("name", "?"),
                "thumbnail_url": w.get("thumbnailImageUrl", ""),
            })
            results_list.addItem(list_item)

    def _on_user_search_succeeded(results: list):
        stop_worker(state)
        _set_busy(False)
        results_list.clear()
        if not results:
            status_lbl.setText("No users found.")
            return
        status_lbl.setText("")
        for u in results:
            list_item = QListWidgetItem(f"{u.get('displayName', '?')}  ({u.get('id', '?')})")
            list_item.setData(Qt.UserRole, {
                "id": u.get("id"), "name": u.get("displayName", "?"),
                "thumbnail_url": u.get("currentAvatarThumbnailImageUrl", ""),
            })
            results_list.addItem(list_item)

    def _on_avatar_fetch_succeeded(a: dict):
        stop_worker(state)
        _set_busy(False)
        status_lbl.setText("")
        _populate_result(a.get("id", "?"), a.get("name", "?"), {"thumbnail_url": a.get("thumbnailImageUrl", "")})

    def _on_user_fetch_succeeded(u: dict):
        stop_worker(state)
        _set_busy(False)
        status_lbl.setText("")
        _populate_result(u.get("id", "?"), u.get("displayName", "?"),
                          {"thumbnail_url": u.get("currentAvatarThumbnailImageUrl", "")})

    def _on_instance_fetch_succeeded(payload: tuple):
        stop_worker(state)
        _set_busy(False)
        status_lbl.setText("")
        instance_data, world_id, instance_id = payload
        world_field = instance_data.get("world")
        world_name = world_field.get("name") if isinstance(world_field, dict) else None
        name = world_name or instance_data.get("name") or f"{world_id}:{instance_id}"
        _populate_result(f"{world_id}:{instance_id}", name, {
            "world_id": world_id, "instance_id": instance_id,
            "instance_type": describe_instance_type(instance_id),
        })

    def _do_search():
        query = search_edit.text().strip()
        if not query:
            status_lbl.setText("Enter something to search or fetch first.")
            return
        status_lbl.setText("")
        results_list.clear()
        add_btn.setEnabled(False)
        _set_busy(True)

        if category == "worlds":
            run_worker(dlg, lambda: api.search_worlds(query), _on_world_search_succeeded, _on_search_failed, state)

        elif category == "avatars":
            avatar_id = extract_avatar_id(query) or query
            run_worker(dlg, lambda: api.get_avatar(avatar_id), _on_avatar_fetch_succeeded, _on_search_failed, state)

        elif category == "players":
            user_id = extract_user_id(query)
            if user_id:
                run_worker(dlg, lambda: api.get_user(user_id), _on_user_fetch_succeeded, _on_search_failed, state)
            else:
                run_worker(dlg, lambda: api.search_users(query), _on_user_search_succeeded, _on_search_failed, state)

        elif category == "instances":
            parsed = extract_world_and_instance(query)
            if not parsed:
                _set_busy(False)
                status_lbl.setText("Couldn't find a world ID + instance ID in that. Paste a full instance link.")
                return
            world_id, instance_id = parsed

            def _fetch():
                data = api.get_instance(world_id, instance_id)
                return (data, world_id, instance_id)

            run_worker(dlg, _fetch, _on_instance_fetch_succeeded, _on_search_failed, state)

    def _do_add():
        current = results_list.currentItem()
        if current is None:
            status_lbl.setText("Select a result first.")
            return
        item_data = current.data(Qt.UserRole)

        target_groups = []
        for i in range(groups_list.count()):
            gi = groups_list.item(i)
            if gi.checkState() == Qt.Checked:
                target_groups.append(gi.text())
        new_group_name = new_group_edit.text().strip()
        if new_group_name:
            target_groups.append(new_group_name)

        if not target_groups:
            status_lbl.setText("Choose or type at least one group.")
            return

        for group_name in target_groups:
            safe = store.create_group(category, group_name)
            store.add_item(category, safe, item_data)

        if on_added is not None:
            on_added()
        dlg.accept()

    search_btn.clicked.connect(_do_search)
    search_edit.returnPressed.connect(_do_search)
    add_btn.clicked.connect(_do_add)
    cancel_btn.clicked.connect(dlg.reject)

    dlg.exec()
