"""
ui/app.py
─────────
Root window for VRChat Local Favorites. Same header/tabs structure as
the rest of VRChat-Tools. Owns the VRChatAPI session and FavoritesStore
so they survive a theme rebuild (§6.8), and the login/secure-storage
flow — same pattern as VRChat-Social-Logger's app.py (already debugged
there), reused here rather than re-derived.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QApplication

from config import load_config, save_config, get_defaults, SESSION_BLOB_FILE
from core.vrchat_api import VRChatAPI, VRChatAPIError
from core.secure_store import SecureStore, WrongPassword, CorruptBlob
from core.favorites_store import FavoritesStore
from ui.favorites_tab import FavoritesCategoryTab
from ui.help_dialog import open_help
from ui.settings_dialog import open_settings
from ui.login_dialog import open_login
from ui.master_password_dialog import open_master_password_prompt
from ui.import_dialog import open_import_dialog
from ui import theme

try:
    from main import VERSION
except ImportError:
    VERSION = "version error"


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self._cfg = load_config()

        theme.set_theme(self._cfg.get("theme_mode", "rich_purple"))
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.setStyleSheet(theme.qss())

        # Backend state that must survive a theme rebuild.
        self._api = VRChatAPI()
        self._secure_store = SecureStore(SESSION_BLOB_FILE)
        self._favorites_store = FavoritesStore(self._cfg.get("favorites_dir"))

        self._build_root()
        self._build_tabs()

        QTimer.singleShot(0, self._ensure_logged_in)

    # ── Root window ───────────────────────────────────────────────────

    def _build_root(self):
        self.setWindowTitle(f"{theme.TITLE_PREFIX} VRChat Local Favorites")
        self.resize(820, 640)
        self.setMinimumSize(600, 440)

        central = theme.StripeBackground()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 14, 8)

        title_lbl = QLabel(f"{theme.TITLE_PREFIX} VRChat Local Favorites")
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

    # ── Tabs ──────────────────────────────────────────────────────────

    def _build_tabs(self):
        self._tabs = {}
        for category, label in (
            ("worlds", "  Worlds  "),
            ("avatars", "  Avatars  "),
            ("players", "  Players  "),
            ("instances", "  Instances  "),
        ):
            tab = FavoritesCategoryTab(
                category, self._cfg, self._api, self._favorites_store,
                self._open_help, self._open_settings,
            )
            self._tabs[category] = tab
            self._notebook.addTab(tab, label)

    def _reload_all_tabs(self):
        for tab in self._tabs.values():
            tab._reload_tree()

    # ── Account / login ───────────────────────────────────────────────

    def _account_status_text(self) -> str:
        return "Logged in" if self._api.is_logged_in() else "Not logged in"

    def _ensure_logged_in(self):
        mode = self._cfg.get("secure_storage_mode", "keyring")

        if mode == "keyring":
            cookies = self._secure_store.load_keyring()
            if cookies and self._try_resume(cookies):
                self._maybe_prompt_first_launch_import()
                return
            self._do_login()
            self._maybe_prompt_first_launch_import()
            return

        if mode == "master_password":
            if not self._secure_store.has_master_password_blob():
                self._do_login()
                self._maybe_prompt_first_launch_import()
                return
            for _attempt in range(3):
                password = open_master_password_prompt(self, self._cfg, "unlock")
                if password is None:
                    self._set_footer("Master password entry cancelled — logging in fresh.", is_error=True)
                    self._do_login()
                    self._maybe_prompt_first_launch_import()
                    return
                try:
                    cookies = self._secure_store.load_master_password(password)
                except WrongPassword:
                    password = ""
                    continue
                except CorruptBlob as exc:
                    password = ""
                    self._set_footer(f"Saved session is unreadable ({exc}) — logging in fresh.", is_error=True)
                    break
                except (FileNotFoundError, OSError):
                    break
                password = ""
                if self._try_resume(cookies):
                    self._maybe_prompt_first_launch_import()
                    return
                break
            self._do_login()
            self._maybe_prompt_first_launch_import()
            return

        self._do_login()
        self._maybe_prompt_first_launch_import()

    def _try_resume(self, cookies: dict) -> bool:
        self._api.import_cookies(cookies)
        try:
            self._api.get_current_user()
        except VRChatAPIError:
            self._api.clear_cookies()
            return False
        self._account_lbl.setText(self._account_status_text())
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
            self._set_footer("Not logged in — searching, importing, and switching avatars won't work.", is_error=True)

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
                password = ""

    def _do_logout(self):
        self._api.logout()
        self._secure_store.clear_keyring()
        self._secure_store.clear_master_password()
        self._account_lbl.setText(self._account_status_text())
        self._set_footer("Logged out.")

    # ── First-launch import ──────────────────────────────────────────

    def _maybe_prompt_first_launch_import(self):
        if self._cfg.get("did_first_launch_import_prompt"):
            return
        self._cfg["did_first_launch_import_prompt"] = True
        self._save()
        if not self._api.is_logged_in():
            return
        self._trigger_import()

    def _trigger_import(self):
        open_import_dialog(self, self._api, self._favorites_store, on_done=self._reload_all_tabs)

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
            import_cb=self._trigger_import,
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
        for tab in self._tabs.values():
            tab.destroy_all()
        self._save()
        super().closeEvent(event)
