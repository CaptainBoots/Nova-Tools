"""
ui/spotify_section.py
────────────────────────
The "Spotify" subsection inside Settings -> Media. Deliberately NOT a
popup dialog — everything lives inline in the same collapsible Media
section as the priority list, per how this was asked for.

Connecting still has to leave the app at some point (Spotify's login
page, 2FA, and password entry are Spotify's own UI, not ours — there is
no username/password field here because Spotify's API doesn't accept
one from third-party apps; only OAuth). That "leaving the app" is the
person's own default system browser (core.spotify_api.connect_blocking
-> webbrowser.open), not an embedded webview or a Qt popup window —
this file never renders Spotify's login form itself.

Storage options mirror VRChat Social Logger's account section exactly
(same three modes, same combo box pattern, same wording) — see
core/secure_store.py.

Threading: the OAuth round-trip (open browser, wait up to 2 minutes for
the redirect, exchange the code) blocks on network + user action, so it
runs on a QThread. Signal-to-signal relay via a real QObject
(_ConnectRelay) — same pattern and same reasoning as
ui/login_dialog.py's _ResultRelay in VRChat Social Logger: a bare
Python closure has no .thread() for Qt to inspect, so connecting a
worker's signal straight to one doesn't reliably queue across threads.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from core import spotify_api
from core.secure_store import WrongPassword, CorruptBlob
from ui import theme
from ui.master_password_dialog import open_master_password_prompt

REDIRECT_NOTE = (
    "Needs your own free Spotify client ID (Dashboard -> Create app -> "
    "redirect URI http://127.0.0.1:0/callback, or tick \"skip\" for redirect "
    "URI if offered) — spotify doesn't allow third-party apps to share one."
)


class _ConnectWorker(QObject):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, client_id: str):
        super().__init__()
        self._client_id = client_id

    def run(self):
        try:
            tokens = spotify_api.connect_blocking(self._client_id)
            self.succeeded.emit(tokens)
        except spotify_api.SpotifyAuthTimeout:
            self.failed.emit("Timed out waiting for the browser — try again.")
        except spotify_api.SpotifyAuthDenied as exc:
            self.failed.emit(str(exc))
        except spotify_api.SpotifyAPIError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Could not connect: {exc}")


class _ConnectRelay(QObject):
    """See module docstring — real QObject so the cross-thread signal
    connection queues correctly onto the main thread."""
    succeeded = Signal(dict)
    failed = Signal(str)


def _maybe_restore_master_password_session(dlg, cfg: dict, spotify_ctx):
    """"master_password" mode can't restore a saved login silently at app
    launch the way "keyring" mode does (see ui/app.py) — it needs the
    password, which nobody's typed yet. So instead: the first time
    Settings is opened with a saved blob and no active session yet,
    prompt once here. If they cancel or mistype it, this just quietly
    tries again next time Settings is opened rather than erroring."""
    if spotify_ctx.get_session() is not None:
        return
    if cfg.get("secure_storage_mode") != "master_password":
        return
    if not spotify_ctx.secure_store.has_master_password_blob():
        return

    password = open_master_password_prompt(dlg, cfg, "unlock")
    if not password:
        return
    try:
        tokens = spotify_ctx.secure_store.load_master_password(password)
    except (WrongPassword, CorruptBlob):
        return
    finally:
        password = ""  # drop our reference immediately after use

    if tokens:
        spotify_ctx.set_session(spotify_api.SpotifySession(
            cfg.get("spotify_client_id", ""), tokens,
            on_tokens_changed=None,  # see build_spotify_section's docstring
        ))


def build_spotify_section(parent_layout: QVBoxLayout, dlg, cfg: dict, save_cb, spotify_ctx):
    """spotify_ctx (owned by ui/app.py, survives Settings being reopened)
    needs:
        .secure_store        — core.secure_store.SecureStore instance
        .get_session()        -> core.spotify_api.SpotifySession | None
        .set_session(session_or_None)
        .status_text()        -> str, for the label
    """
    _maybe_restore_master_password_session(dlg, cfg, spotify_ctx)

    note = QLabel(REDIRECT_NOTE)
    note.setWordWrap(True)
    note.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    note.setFont(theme.qt_font(8))
    parent_layout.addWidget(note)

    client_id_row = QHBoxLayout()
    client_id_lbl = QLabel("Client ID:")
    client_id_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
    client_id_lbl.setFont(theme.qt_font(9))
    client_id_row.addWidget(client_id_lbl)

    client_id_edit = QLineEdit(cfg.get("spotify_client_id", ""))
    client_id_edit.setPlaceholderText("from developer.spotify.com/dashboard")
    client_id_edit.setStyleSheet(theme.line_edit_qss())
    client_id_row.addWidget(client_id_edit, 1)
    parent_layout.addLayout(client_id_row)

    def _client_id_changed():
        cfg["spotify_client_id"] = client_id_edit.text().strip()
        save_cb()

    client_id_edit.editingFinished.connect(_client_id_changed)

    # ── Storage mode — same 3 options/wording as VRChat Social Logger ────────
    storage_row = QHBoxLayout()
    storage_lbl = QLabel("Remember login using:")
    storage_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    storage_lbl.setFont(theme.qt_font(9))
    storage_row.addWidget(storage_lbl)

    storage_combo = QComboBox()
    storage_options = [
        ("keyring", "OS credential store (recommended)"),
        ("master_password", "Master password (typed each launch)"),
        ("none", "Don't remember — reconnect every launch"),
    ]
    for value, label in storage_options:
        storage_combo.addItem(label, userData=value)
    current_idx = next(
        (i for i, (v, _l) in enumerate(storage_options) if v == cfg.get("secure_storage_mode")), 0,
    )
    storage_combo.setCurrentIndex(current_idx)

    def _on_storage_changed(idx):
        cfg["secure_storage_mode"] = storage_combo.itemData(idx)
        save_cb()

    storage_combo.currentIndexChanged.connect(_on_storage_changed)
    storage_row.addWidget(storage_combo, 1)
    parent_layout.addLayout(storage_row)

    storage_note = QLabel(
        "Takes effect next time you connect — disconnect and reconnect to "
        "switch an already-saved login to the new mode."
    )
    storage_note.setWordWrap(True)
    storage_note.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    storage_note.setFont(theme.qt_font(7))
    parent_layout.addWidget(storage_note)

    # ── Status + Connect/Disconnect ──────────────────────────────────────────
    status_lbl = QLabel(spotify_ctx.status_text())
    status_lbl.setWordWrap(True)
    status_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
    status_lbl.setFont(theme.qt_font(9, bold=True))
    parent_layout.addWidget(status_lbl)

    btn_row = QHBoxLayout()
    connect_btn = QPushButton("Connect Spotify")
    connect_btn.setStyleSheet(theme.accent_button_qss())
    connect_btn.setFont(theme.qt_font(9, bold=True))
    btn_row.addWidget(connect_btn)

    disconnect_btn = QPushButton("Disconnect")
    disconnect_btn.setStyleSheet(theme.subtle_button_qss())
    disconnect_btn.setFont(theme.qt_font(9))
    btn_row.addWidget(disconnect_btn)
    btn_row.addStretch(1)
    parent_layout.addLayout(btn_row)

    _thread_state = {"thread": None, "worker": None, "relay": None, "busy": False}

    def _refresh_buttons():
        connected = spotify_ctx.get_session() is not None
        status_lbl.setText(spotify_ctx.status_text())
        connect_btn.setEnabled(not _thread_state["busy"])
        connect_btn.setText("Reconnect" if connected else "Connect Spotify")
        disconnect_btn.setEnabled(connected and not _thread_state["busy"])

    def _persist_tokens(tokens: dict, prompt_for_password: bool):
        """Only called right after an explicit user action (Connect
        succeeding) — NEVER from SpotifySession's background auto-refresh,
        since that can fire at unpredictable times mid-session and popping
        a master-password prompt out of nowhere would be a worse surprise
        than just not persisting that particular refresh. Matches VRChat
        Social Logger's own precedent: master-password mode only writes
        the blob at explicit login, not on every later token update."""
        mode = cfg.get("secure_storage_mode", "keyring")
        if mode == "keyring":
            try:
                spotify_ctx.secure_store.save_keyring(tokens)
            except RuntimeError as exc:
                status_lbl.setText(str(exc))
        elif mode == "master_password" and prompt_for_password:
            password = open_master_password_prompt(dlg, cfg, "create")
            if password:
                spotify_ctx.secure_store.save_master_password(tokens, password)
                password = ""  # drop our reference immediately after use
        # mode == "none", or a background refresh under master_password:
        # deliberately not persisted.

    def _on_connect_succeeded(tokens: dict):
        _stop_thread()
        mode = cfg.get("secure_storage_mode", "keyring")
        session = spotify_api.SpotifySession(
            client_id_edit.text().strip(), tokens,
            # Only keyring mode can safely auto-persist a background
            # refresh (no prompt needed) — see _persist_tokens' docstring.
            on_tokens_changed=(
                spotify_ctx.secure_store.save_keyring if mode == "keyring" else None
            ),
        )
        spotify_ctx.set_session(session)
        _persist_tokens(tokens, prompt_for_password=True)
        status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
        _thread_state["busy"] = False
        _refresh_buttons()

    def _on_connect_failed(msg: str):
        _stop_thread()
        status_lbl.setText(msg)
        status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        _thread_state["busy"] = False
        _refresh_buttons()

    def _stop_thread():
        thread = _thread_state["thread"]
        if thread is not None:
            thread.quit()
            thread.wait()
        _thread_state["thread"] = None
        _thread_state["worker"] = None

    def _try_unlock_existing() -> bool:
        """If there's already a saved login (either mode), use it
        instead of making the person go through Spotify's browser flow
        again. Returns True if a session was restored."""
        mode = cfg.get("secure_storage_mode", "keyring")
        tokens = None

        if mode == "keyring":
            tokens = spotify_ctx.secure_store.load_keyring()
        elif mode == "master_password" and spotify_ctx.secure_store.has_master_password_blob():
            password = open_master_password_prompt(dlg, cfg, "unlock")
            if password:
                try:
                    tokens = spotify_ctx.secure_store.load_master_password(password)
                except (WrongPassword, CorruptBlob) as exc:
                    status_lbl.setText(str(exc))
                    status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
                password = ""

        if not tokens:
            return False

        client_id = client_id_edit.text().strip()
        session = spotify_api.SpotifySession(client_id, tokens, on_tokens_changed=_on_tokens_changed)
        spotify_ctx.set_session(session)
        return True

    def _do_connect():
        client_id = client_id_edit.text().strip()
        if not client_id:
            status_lbl.setText("Enter your Spotify client ID first.")
            status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
            return
        cfg["spotify_client_id"] = client_id
        save_cb()

        if spotify_ctx.get_session() is None and _try_unlock_existing():
            status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
            _refresh_buttons()
            return

        _thread_state["busy"] = True
        status_lbl.setText("Opening your browser to authorize with Spotify...")
        status_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
        _refresh_buttons()

        thread = QThread(dlg)
        relay = _ConnectRelay(dlg)  # main-thread QObject — see module docstring
        worker = _ConnectWorker(client_id)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        worker.succeeded.connect(relay.succeeded)
        worker.failed.connect(relay.failed)
        relay.succeeded.connect(_on_connect_succeeded)
        relay.failed.connect(_on_connect_failed)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        _thread_state["thread"] = thread
        _thread_state["worker"] = worker
        _thread_state["relay"] = relay
        thread.start()

    def _do_disconnect():
        spotify_ctx.set_session(None)
        spotify_ctx.secure_store.clear_keyring()
        spotify_ctx.secure_store.clear_master_password()
        status_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
        _refresh_buttons()

    connect_btn.clicked.connect(_do_connect)
    disconnect_btn.clicked.connect(_do_disconnect)
    _refresh_buttons()
