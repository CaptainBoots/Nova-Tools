"""
ui/app.py
─────────
Root window for OSC-ScriptMaker.
Same structure as the rest of the suite: header bar with title +
version, dark tab widget, single tab.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QApplication,
)

from config import load_config, save_config, get_defaults
from ui.scriptmaker_tab import ScriptMakerTab
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

        # Apply the saved theme before building anything — otherwise the
        # window is built with theme.py's hardcoded default palette and
        # the saved theme_mode only takes effect the next time the user
        # opens Settings and picks a theme (even the same one).
        theme.set_theme(self._cfg.get("theme_mode", "rich_purple"))
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.setStyleSheet(theme.qss())

        self._build_root()
        self._build_tabs()
        self._script_tab.load_scripts()

    # ── Root window ───────────────────────────────────────────────────────────

    def _build_root(self):
        self.setWindowTitle(f"{theme.TITLE_PREFIX} OSC-ScriptMaker")
        self.resize(760, 720)
        self.setMinimumSize(560, 480)

        central = theme.StripeBackground()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 14, 8)

        title_lbl = QLabel(f"{theme.TITLE_PREFIX} OSC-ScriptMaker")
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
        self._script_tab = ScriptMakerTab(
            self._cfg,
            save_cb     = self._save,
            help_cb     = self._open_help,
            settings_cb = self._open_settings,
        )
        self._notebook.addTab(self._script_tab, "  Scripts  ")

    # ── Config ────────────────────────────────────────────────────────────────

    def _save(self):
        self._cfg["scripts"] = self._script_tab.collect_scripts()
        save_config(self._cfg)

    def _reset_to_defaults(self):
        defaults = get_defaults()
        keep_scripts = self._cfg.get("scripts", [])
        keep_theme = self._cfg.get("theme_mode", "rich_purple")
        self._cfg.clear()
        self._cfg.update(defaults)
        self._cfg["scripts"] = keep_scripts
        self._cfg["theme_mode"] = keep_theme
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
        """Tear down and reconstruct the central widget + tab with whatever
        the current theme.* colours now are. The engine's OSC listener and
        timer thread are cleanly shut down first — the rebuilt tab reloads
        scripts from cfg the same way a fresh launch would, just without
        needing to relaunch."""
        was_connected = self._script_tab.engine.is_running
        self._script_tab.destroy_all()

        old_central = self.takeCentralWidget()
        if old_central is not None:
            old_central.deleteLater()

        self._build_root()
        self._build_tabs()
        self._script_tab.load_scripts()
        if was_connected and not self._script_tab.engine.is_running:
            self._script_tab.start_engine()

        self.show()
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.processEvents()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._save()
        self._script_tab.destroy_all()
        super().closeEvent(event)