"""
ui/favorites_tab.py
──────────────────────
One instance of this widget per category (Worlds/Avatars/Players/
Instances) — a group/item tree on the left, a detail panel with
category-appropriate action buttons on the right. This is the main
browsing surface of the tool.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSplitter,
    QTreeWidget, QTreeWidgetItem, QInputDialog, QMenu, QMessageBox, QFrame,
)

from core import deep_link
from core.vrchat_api import VRChatAPIError
from ui.add_favorite_dialog import open_add_favorite_dialog
from ui.worker_utils import run_worker, stop_worker
from ui import theme

_ACTION_LABELS = {
    "worlds": "Launch / Join",
    "avatars": "Change Into This Avatar",
    "players": "Open Profile",
    "instances": "Launch / Join Instance",
}


class FavoritesCategoryTab(theme.StripeBackground):
    def __init__(self, category: str, cfg: dict, api, store, help_cb, settings_cb, parent=None):
        super().__init__(parent)
        self._category = category
        self._cfg = cfg
        self._api = api
        self._store = store
        self._help_cb = help_cb
        self._settings_cb = settings_cb
        self._worker_state = {"thread": None, "worker": None, "relay": None}
        self._current_selection = None  # (group_name, item_dict) or None

        self._build()
        self._reload_tree()

    # ── Layout ────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 0)
        outer.setSpacing(8)

        top_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Favorite")
        add_btn.setStyleSheet(theme.accent_button_qss())
        add_btn.setFont(theme.qt_font(9, bold=True))
        add_btn.clicked.connect(self._open_add_dialog)
        top_row.addWidget(add_btn)

        new_group_btn = QPushButton("+ New Group")
        new_group_btn.setStyleSheet(theme.subtle_button_qss())
        new_group_btn.clicked.connect(self._create_group)
        top_row.addWidget(new_group_btn)
        top_row.addStretch(1)
        outer.addLayout(top_row)

        splitter = QSplitter(Qt.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setStyleSheet(
            f"QTreeWidget {{ background-color: {theme.PANEL}; border: 1px solid {theme.BORDER}; "
            f"color: {theme.TEXT}; }}"
        )
        self._tree.itemClicked.connect(self._on_tree_item_clicked)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        splitter.addWidget(self._tree)

        self._detail_panel = QFrame()
        self._detail_panel.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
        self._detail_layout = QVBoxLayout(self._detail_panel)
        self._detail_layout.setContentsMargins(16, 16, 16, 16)
        self._detail_layout.setAlignment(Qt.AlignTop)
        splitter.addWidget(self._detail_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

        footer = QFrame()
        footer.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 6, 0, 6)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        self._status_lbl.setFont(theme.qt_font(8))
        footer_layout.addWidget(self._status_lbl)
        footer_layout.addStretch(1)

        help_btn = QPushButton("? Help")
        help_btn.setStyleSheet(theme.subtle_button_qss())
        help_btn.clicked.connect(self._help_cb)
        footer_layout.addWidget(help_btn)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setStyleSheet(theme.subtle_button_qss())
        settings_btn.clicked.connect(self._settings_cb)
        footer_layout.addWidget(settings_btn)

        outer.addWidget(footer)

        self._show_empty_detail()

    # ── Tree ──────────────────────────────────────────────────────────

    def _reload_tree(self):
        self._tree.clear()
        for group in self._store.list_groups(self._category):
            items = self._store.list_items(self._category, group)
            group_node = QTreeWidgetItem([f"{group}  ({len(items)})"])
            group_node.setData(0, Qt.UserRole, {"type": "group", "name": group})
            self._tree.addTopLevelItem(group_node)
            for item in items:
                leaf = QTreeWidgetItem([item.get("name", "?")])
                leaf.setData(0, Qt.UserRole, {"type": "item", "group": group, "item": item})
                group_node.addChild(leaf)
        self._tree.expandAll()

    def _on_tree_item_clicked(self, tree_item, _column):
        data = tree_item.data(0, Qt.UserRole)
        if data is None:
            return
        if data["type"] == "item":
            self._current_selection = (data["group"], data["item"])
            self._show_detail(data["group"], data["item"])
        else:
            self._current_selection = None
            self._show_empty_detail()

    def _open_add_dialog(self):
        open_add_favorite_dialog(self, self._category, self._api, self._store, on_added=self._reload_tree)

    def _create_group(self):
        name, ok = QInputDialog.getText(self, "New Group", "Group name:")
        if ok and name.strip():
            self._store.create_group(self._category, name.strip())
            self._reload_tree()

    def _on_tree_context_menu(self, pos):
        tree_item = self._tree.itemAt(pos)
        if tree_item is None:
            return
        data = tree_item.data(0, Qt.UserRole)
        if data is None:
            return
        menu = QMenu(self)

        if data["type"] == "group":
            rename_action = menu.addAction("Rename group")
            delete_action = menu.addAction("Delete group")
            chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
            if chosen == rename_action:
                new_name, ok = QInputDialog.getText(self, "Rename Group", "New name:", text=data["name"])
                if ok and new_name.strip():
                    self._store.rename_group(self._category, data["name"], new_name.strip())
                    self._reload_tree()
            elif chosen == delete_action:
                confirm = QMessageBox.question(
                    self, "Delete Group",
                    f"Delete group \"{data['name']}\" and everything in it? This can't be undone.",
                )
                if confirm == QMessageBox.Yes:
                    self._store.delete_group(self._category, data["name"])
                    self._reload_tree()
                    self._show_empty_detail()

        elif data["type"] == "item":
            remove_action = menu.addAction("Remove from this group")
            chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
            if chosen == remove_action:
                self._store.remove_item(self._category, data["group"], data["item"].get("id"))
                self._reload_tree()
                self._show_empty_detail()

    # ── Detail panel ──────────────────────────────────────────────────

    def _clear_detail_layout(self):
        while self._detail_layout.count():
            child = self._detail_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()

    def _show_empty_detail(self):
        self._clear_detail_layout()
        lbl = QLabel("Select a favorite to see details.")
        lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        lbl.setFont(theme.qt_font(9))
        self._detail_layout.addWidget(lbl)

    def _show_detail(self, group: str, item: dict):
        self._clear_detail_layout()

        name_lbl = QLabel(item.get("name", "?"))
        name_lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
        name_lbl.setFont(theme.qt_font(13, bold=True))
        name_lbl.setWordWrap(True)
        self._detail_layout.addWidget(name_lbl)

        id_lbl = QLabel(item.get("id", "?"))
        id_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        id_lbl.setFont(theme.qt_font(8))
        id_lbl.setWordWrap(True)
        self._detail_layout.addWidget(id_lbl)

        if self._category == "instances":
            type_lbl = QLabel(f"Type: {item.get('instance_type', 'Unknown')}")
            type_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
            type_lbl.setFont(theme.qt_font(9))
            self._detail_layout.addWidget(type_lbl)

        added_lbl = QLabel(f"Added: {item.get('added_at', '?')}")
        added_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        added_lbl.setFont(theme.qt_font(8))
        self._detail_layout.addWidget(added_lbl)

        self._detail_layout.addSpacing(12)

        action_btn = QPushButton(_ACTION_LABELS.get(self._category, "Open"))
        action_btn.setStyleSheet(theme.accent_button_qss())
        action_btn.setFont(theme.qt_font(9, bold=True))
        action_btn.clicked.connect(lambda: self._do_primary_action(item))
        self._detail_layout.addWidget(action_btn)
        self._action_btn = action_btn

        website_btn = QPushButton("Open on Website")
        website_btn.setStyleSheet(theme.subtle_button_qss())
        website_btn.clicked.connect(lambda: self._open_website(item))
        self._detail_layout.addWidget(website_btn)

        remove_btn = QPushButton("Remove from this group")
        remove_btn.setStyleSheet(theme.subtle_button_qss())
        remove_btn.clicked.connect(lambda: self._remove_current(group, item))
        self._detail_layout.addWidget(remove_btn)

        self._detail_layout.addStretch(1)

    def _remove_current(self, group: str, item: dict):
        self._store.remove_item(self._category, group, item.get("id"))
        self._reload_tree()
        self._show_empty_detail()

    # ── Actions ───────────────────────────────────────────────────────

    def _website_url(self, item: dict) -> str | None:
        if self._category == "worlds":
            return deep_link.world_page_url(item["id"])
        if self._category == "avatars":
            return deep_link.avatar_page_url(item["id"])
        if self._category == "players":
            return deep_link.user_page_url(item["id"])
        if self._category == "instances":
            return deep_link.world_page_url(item.get("world_id", ""))
        return None

    def _open_website(self, item: dict):
        url = self._website_url(item)
        if url:
            deep_link.open_url(url)

    def _do_primary_action(self, item: dict):
        if self._category == "worlds":
            deep_link.open_url(deep_link.launch_url(item["id"]))
            self._status_lbl.setText("Opened launch link in your browser.")

        elif self._category == "instances":
            deep_link.open_url(deep_link.launch_url(item.get("world_id", ""), item.get("instance_id", "")))
            self._status_lbl.setText("Opened join link in your browser.")

        elif self._category == "players":
            self._open_website(item)

        elif self._category == "avatars":
            self._change_avatar(item)

    def _change_avatar(self, item: dict):
        avatar_id = item.get("id", "")
        self._action_btn.setEnabled(False)
        self._status_lbl.setText("Switching avatar...")

        def _fetch():
            return self._api.select_avatar(avatar_id)

        def _on_success(_result):
            stop_worker(self._worker_state)
            self._action_btn.setEnabled(True)
            self._status_lbl.setText("Avatar switched.")
            self._status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")

        def _on_failed(msg: str):
            stop_worker(self._worker_state)
            self._action_btn.setEnabled(True)
            self._status_lbl.setText("Couldn't switch remotely (not in your real favorites/owned) — opening its page instead.")
            self._status_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
            self._open_website(item)

        run_worker(self, _fetch, _on_success, _on_failed, self._worker_state)

    def destroy_all(self):
        stop_worker(self._worker_state)
