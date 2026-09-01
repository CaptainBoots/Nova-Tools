"""
ui/instance_info_tab.py
──────────────────────────
Tab 1: "Current Instance". Shows details for whatever instance the
user's own VRChat client is presently in — world name, instance type,
region, population — plus which of their friends are also there.

Deliberately, there is no field anywhere in this tab to type or paste
an instance ID. Everything shown here comes from the engine's own log
tail (core/vrlog_tail.py) tracking the local client's session, and from
the friends snapshot the engine already polls — never from a lookup a
person could point at an arbitrary instance.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QGridLayout,
)

from core.vrchat_api import VRChatAPIError, describe_instance_type
from ui import theme


class _PopulationWorker(QObject):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, api, world_id: str, instance_id: str):
        super().__init__()
        self._api = api
        self._world_id = world_id
        self._instance_id = instance_id

    def run(self):
        try:
            data = self._api.get_instance(self._world_id, self._instance_id)
            self.succeeded.emit(data)
        except VRChatAPIError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Could not reach VRChat: {exc}")


class InstanceInfoTab(theme.StripeBackground):
    def __init__(self, cfg: dict, save_cb, help_cb, settings_cb, api, engine, bridge, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._save_cb = save_cb
        self._help_cb = help_cb
        self._settings_cb = settings_cb
        self._api = api
        self._engine = engine
        self._bridge = bridge
        self._chips = []
        self._pop_thread = None
        self._pop_worker = None

        self._build()
        self._refresh_from_engine()

        # Bound methods of self (a real QWidget/QObject on the main
        # thread), not lambdas — a lambda receiver doesn't reliably
        # queue across threads even with the background engine emitting
        # via a genuine QObject bridge; see ui/login_dialog.py's
        # _ResultRelay docstring for the full explanation.
        self._bridge.instance_event.connect(self._on_instance_event)
        self._bridge.friend_event.connect(self._on_friend_event)

    # ── Layout ────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 0)
        outer.setSpacing(8)

        panel = QFrame()
        panel.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
        grid = QGridLayout(panel)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        self._field_labels = {}
        for row, (key, caption) in enumerate((
                ("world_name", "World"),
                ("world_id", "World ID"),
                ("instance_id", "Instance ID"),
                ("instance_type", "Instance Type"),
                ("region", "Region"),
                ("population", "Population"),
        )):
            cap_lbl = QLabel(caption)
            cap_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
            cap_lbl.setFont(theme.qt_font(9, bold=True))
            grid.addWidget(cap_lbl, row, 0)

            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
            val_lbl.setFont(theme.qt_font(9))
            val_lbl.setWordWrap(True)
            grid.addWidget(val_lbl, row, 1)
            self._field_labels[key] = val_lbl

        outer.addWidget(panel)

        refresh_row = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh Population")
        self._refresh_btn.setStyleSheet(theme.subtle_button_qss())
        self._refresh_btn.setFont(theme.qt_font(9))
        self._refresh_btn.clicked.connect(self._refresh_population)
        refresh_row.addWidget(self._refresh_btn)
        refresh_row.addStretch(1)
        outer.addLayout(refresh_row)

        friends_lbl = QLabel("Friends in this instance")
        friends_lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
        friends_lbl.setFont(theme.qt_font(10, bold=True))
        outer.addWidget(friends_lbl)

        self._friends_scroll = QScrollArea()
        self._friends_scroll.setWidgetResizable(True)
        self._friends_scroll.setStyleSheet("background: transparent; border: none;")
        self._friends_inner = QWidget()
        self._friends_inner.setStyleSheet("background: transparent;")
        self._friends_layout = QVBoxLayout(self._friends_inner)
        self._friends_layout.setSpacing(3)
        self._friends_scroll.setWidget(self._friends_inner)
        outer.addWidget(self._friends_scroll, 1)

        footer = QFrame()
        footer.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 6, 12, 6)

        self._status_lbl = QLabel("Waiting for VRChat...")
        self._status_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
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

    # ── Data refresh ──────────────────────────────────────────────────

    def _on_instance_event(self, _event: dict):
        self._refresh_from_engine()

    def _on_friend_event(self, _event: dict):
        self._refresh_friends_present()

    def _refresh_from_engine(self):
        world_id, instance_id, world_name = self._engine.get_current_location()
        if not world_id:
            for lbl in self._field_labels.values():
                lbl.setText("—")
            self._status_lbl.setText("Not currently in an instance (or VRChat isn't running).")
            self._clear_friends_list()
            return

        self._field_labels["world_name"].setText(world_name or "(unknown — enter the world to populate)")
        self._field_labels["world_id"].setText(world_id)
        self._field_labels["instance_id"].setText(instance_id)
        self._field_labels["instance_type"].setText(describe_instance_type(instance_id))
        region = "unknown"
        if "region(" in instance_id:
            try:
                region = instance_id.split("region(", 1)[1].split(")", 1)[0]
            except IndexError:
                pass
        self._field_labels["region"].setText(region)
        self._status_lbl.setText("Tracking current instance from local VRChat log.")
        self._refresh_friends_present()

    def _refresh_population(self):
        world_id, instance_id, _ = self._engine.get_current_location()
        if not world_id:
            self._status_lbl.setText("Not currently in an instance.")
            return
        self._refresh_btn.setEnabled(False)  # also prevents a second click re-entering mid-flight
        self._status_lbl.setText("Refreshing population...")

        self._pop_thread = QThread(self)
        self._pop_worker = _PopulationWorker(self._api, world_id, instance_id)
        self._pop_worker.moveToThread(self._pop_thread)
        self._pop_thread.started.connect(self._pop_worker.run)
        # Explicit QueuedConnection: even though these two ARE bound
        # QObject methods (auto-detection normally handles that fine),
        # being explicit here matches the rest of the app after the
        # lambda-connection bug found elsewhere, and costs nothing.
        self._pop_worker.succeeded.connect(self._on_population, Qt.QueuedConnection)
        self._pop_worker.failed.connect(self._on_population_failed, Qt.QueuedConnection)
        self._pop_thread.finished.connect(self._pop_worker.deleteLater)
        self._pop_thread.finished.connect(self._pop_thread.deleteLater)
        self._pop_thread.start()

    def _stop_pop_thread(self):
        if self._pop_thread is not None:
            self._pop_thread.quit()
            self._pop_thread.wait()
        self._pop_thread = None
        self._pop_worker = None

    def _on_population(self, data: dict):
        self._stop_pop_thread()
        self._refresh_btn.setEnabled(True)
        pop = data.get("n_users", data.get("userCount", "?"))
        self._field_labels["population"].setText(str(pop))
        self._status_lbl.setText("Population refreshed.")

    def _on_population_failed(self, msg: str):
        self._stop_pop_thread()
        self._refresh_btn.setEnabled(True)
        self._status_lbl.setText(f"Couldn't refresh population: {msg}")

    def _clear_friends_list(self):
        while self._friends_layout.count():
            item = self._friends_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _refresh_friends_present(self):
        world_id, instance_id, _ = self._engine.get_current_location()
        self._clear_friends_list()
        if not world_id:
            return

        location = f"{world_id}:{instance_id}"
        snapshot = self._engine.get_friends_snapshot()
        present = [f for f in snapshot.values() if f.get("location") == location]

        if not present:
            empty_lbl = QLabel("None of your friends are in this instance right now.")
            empty_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
            empty_lbl.setFont(theme.qt_font(9))
            self._friends_layout.addWidget(empty_lbl)
            return

        for friend in present:
            row = QFrame()
            row.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 4, 8, 4)
            name_lbl = QLabel(friend.get("displayName", "?"))
            name_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
            name_lbl.setFont(theme.qt_font(9, bold=True))
            row_layout.addWidget(name_lbl)
            row_layout.addStretch(1)
            self._friends_layout.addWidget(row)

    # ── Lifecycle ─────────────────────────────────────────────────────

    def destroy_all(self):
        self._stop_pop_thread()