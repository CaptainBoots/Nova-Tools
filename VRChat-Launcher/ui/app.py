"""
ui/app.py
─────────
Root window for VRChat Launcher.
Same structure and theme as the other OSC tools: header bar with
title + version, dark tab widget, single tab.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QApplication,
)

from config import load_config, save_config, get_defaults
from core.launcher import LauncherProcessManager, resync_uid_counter
from ui.launcher_tab import LauncherTab
from ui.help_dialog import open_help
from ui.settings_dialog import open_settings
from ui import theme

try:
    from main import VERSION
except ImportError:
    VERSION = "version error"


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self._cfg = load_config()

        # Owned here, not inside the tab — this must survive a theme
        # rebuild (§6.8) without losing track of any VRChat instances
        # the person has already launched.
        self._process_mgr = LauncherProcessManager()

        self._build_root()
        self._build_tabs()

    # ── Root window ───────────────────────────────────────────────────────────

    def _build_root(self):
        self.setWindowTitle(f"{theme.TITLE_PREFIX} VRChat Launcher")
        self.resize(960, 680)
        self.setMinimumSize(920, 480)

        central = theme.StripeBackground()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 14, 8)

        title_lbl = QLabel(f"{theme.TITLE_PREFIX} VRChat Launcher")
        title_lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
        title_lbl.setFont(theme.qt_font(13, bold=True))
        header_layout.addWidget(title_lbl)
        header_layout.addStretch(1)

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

        self.setCentralWidget(central)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _build_tabs(self):
        self._launcher_tab = LauncherTab(
            self._cfg,
            self._process_mgr,
            save_cb     = self._save,
            help_cb     = self._open_help,
            settings_cb = self._open_settings,
        )
        self._notebook.addTab(self._launcher_tab, "  Launcher  ")

    # ── Config ────────────────────────────────────────────────────────────────

    def _save(self):
        save_config(self._cfg)

    def _reset_to_defaults(self):
        defaults = get_defaults()
        keep = {k: self._cfg[k] for k in ("theme_mode",) if k in self._cfg}
        self._cfg.clear()
        self._cfg.update(defaults)
        self._cfg.update(keep)
        resync_uid_counter(self._cfg["profiles"])
        self._save()

    # ── Dialogs ───────────────────────────────────────────────────────────────

    def _open_settings(self):
        open_settings(
            parent   = self,
            cfg      = self._cfg,
            save_cb  = self._save,
            reset_cb = self._reset_to_defaults,
            theme_cb = self._set_theme,
        )

    def _open_help(self):
        open_help(self)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _set_theme(self, mode: str):
        self._cfg["theme_mode"] = mode
        self._save()
        theme.set_theme(mode)
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.setStyleSheet(theme.qss())
        self._rebuild_ui()

    def _rebuild_ui(self):
        """Tear down and reconstruct the central widget + tab with
        whatever the current theme.* colours now are. The process
        manager (self._process_mgr) is owned by App, not the tab, and
        is handed to the freshly-built tab unchanged — any VRChat
        instances already launched keep running straight through the
        rebuild, same as the "backend runs independent of the UI"
        case in the porting guide."""
        self._launcher_tab.stop_polling()

        old_central = self.takeCentralWidget()
        if old_central is not None:
            old_central.deleteLater()

        self._build_root()
        self._build_tabs()

        self.show()
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.processEvents()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        # Deliberately does NOT kill any launched VRChat instances —
        # they're independent processes and should keep running after
        # this tool closes, same as the original.
        self._launcher_tab.stop_polling()
        self._save()
        super().closeEvent(event)
