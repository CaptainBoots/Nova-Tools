"""
ui/app.py
─────────
Root window (Qt). Creates the two-tab notebook and wires together:
  - BuilderTab  (page/slot editor)
  - ChatboxTab  (live preview + controls)
  - OSC loop start/stop/restart
  - Config load/save
  - Settings dialog
  - Theme selection

The OSC loop itself (osc_loop.py) is unchanged — it's plain threading, no
UI-toolkit dependency. The only thing that changes is how its callbacks
reach the UI thread: a small QObject bridge re-emits them as Qt signals
(thread-safe by default across threads).
"""

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QApplication,
)

from config import load_config, save_config, get_defaults, SPOTIFY_BLOB_FILE
from core.osc_loop import start_loop, stop_loop
from core.secure_store import SecureStore
from core.state import AppState
from core import spotify_api
from monitors import media as media_mod
from ui.builder import BuilderTab
from ui.chatbox_tab import ChatboxTab
from ui.help_dialog import open_help
from ui.settings_dialog import open_settings
from ui import theme

try:
    from main import VERSION
except ImportError:
    VERSION = "version error"


class _LoopBridge(QObject):
    """Re-emits osc_loop's callbacks as Qt signals so they land safely on
    the UI thread no matter which worker thread calls them."""
    status_signal  = Signal(str)
    preview_signal = Signal(str)


class _SpotifyCtx:
    """Owns the live Spotify session across Settings dialog open/close —
    the dialog itself is rebuilt from scratch every time it's opened
    (see ui/settings_dialog.py), so anything that needs to survive that
    (the actual connected session) has to live up here in App instead."""
    def __init__(self, secure_store: SecureStore):
        self.secure_store = secure_store
        self._session: spotify_api.SpotifySession | None = None

    def get_session(self):
        return self._session

    def set_session(self, session):
        self._session = session

    def status_text(self) -> str:
        return "Spotify: connected" if self._session is not None else "Spotify: not connected"


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self._cfg   = load_config()
        self._state = AppState()

        # Apply state flags from config
        self._state.slow_mode        = self._cfg.get("slow_mode", False)
        self._state.speed_mode       = self._cfg.get("speed_mode", False)
        self._state.media_title_trim = self._cfg.get("media_title_trim", True)
        self._state.cat_mode         = self._cfg.get("cat_mode", False)
        self._state.progress_filled  = self._cfg.get("progress_filled", self._state.progress_filled)
        self._state.progress_border  = self._cfg.get("progress_border", self._state.progress_border)
        self._state.progress_empty   = self._cfg.get("progress_empty",  self._state.progress_empty)

        # ── Spotify (Settings -> Media -> Spotify) ──────────────────────────
        self._spotify_ctx = _SpotifyCtx(SecureStore(SPOTIFY_BLOB_FILE))

        # Only "keyring" mode can restore a saved login silently at launch
        # with no prompt at all. "master_password" mode unlocks lazily the
        # first time Settings is opened instead (ui/spotify_section.py) —
        # popping a password prompt before the person has even opened
        # Settings would just be a different unwanted popup.
        if self._cfg.get("secure_storage_mode", "keyring") == "keyring":
            saved_tokens = self._spotify_ctx.secure_store.load_keyring()
            if saved_tokens:
                self._spotify_ctx.set_session(spotify_api.SpotifySession(
                    self._cfg.get("spotify_client_id", ""),
                    saved_tokens,
                    on_tokens_changed=self._spotify_ctx.secure_store.save_keyring,
                ))

        media_mod.set_priority_order(self._cfg.get("media_priority_order"))
        media_mod.set_spotify_session_provider(self._spotify_ctx.get_session)

        self._bridge = _LoopBridge()
        self._last_status  = "Stopped"
        self._last_preview = ""

        self._build_root()
        self._build_tabs()
        self._connect_bridge()

        # The central widget's alpha was already set in _build_root, but the
        # two tab widgets (ChatboxTab/BuilderTab) are ALSO StripeBackground
        # instances covering nearly the whole window, and they default to
        # fully opaque — apply the saved value to everything now that they
        # exist, or the slider would only visibly affect a thin sliver
        # around the header.
        self._apply_bg_alpha_everywhere(self._bg_alpha)

    def _connect_bridge(self):
        """(Re)wire the OSC loop callbacks to the current ChatboxTab. Split
        out so _rebuild_ui can reconnect to a freshly built tab after a
        live theme change."""
        if getattr(self, "_bridge_connected", False):
            for sig in (self._bridge.status_signal, self._bridge.preview_signal):
                sig.disconnect()
        self._bridge_connected = True

        def _on_status(text):
            self._last_status = text
            self._chatbox_tab.set_status(text)

        def _on_preview(text):
            self._last_preview = text
            self._chatbox_tab.set_preview(text)

        self._bridge.status_signal.connect(_on_status)
        self._bridge.preview_signal.connect(_on_preview)
        # Restore whatever was last known (e.g. after a theme rebuild while
        # the loop is running) instead of showing a blank/stale "Stopped".
        self._chatbox_tab.set_status(self._last_status)
        self._chatbox_tab.set_preview(self._last_preview)

    # ── Root window ───────────────────────────────────────────────────────────

    def _build_root(self):
        self.setWindowTitle(f"{theme.TITLE_PREFIX} OSC-Chatbox")
        self.resize(1080, 720)
        self.setMinimumSize(150, 30)

        # ── Background-only transparency ─────────────────────────────────────
        # NOTE on transparency vs. the native window frame: true per-pixel
        # desktop compositing on Windows normally wants FramelessWindowHint
        # paired with WA_TranslucentBackground — without it, Qt/Windows
        # doesn't reliably composite arbitrary alpha in the client area, so
        # this slider may have little to no visible see-through effect with
        # the native frame restored (it may just look like a slightly
        # different shade, similar to the very first version of this).
        # That's the deliberate trade-off here: going frameless to get real
        # transparency meant losing native resize/drag/snap behaviour,
        # which breaks tools like FancyZones — those need a standard
        # top-level window, not a custom-drawn one, to hook into properly.
        # Getting both at once requires intercepting native Win32 messages
        # (WM_NCHITTEST) to tell Windows which regions act as a resize
        # border/title bar on an otherwise-frameless window — doable, but
        # real native platform code that needs testing on actual Windows to
        # get right, not something to guess at blind. Flagging it as a
        # possible follow-up rather than shipping an unverified version.
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        saved_opacity = self._cfg.get("transparency_opacity", 1.0)
        self._bg_alpha = max(0.0, min(1.0, float(saved_opacity)))

        central = theme.StripeBackground()
        central.set_bg_alpha(self._bg_alpha)
        self._bg_canvas = central
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 14, 8)

        title_lbl = QLabel(f"{theme.TITLE_PREFIX} OSC-Chatbox")
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
        self._chatbox_tab = ChatboxTab(
            self._cfg, self._state,
            save_cb     = self._save,
            start_cb    = self._start,
            stop_cb     = self._stop,
            restart_cb  = self._restart,
            settings_cb = self._open_settings,
            help_cb     = self._open_help,
        )
        self._builder_tab = BuilderTab(self._cfg, save_cb=self._save)

        self._notebook.addTab(self._chatbox_tab, "  Chatbox  ")
        self._notebook.addTab(self._builder_tab, "  Builder  ")

    # ── OSC loop control ──────────────────────────────────────────────────────

    def _start(self):
        if self._state.running:
            return
        self._sync_state_from_cfg()
        start_loop(
            cfg        = self._cfg,
            state      = self._state,
            status_cb  = lambda text: self._bridge.status_signal.emit(text),
            preview_cb = lambda text: self._bridge.preview_signal.emit(text),
        )

    def _stop(self):
        stop_loop(self._state)

    def _restart(self):
        self._stop()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1200, self._start)

    # ── Config sync ───────────────────────────────────────────────────────────

    def _sync_state_from_cfg(self):
        self._state.slow_mode        = self._cfg.get("slow_mode", False)
        self._state.speed_mode       = self._cfg.get("speed_mode", False)
        self._state.media_title_trim = self._cfg.get("media_title_trim", True)
        self._state.cat_mode         = self._cfg.get("cat_mode", False)
        self._state.progress_filled  = self._cfg.get("progress_filled", self._state.progress_filled)
        self._state.progress_border  = self._cfg.get("progress_border", self._state.progress_border)
        self._state.progress_empty   = self._cfg.get("progress_empty",  self._state.progress_empty)

    def _save(self):
        self._cfg["slow_mode"]        = self._state.slow_mode
        self._cfg["speed_mode"]       = self._state.speed_mode
        self._cfg["media_title_trim"] = self._state.media_title_trim
        self._cfg["cat_mode"]         = self._state.cat_mode
        self._cfg["progress_filled"]  = self._state.progress_filled
        self._cfg["progress_border"]  = self._state.progress_border
        self._cfg["progress_empty"]   = self._state.progress_empty
        save_config(self._cfg)

    # ── Settings dialog ───────────────────────────────────────────────────────

    def _open_settings(self):
        open_settings(
            parent        = self,
            state         = self._state,
            cfg           = self._cfg,
            save_cb       = self._save,
            reset_cb      = self._reset_to_defaults,
            theme_cb      = self._set_theme,
            opacity_cb    = self._set_opacity,
            spotify_ctx   = self._spotify_ctx,
        )

    def _open_help(self):
        open_help(self)

    def _reset_to_defaults(self):
        defaults = get_defaults()
        keep = {k: self._cfg[k] for k in
                ("pages", "osc_ip", "osc_port", "interface", "location", "theme_mode")
                if k in self._cfg}
        self._cfg.clear()
        self._cfg.update(defaults)
        self._cfg.update(keep)
        self._sync_state_from_cfg()
        self._save()
        self._builder_tab.refresh()

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
        """Tear down and reconstruct the central widget + both tabs with
        whatever the current theme.* colours now are, and reconnect the OSC
        loop callbacks to the new ChatboxTab. This is what makes theme
        switching "live" — colours are baked into a lot of individual
        widgets as literal stylesheet strings at construction time (that's
        how Qt Style Sheets work), so recolouring in place isn't practical;
        rebuilding the tree is instant and doesn't touch the running OSC
        loop or lose your connection, so it's effectively the same as an
        auto-restart of just the UI, without actually relaunching the app."""
        old_central = self.takeCentralWidget()
        if old_central is not None:
            old_central.deleteLater()

        self._build_root()
        self._build_tabs()
        self._connect_bridge()
        self._apply_bg_alpha_everywhere(self._bg_alpha)

        # Cheap safety net — setCentralWidget() shouldn't hide the window,
        # but forcing show() costs nothing and guards against edge cases.
        self.show()

        # setCentralWidget() queues a layout/show pass for the next event
        # loop iteration — pump it now so the rebuild is visually instant
        # rather than leaving a one-frame gap before Qt catches up.
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.processEvents()

    # ── Opacity (background-only — see WA_TranslucentBackground above) ───────

    def _apply_bg_alpha_everywhere(self, alpha_val: float):
        """StripeBackground is used by the central widget AND both tabs
        (ChatboxTab/BuilderTab) — all three need the same alpha applied,
        since together they cover essentially the entire window."""
        for widget in (self._bg_canvas, self._chatbox_tab, self._builder_tab):
            widget.set_bg_alpha(alpha_val)

    def _set_opacity(self, alpha_val: float):
        alpha_val = max(0.0, min(1.0, float(alpha_val)))
        self._cfg["transparency_opacity"] = alpha_val
        self._save()
        self._bg_alpha = alpha_val
        self._apply_bg_alpha_everywhere(alpha_val)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._stop()
        self._save()
        super().closeEvent(event)

    # ── Entry point ───────────────────────────────────────────────────────────
    # Kept so main.py's existing `app = App(); app.run()` still works
    # unchanged. If a QApplication doesn't exist yet (normal case, since
    # QMainWindow needs one to already exist before it's constructed), this
    # creates one.

    def run(self):
        self.show()
        instance = QApplication.instance()
        if instance is not None:
            instance.exec()