"""
ui/app.py
─────────
Root window for VRChat Social Logger.
Same structure and theme as the rest of VRChat-Tools: header bar with
title + version, dark tab widget, three tabs.

Owns the VRChatAPI session and the shared Engine (background friends
poll + local log tail) — these must survive a theme rebuild, so per
§5/§6.8 they live here, not inside any tab.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QObject, Signal, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QApplication, QMessageBox,
)

from config import load_config, save_config, get_defaults, SESSION_BLOB_FILE
from core.vrchat_api import VRChatAPI, VRChatAPIError
from core.secure_store import SecureStore, WrongPassword, CorruptBlob
from ui.instance_info_tab import InstanceInfoTab
from ui.friends_feed_tab import FriendsFeedTab
from ui.instance_log_tab import InstanceLogTab
from ui.help_dialog import open_help
from ui.settings_dialog import open_settings
from ui.login_dialog import open_login
from ui.master_password_dialog import open_master_password_prompt
from ui import theme

try:
    from main import VERSION
except ImportError:
    VERSION = "version error"


class _Bridge(QObject):
    """§6.16 — the engine's background thread never touches a widget
    directly; it calls these signals, which Qt auto-queues onto the
    main thread for every connected slot."""
    friend_event = Signal(dict)
    instance_event = Signal(dict)
    engine_status = Signal(bool)
    status = Signal(str)
    error = Signal(str)


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self._cfg = load_config()

        # Apply the saved theme BEFORE building anything (§6.18).
        theme.set_theme(self._cfg.get("theme_mode", "rich_purple"))
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.setStyleSheet(theme.qss())

        # Backend state that must survive a theme rebuild (§6.8/§6.16).
        self._api = VRChatAPI()
        self._secure_store = SecureStore(SESSION_BLOB_FILE)
        self._bridge = _Bridge()
        # Bound methods of `self` (App is a real QObject/QMainWindow
        # constructed on the main thread), not lambdas — see the note
        # in ui/login_dialog.py's _ResultRelay docstring for why a bare
        # lambda receiver doesn't reliably queue across threads, while
        # a genuine bound method does.
        self._bridge.status.connect(self._on_bridge_status)
        self._bridge.error.connect(self._on_bridge_error)

        from core.engine import Engine
        self._engine = Engine(
            api=self._api,
            get_config_cb=lambda: self._cfg,
            on_friend_event=self._bridge.friend_event.emit,
            on_instance_event=self._bridge.instance_event.emit,
            on_status=self._bridge.status.emit,
            on_error=self._bridge.error.emit,
        )

        self._build_root()
        self._build_tabs()

        QTimer.singleShot(0, self._ensure_logged_in)

    # ── Root window ───────────────────────────────────────────────────

    def _build_root(self):
        self.setWindowTitle(f"{theme.TITLE_PREFIX} VRChat Social Logger")
        self.resize(760, 640)
        self.setMinimumSize(560, 440)

        central = theme.StripeBackground()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 14, 8)

        title_lbl = QLabel(f"{theme.TITLE_PREFIX} VRChat Social Logger")
        title_lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
        title_lbl.setFont(theme.qt_font(13, bold=True))
        header_layout.addWidget(title_lbl)
        header_layout.addStretch(1)

        self._account_lbl = QLabel(self._account_status_text())
        self._account_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        self._account_lbl.setFont(theme.qt_font(9))
        header_layout.addWidget(self._account_lbl)

        header_layout.addSpacing(10)

        version_lbl = QLabel(f"v{VERSION}")
        version_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        version_lbl.setFont(theme.qt_font(9))
        header_layout.addWidget(version_lbl)

        root_layout.addWidget(header)

        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
        root_layout.addWidget(divider)

        self._notebook = QTabWidget()
        self._notebook.setDocumentMode(True)
        root_layout.addWidget(self._notebook, 1)

        footer = QWidget()
        footer.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 4, 14, 4)
        self._footer_lbl = QLabel("Ready")
        self._footer_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        self._footer_lbl.setFont(theme.qt_font(8))
        footer_layout.addWidget(self._footer_lbl)
        footer_layout.addStretch(1)
        root_layout.addWidget(footer)

        self.setCentralWidget(central)

    def _set_footer(self, text: str, is_error: bool = False):
        self._footer_lbl.setText(text)
        colour = theme.RED if is_error else theme.SUBTEXT
        self._footer_lbl.setStyleSheet(f"color: {colour}; background: transparent; border: none;")

    def _on_bridge_status(self, text: str):
        self._set_footer(text)

    def _on_bridge_error(self, text: str):
        self._set_footer(text, is_error=True)

    # ── Tabs ──────────────────────────────────────────────────────────

    def _build_tabs(self):
        self._instance_info_tab = InstanceInfoTab(
            self._cfg, self._save, self._open_help, self._open_settings,
            self._api, self._engine, self._bridge,
        )
        self._friends_feed_tab = FriendsFeedTab(
            self._cfg, self._save, self._open_help, self._open_settings,
            self._engine, self._bridge,
        )
        self._instance_log_tab = InstanceLogTab(
            self._cfg, self._save, self._open_help, self._open_settings,
            self._engine, self._bridge,
        )
        self._notebook.addTab(self._instance_info_tab, "  Current Instance  ")
        self._notebook.addTab(self._friends_feed_tab, "  Friends Feed  ")
        self._notebook.addTab(self._instance_log_tab, "  Instance Log  ")

    # ── Account / login ───────────────────────────────────────────────

    def _account_status_text(self) -> str:
        if self._api.is_logged_in():
            return "Logged in"
        return "Not logged in"

    def _ensure_logged_in(self):
        mode = self._cfg.get("secure_storage_mode", "keyring")

        if mode == "keyring":
            cookies = self._secure_store.load_keyring()
            if cookies and self._try_resume(cookies):
                return
            self._do_login()
            return

        if mode == "master_password":
            if not self._secure_store.has_master_password_blob():
                self._do_login()  # first run in this mode — nothing saved to unlock yet
                return
            for _attempt in range(3):
                password = open_master_password_prompt(self, self._cfg, "unlock")
                if password is None:
                    self._set_footer("Master password entry cancelled — logging in fresh.", is_error=True)
                    self._do_login()
                    return
                try:
                    cookies = self._secure_store.load_master_password(password)
                except WrongPassword:
                    password = ""  # drop our reference immediately
                    continue  # let them retry — up to 3 tries before falling back to fresh login
                except CorruptBlob as exc:
                    # Not something retyping the password can fix —
                    # stop asking, tell them plainly, and start fresh.
                    password = ""
                    self._set_footer(f"Saved session is unreadable ({exc}) — logging in fresh.", is_error=True)
                    break
                except (FileNotFoundError, OSError):
                    break
                password = ""
                if self._try_resume(cookies):
                    return
                break
            self._do_login()
            return

        # mode == "none" — never persisted, always log in fresh.
        self._do_login()

    def _try_resume(self, cookies: dict) -> bool:
        """Attempt to resume a session from previously-saved cookies.
        Returns True and updates the UI if the session's still valid;
        returns False (leaving the caller to fall back to a fresh
        login) if it's expired or otherwise rejected."""
        self._api.import_cookies(cookies)
        try:
            self._api.get_current_user()
        except VRChatAPIError:
            self._api.clear_cookies()
            return False
        self._account_lbl.setText(self._account_status_text())
        if self._cfg.get("auto_start"):
            self._engine.start()
            self._bridge.engine_status.emit(True)
        return True

    def _do_login(self):
        user = open_login(self, self._api, saved_username=self._cfg.get("username", ""))
        if user is not None:
            self._cfg["username"] = user.get("username", self._cfg.get("username", ""))
            self._save()
            self._account_lbl.setText(self._account_status_text())
            self._set_footer(f"Logged in as {user.get('displayName', user.get('username', '?'))}")
            self._persist_session()
        else:
            self._set_footer("Not logged in — Friends Feed and Friends-in-instance will be empty.", is_error=True)

    def _persist_session(self):
        mode = self._cfg.get("secure_storage_mode", "keyring")
        cookies = self._api.export_cookies()
        if mode == "keyring":
            try:
                self._secure_store.save_keyring(cookies)
            except RuntimeError as exc:
                self._set_footer(str(exc), is_error=True)
        elif mode == "master_password":
            password = open_master_password_prompt(self, self._cfg, "create")
            if password:
                self._secure_store.save_master_password(cookies, password)
                password = ""  # drop our reference immediately after use
        # mode == "none": deliberately don't persist anything.

    def _do_logout(self):
        self._engine.stop()
        self._bridge.engine_status.emit(False)
        self._api.logout()
        self._secure_store.clear_keyring()
        self._secure_store.clear_master_password()
        self._account_lbl.setText(self._account_status_text())
        self._set_footer("Logged out.")

    # ── Config ────────────────────────────────────────────────────────

    def _save(self):
        save_config(self._cfg)

    def _reset_to_defaults(self):
        defaults = get_defaults()
        keep = {k: self._cfg[k] for k in ("theme_mode", "username") if k in self._cfg}
        self._cfg.clear()
        self._cfg.update(defaults)
        self._cfg.update(keep)
        self._save()

    # ── Dialogs ───────────────────────────────────────────────────────

    def _open_settings(self):
        open_settings(
            parent=self,
            cfg=self._cfg,
            save_cb=self._save,
            reset_cb=self._reset_to_defaults,
            theme_cb=self._set_theme,
            account_status_cb=self._account_status_text,
            login_cb=self._do_login,
            logout_cb=self._do_logout,
        )

    def _open_help(self):
        open_help(self)

    # ── Theme ─────────────────────────────────────────────────────────

    def _set_theme(self, mode: str):
        self._cfg["theme_mode"] = mode
        self._save()
        theme.set_theme(mode)
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.setStyleSheet(theme.qss())
        self._rebuild_ui()

    def _rebuild_ui(self):
        old_central = self.takeCentralWidget()
        if old_central is not None:
            old_central.deleteLater()

        self._build_root()
        self._build_tabs()

        self.show()
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.processEvents()

    # ── Lifecycle ─────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._instance_info_tab.destroy_all()
        self._friends_feed_tab.destroy_all()
        self._instance_log_tab.destroy_all()
        self._engine.stop()
        self._save()
        super().closeEvent(event)