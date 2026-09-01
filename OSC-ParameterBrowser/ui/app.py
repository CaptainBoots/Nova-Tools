"""
ui/app.py
─────────
Root window for OSC Parameter Browser.
Same structure and theme as the other OSC tools: header bar with
title + version, dark tab widget, single tab.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QMessageBox, QApplication,
)

from config import load_config, save_config, get_defaults
from core.osc_bridge import PYTHON_OSC
from ui.browser_tab import BrowserTab
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

        self._build_root()
        self._build_tabs()

        if not PYTHON_OSC:
            QMessageBox.warning(
                self, "Missing Dependency",
                "python-osc is not installed.\nSend functions will be unavailable.\n"
                "Run: pip install python-osc"
            )

    # ── Root window ───────────────────────────────────────────────────────────

    def _build_root(self):
        self.setWindowTitle(f"{theme.TITLE_PREFIX} OSC Parameter Browser")
        self.resize(850, 680)
        self.setMinimumSize(600, 460)

        central = theme.StripeBackground()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 14, 8)

        title_lbl = QLabel(f"{theme.TITLE_PREFIX} OSC Parameter Browser")
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
        self._browser_tab = BrowserTab(
            self._cfg,
            save_cb     = self._save,
            help_cb     = self._open_help,
            settings_cb = self._open_settings,
        )
        self._notebook.addTab(self._browser_tab, "  Browser  ")

    # ── Config ────────────────────────────────────────────────────────────────

    def _save(self):
        save_config(self._cfg)

    def _reset_to_defaults(self):
        defaults = get_defaults()
        keep = {k: self._cfg[k] for k in ("theme_mode",) if k in self._cfg}
        self._cfg.clear()
        self._cfg.update(defaults)
        self._cfg.update(keep)
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
        the current theme.* colours now are. Captured parameter data and
        an active listener (if any) are handed off to the new tab rather
        than lost — the listener itself is never stopped, so its socket
        stays bound and it keeps receiving packets the entire time."""
        preserved = self._browser_tab.export_state()

        old_central = self.takeCentralWidget()
        if old_central is not None:
            old_central.deleteLater()

        self._build_root()
        self._build_tabs()
        self._browser_tab.import_state(preserved)

        self.show()
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.processEvents()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._browser_tab.destroy_listener()
        self._save()
        super().closeEvent(event)