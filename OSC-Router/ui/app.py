"""
ui/app.py
─────────
Root window for OSC-Router.
Same structure and theme as OSC-Chatbox.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QMessageBox, QApplication,
)

from config import load_config, save_config, get_defaults
from core.router import OscRouter, OutputTarget
from core.source import OscSource
from ui.help_dialog import open_help
from ui.router_tab import RouterTab
from ui.settings_dialog import open_settings
from ui import theme

try:
    from main import VERSION
except ImportError:
    VERSION = "version error"


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self._cfg    = load_config()
        self._router = OscRouter()

        self._build_root()
        self._build_tabs()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000)

    # ── Root window ───────────────────────────────────────────────────────────

    def _build_root(self):
        self.setWindowTitle(f"{theme.TITLE_PREFIX} OSC-Router")
        self.resize(640, 720)
        self.setMinimumSize(500, 460)

        central = theme.StripeBackground()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 14, 8)

        title_lbl = QLabel(f"{theme.TITLE_PREFIX} OSC-Router")
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
        self._router_tab = RouterTab(
            self._cfg, self._router,
            save_cb     = self._save,
            start_cb    = self._start,
            stop_cb     = self._stop,
            restart_cb  = self._restart,
            settings_cb = self._open_settings,
            help_cb     = self._open_help,
        )
        self._notebook.addTab(self._router_tab, "  Router  ")

        for src in self._cfg.get("sources", []):
            self._router_tab.add_source_row(src.get("name", "Source"), src.get("port", 9001))

        for out in self._cfg.get("outputs", []):
            self._router_tab.add_output_row(
                name       = out.get("name", "Output"),
                ip         = out.get("ip",   "127.0.0.1"),
                port       = out.get("port", 9000),
                subscribed = out.get("sources", []),
            )

    # ── Router control ────────────────────────────────────────────────────────

    def _start(self):
        if self._router.running:
            return

        cfg = self._router_tab.collect_config()
        self._cfg.update(cfg)
        self._save()

        self._router.sources = [
            OscSource(s["name"], s["port"]) for s in cfg["sources"]
        ]

        self._router.outputs = [
            OutputTarget(
                name         = o["name"],
                ip           = o["ip"],
                port         = o["port"],
                source_names = o.get("sources", [s["name"] for s in cfg["sources"]]),
            )
            for o in cfg["outputs"]
        ]

        result = self._router.start()

        msgs = []
        if result["sources"]:
            msgs.append(f"Sources failed to bind: {', '.join(result['sources'])}")
        if result["outputs"]:
            msgs.append(f"Outputs failed to open: {', '.join(result['outputs'])}")
        if msgs:
            QMessageBox.warning(self, "Start Issues", "\n".join(msgs))

        self._router_tab.set_status("Running" if self._router.running else "Failed")

    def _stop(self):
        self._router.stop()
        self._router_tab.set_status("Stopped")

    def _restart(self):
        self._stop()
        QTimer.singleShot(800, self._start)

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
        the current theme.* colours now are. self._router runs on its own
        background thread independent of the UI, so a running router
        keeps routing straight through the rebuild — only the status
        label needs to be told what's actually going on afterward, since
        the fresh RouterTab starts out assuming "Stopped"."""
        old_central = self.takeCentralWidget()
        if old_central is not None:
            old_central.deleteLater()

        self._build_root()
        self._build_tabs()
        self._router_tab.set_status("Running" if self._router.running else "Stopped")

        self.show()
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.processEvents()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _tick(self):
        self._router_tab.tick()

    def closeEvent(self, event):
        self._router.stop()
        self._save()
        super().closeEvent(event)