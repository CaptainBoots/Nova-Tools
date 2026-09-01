"""
ui/launcher_tab.py
────────────────────
Main content tab: the 3-instance-limit warning banner, the scrollable
profile list (each row launches/kills/removes that profile), a
slide-out editor panel for the selected profile, and the launch.exe
path picker.
"""

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFileDialog, QMessageBox, QDialog,
)

from core.launcher import LIMIT_NOTE, default_profile
from ui import theme
from ui.theme import StripeBackground


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()
        else:
            child_layout = item.layout()
            if child_layout is not None:
                _clear_layout(child_layout)


def _row_button_qss(fg: str, hover_bg: str) -> str:
    return (
        f"QPushButton {{ background-color: {theme.PANEL}; color: {fg}; "
        f"border: none; border-radius: 3px; padding: 4px 12px; font-weight: bold; }}"
        f"QPushButton:hover {{ background-color: {hover_bg}; }}"
        f"QPushButton:disabled {{ color: {theme.SUBTEXT}; background-color: {theme.PANEL}; }}"
    )


def _launch_button_qss() -> str:
    return (
        f"QPushButton {{ background-color: {theme.GREEN}; color: {theme.BG}; "
        f"border: none; border-radius: 3px; padding: 4px 14px; font-weight: bold; }}"
        f"QPushButton:hover {{ background-color: {theme.ACCENT2}; }}"
        f"QPushButton:disabled {{ background-color: {theme.BORDER}; color: {theme.SUBTEXT}; }}"
    )


def _status_dot_qss(colour: str) -> str:
    return f"color: {colour}; background: transparent; border: none;"


class LauncherTab(StripeBackground):
    def __init__(self, cfg: dict, process_mgr, save_cb, help_cb, settings_cb, parent=None):
        super().__init__(parent)
        self._cfg          = cfg
        self._process_mgr  = process_mgr
        self._save_cb      = save_cb
        self._help_cb      = help_cb
        self._settings_cb  = settings_cb

        if "profiles" not in cfg or not cfg["profiles"]:
            cfg["profiles"] = [default_profile(i) for i in range(3)]
        self._profiles: list[dict] = cfg["profiles"]
        self._rows: dict[int, dict] = {}
        self._chips = []
        self._active_edit_uid = None

        self._build()
        self._rebuild_rows()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(1000)

    def set_bg_alpha(self, alpha: float):
        super().set_bg_alpha(alpha)
        for chip in self._chips:
            chip.set_bg_alpha(alpha)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 0)
        outer.setSpacing(6)

        # ── Warning banner ───────────────────────────────────────────────────
        warn_frame = QFrame()
        warn_frame.setStyleSheet("background-color: #1a1208; border: none;")
        warn_layout = QHBoxLayout(warn_frame)
        warn_layout.setContentsMargins(10, 6, 6, 6)

        warn_lbl = QLabel("⚠  VRChat allows max 3 instances per public IP")
        warn_lbl.setStyleSheet(f"color: {theme.YELLOW}; background: transparent; border: none;")
        warn_lbl.setFont(theme.qt_font(9))
        warn_layout.addWidget(warn_lbl)
        warn_layout.addStretch(1)

        why_btn = QPushButton("Why? / Workarounds")
        why_btn.setStyleSheet(theme.subtle_button_qss())
        why_btn.setFont(theme.qt_font(9))
        why_btn.setCursor(Qt.PointingHandCursor)
        why_btn.clicked.connect(self._show_limit)
        warn_layout.addWidget(why_btn)

        outer.addWidget(warn_frame)

        # ── Main split: profile list + editor panel ──────────────────────────
        split = QHBoxLayout()
        split.setSpacing(8)

        self._profiles_scroll = QScrollArea()
        self._profiles_scroll.setWidgetResizable(True)
        self._profiles_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._profiles_scroll.setStyleSheet("background: transparent; border: none;")

        self._profiles_inner = QWidget()
        self._profiles_inner.setStyleSheet("background: transparent;")
        self._profiles_layout = QVBoxLayout(self._profiles_inner)
        self._profiles_layout.setContentsMargins(0, 0, 0, 0)
        self._profiles_layout.setSpacing(4)
        self._profiles_scroll.setWidget(self._profiles_inner)

        split.addWidget(self._profiles_scroll, 1)

        self._config_panel = QFrame()
        self._config_panel.setFixedWidth(300)
        self._config_panel.setStyleSheet(
            f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};"
        )
        self._config_panel_layout = QVBoxLayout(self._config_panel)
        self._config_panel_layout.setContentsMargins(0, 0, 0, 0)
        self._config_panel_layout.setSpacing(0)
        self._config_panel.hide()

        split.addWidget(self._config_panel)

        outer.addLayout(split, 1)

        # ── Add profile ───────────────────────────────────────────────────────
        add_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Profile")
        add_btn.setStyleSheet(theme.accent_button_qss())
        add_btn.setFont(theme.qt_font(9, bold=True))
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_profile)
        add_row.addWidget(add_btn)
        add_row.addStretch(1)
        outer.addLayout(add_row)

        # ── Divider ───────────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
        outer.addWidget(divider)

        # ── Exe path ──────────────────────────────────────────────────────────
        exe_lbl = theme.TextChip("LAUNCH EXE PATH", fg=theme.SUBTEXT, padding="2px 6px")
        exe_lbl.setFont(theme.qt_font(9, bold=True))
        outer.addWidget(exe_lbl)
        self._chips.append(exe_lbl)

        exe_row = QHBoxLayout()
        self._exe_entry = QLineEdit(self._cfg.get("launch_exe", ""))
        self._exe_entry.setFont(theme.qt_font(9))
        self._exe_entry.setStyleSheet(theme.line_edit_qss())
        self._exe_entry.editingFinished.connect(self._persist_exe_path)
        exe_row.addWidget(self._exe_entry, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet(theme.subtle_button_qss())
        browse_btn.setFont(theme.qt_font(9))
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self._browse)
        exe_row.addWidget(browse_btn)

        outer.addLayout(exe_row)

        note_chip = theme.TextChip(
            "* Must use launch.exe — launching VRChat.exe directly forces offline test mode.",
            fg=theme.YELLOW, padding="2px 6px",
        )
        note_chip.setFont(theme.qt_font(8))
        note_chip.setWordWrap(True)
        outer.addWidget(note_chip)
        self._chips.append(note_chip)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 6, 12, 6)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        self._status_lbl.setFont(theme.qt_font(9))
        footer_layout.addWidget(self._status_lbl)
        footer_layout.addStretch(1)

        help_btn = QPushButton("? Help")
        help_btn.setStyleSheet(theme.subtle_button_qss())
        help_btn.setFont(theme.qt_font(9))
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.clicked.connect(self._help_cb)
        footer_layout.addWidget(help_btn)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setStyleSheet(theme.subtle_button_qss())
        settings_btn.setFont(theme.qt_font(9))
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.clicked.connect(self._settings_cb)
        footer_layout.addWidget(settings_btn)

        outer.addWidget(footer)

    # ── Profile rows ──────────────────────────────────────────────────────────

    def _rebuild_rows(self):
        _clear_layout(self._profiles_layout)
        self._rows.clear()
        for profile in self._profiles:
            self._profiles_layout.addWidget(self._build_row(profile))
        self._profiles_layout.addStretch(1)

    def _build_row(self, profile: dict) -> QFrame:
        uid = profile["uid"]
        color = profile.get("color") or theme.ACCENT

        outer = QFrame()
        outer.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
        row = QHBoxLayout(outer)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(6)

        dot = QLabel("●")
        dot.setStyleSheet(_status_dot_qss(theme.RED))
        dot.setFont(theme.qt_font(10))
        dot.setFixedWidth(14)
        row.addWidget(dot)

        icon = QLabel("◈")
        icon.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        icon.setFont(theme.qt_font(10, bold=True))
        row.addWidget(icon)

        name_lbl = QLabel(profile["name"])
        name_lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        name_lbl.setFont(theme.qt_font(10, bold=True))
        name_lbl.setFixedWidth(76)
        name_lbl.setCursor(Qt.PointingHandCursor)
        name_lbl.mousePressEvent = lambda _evt, u=uid: self._show_config_panel(u)
        row.addWidget(name_lbl)

        port_lbl = QLabel(f"OSC: {profile['listen_port']} → {profile['osc_port']}")
        port_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        port_lbl.setFont(theme.qt_font(9))
        port_lbl.setFixedWidth(128)
        row.addWidget(port_lbl)

        status_lbl = QLabel("Stopped")
        status_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        status_lbl.setFont(theme.qt_font(9))
        status_lbl.setFixedWidth(64)
        row.addWidget(status_lbl)

        launch_btn = QPushButton("Launch")
        launch_btn.setStyleSheet(_launch_button_qss())
        launch_btn.setFont(theme.qt_font(9, bold=True))
        launch_btn.setCursor(Qt.PointingHandCursor)
        launch_btn.setFixedWidth(70)
        launch_btn.clicked.connect(lambda _checked=False, u=uid: self._launch(u))
        row.addWidget(launch_btn)

        kill_btn = QPushButton("Kill")
        kill_btn.setStyleSheet(_row_button_qss(theme.RED, theme.BORDER))
        kill_btn.setFont(theme.qt_font(9, bold=True))
        kill_btn.setCursor(Qt.PointingHandCursor)
        kill_btn.setFixedWidth(54)
        kill_btn.setEnabled(False)
        kill_btn.clicked.connect(lambda _checked=False, u=uid: self._kill(u))
        row.addWidget(kill_btn)

        row.addStretch(1)

        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet(_row_button_qss(theme.SUBTEXT, theme.BORDER))
        remove_btn.setFont(theme.qt_font(9))
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setFixedWidth(64)
        remove_btn.clicked.connect(lambda _checked=False, u=uid: self._remove(u))
        row.addWidget(remove_btn)

        self._rows[uid] = {
            "dot": dot, "status_lbl": status_lbl,
            "launch_btn": launch_btn, "kill_btn": kill_btn,
        }
        return outer

    # ── Editor panel ──────────────────────────────────────────────────────────

    def _find_profile(self, uid: int):
        for p in self._profiles:
            if p["uid"] == uid:
                return p
        return None

    def _show_config_panel(self, uid: int):
        profile = self._find_profile(uid)
        if profile is None:
            return
        self._active_edit_uid = uid
        _clear_layout(self._config_panel_layout)

        header = QFrame()
        header.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
        header.setFixedHeight(36)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 6, 0)

        title_lbl = QLabel(f"⚙ Profile: {profile['name']}")
        title_lbl.setStyleSheet(f"color: {profile['color']}; background: transparent; border: none;")
        title_lbl.setFont(theme.qt_font(10, bold=True))
        header_layout.addWidget(title_lbl)
        header_layout.addStretch(1)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(_row_button_qss(theme.SUBTEXT, theme.PANEL))
        close_btn.setFont(theme.qt_font(9))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self._hide_config_panel)
        header_layout.addWidget(close_btn)

        self._config_panel_layout.addWidget(header)

        form = QWidget()
        form.setStyleSheet(f"background-color: {theme.PANEL};")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(2)

        def field(label_text, value):
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
            lbl.setFont(theme.qt_font(9))
            form_layout.addWidget(lbl)
            form_layout.addSpacing(2)
            entry = QLineEdit(str(value))
            entry.setFont(theme.qt_font(9))
            entry.setStyleSheet(theme.line_edit_qss())
            form_layout.addWidget(entry)
            form_layout.addSpacing(8)
            return entry

        name_entry = field("Profile Name:", profile["name"])
        color_entry = field("UI Theme Color Hex:", profile["color"])
        osc_entry = field("OSC Destination Port (VRC Input):", profile["osc_port"])
        listen_entry = field("OSC Source Bind Port (VRC Output):", profile["listen_port"])
        args_entry = field("Custom Launch Args (Optional):", profile["exe_args"])

        def do_save():
            try:
                new_osc_port = int(osc_entry.text().strip())
                new_listen_port = int(listen_entry.text().strip())
            except ValueError:
                QMessageBox.critical(self, "Error", "OSC ports must be numbers!")
                return
            profile["name"] = name_entry.text().strip() or profile["name"]
            profile["color"] = color_entry.text().strip() or profile["color"]
            profile["osc_port"] = new_osc_port
            profile["listen_port"] = new_listen_port
            profile["exe_args"] = args_entry.text().strip()
            self._save_cb()
            self._rebuild_rows()
            self._show_config_panel(uid)

        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet(theme.accent_button_qss())
        save_btn.setFont(theme.qt_font(9, bold=True))
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(do_save)
        form_layout.addSpacing(8)
        form_layout.addWidget(save_btn)
        form_layout.addStretch(1)

        self._config_panel_layout.addWidget(form, 1)
        self._config_panel.show()

    def _hide_config_panel(self):
        self._config_panel.hide()
        self._active_edit_uid = None

    # ── Actions ───────────────────────────────────────────────────────────────

    def _launch(self, uid: int):
        profile = self._find_profile(uid)
        if profile is None:
            return
        exe = self._exe_entry.text().strip()
        if not os.path.exists(exe):
            QMessageBox.warning(self, "Error", f"launch.exe not found:\n{exe}")
            return
        try:
            self._process_mgr.launch(uid, exe, profile)
            self._status_lbl.setText(f"Launched {profile['name']}")
            self._status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Launch failed: {e}")
            self._status_lbl.setText(f"Launch failed: {e}")
            self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")

    def _kill(self, uid: int):
        self._process_mgr.kill(uid)

    def _remove(self, uid: int):
        if len(self._profiles) <= 1:
            QMessageBox.warning(self, "Can't Remove", "Need at least 1 profile.")
            return
        profile = self._find_profile(uid)
        if profile is None:
            return
        if QMessageBox.question(
            self, "Remove?", f"Remove '{profile['name']}'?"
        ) != QMessageBox.Yes:
            return
        self._process_mgr.drop(uid)
        self._profiles.remove(profile)
        if self._active_edit_uid == uid:
            self._hide_config_panel()
        self._rebuild_rows()
        self._save_cb()

    def _add_profile(self):
        idx = len(self._profiles)
        self._profiles.append(default_profile(idx))
        self._rebuild_rows()
        self._save_cb()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select launch.exe", "", "EXE Files (*.exe);;All Files (*.*)"
        )
        if path:
            self._exe_entry.setText(path)
            self._persist_exe_path()

    def _persist_exe_path(self):
        self._cfg["launch_exe"] = self._exe_entry.text().strip()
        self._save_cb()

    def _show_limit(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Limit Info")
        dlg.setStyleSheet(f"background-color: {theme.BG};")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 16, 20, 16)

        title_lbl = QLabel("VRChat 3-Instance Limit")
        title_lbl.setStyleSheet(f"color: {theme.YELLOW}; background: transparent; border: none;")
        title_lbl.setFont(theme.qt_font(11, bold=True))
        layout.addWidget(title_lbl)

        body_lbl = QLabel(LIMIT_NOTE)
        body_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
        body_lbl.setFont(theme.qt_font(9))
        body_lbl.setWordWrap(True)
        layout.addWidget(body_lbl)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(theme.subtle_button_qss())
        close_btn.setFont(theme.qt_font(9, bold=True))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(dlg.close)
        layout.addWidget(close_btn)

        dlg.exec()

    # ── Live status polling ───────────────────────────────────────────────────

    def _poll(self):
        for uid, widgets in self._rows.items():
            running = self._process_mgr.is_running(uid)
            widgets["dot"].setStyleSheet(_status_dot_qss(theme.GREEN if running else theme.RED))
            if running:
                widgets["status_lbl"].setText("Running")
                widgets["status_lbl"].setStyleSheet(
                    f"color: {theme.GREEN}; background: transparent; border: none;"
                )
            else:
                widgets["status_lbl"].setText("Stopped")
                widgets["status_lbl"].setStyleSheet(
                    f"color: {theme.SUBTEXT}; background: transparent; border: none;"
                )
            widgets["launch_btn"].setEnabled(not running)
            widgets["kill_btn"].setEnabled(running)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def stop_polling(self):
        """Stop this tab's own QTimer before it's discarded on a theme
        rebuild. Never touches the process manager — launched VRChat
        instances are independent OS processes and are meant to keep
        running through a rebuild, and even after this tool closes."""
        self._poll_timer.stop()
