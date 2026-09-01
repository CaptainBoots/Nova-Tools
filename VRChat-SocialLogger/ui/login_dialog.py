"""
ui/login_dialog.py
────────────────────
Modal login for the VRChat account this tool acts as. Two-step: normal
username/password, then (if the account has it enabled) a one-time 2FA
code, using core.vrchat_api's login()/verify_two_factor().

Network calls run on a short-lived background thread so a slow/stalled
request never freezes the window; results come back to the main thread
through a small Signal bridge (§6.16 — this file is the one place in
the tool allowed to know both Qt and vrchat_api exist).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QFrame,
)

from core.vrchat_api import VRChatAPI, VRChatAPIError, TwoFactorRequired
from ui import theme


class _LoginWorker(QObject):
    succeeded = Signal(dict)
    needs_two_factor = Signal(str)
    failed = Signal(str)

    def __init__(self, api: VRChatAPI, username: str, password: str):
        super().__init__()
        self._api = api
        self._username = username
        self._password = password

    def run(self):
        try:
            user = self._api.login(self._username, self._password)
            self.succeeded.emit(user)
        except TwoFactorRequired as exc:
            self.needs_two_factor.emit(exc.method)
        except VRChatAPIError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # network errors, etc.
            self.failed.emit(f"Could not reach VRChat: {exc}")


class _TwoFactorWorker(QObject):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, api: VRChatAPI, code: str, method: str):
        super().__init__()
        self._api = api
        self._code = code
        self._method = method

    def run(self):
        try:
            user = self._api.verify_two_factor(self._code, self._method)
            self.succeeded.emit(user)
        except VRChatAPIError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Could not reach VRChat: {exc}")


class _ResultRelay(QObject):
    """A real QObject, constructed on the main thread (wherever
    open_login() is called from), used purely to hop a worker-thread
    signal safely onto the main thread.

    This matters because of a genuine PySide6 gotcha: connecting a
    signal straight to a plain Python closure (not a bound method of a
    QObject) does NOT reliably queue across threads — Qt's
    AutoConnection (and even an explicit Qt.QueuedConnection) can only
    determine "queue this call" by inspecting the *receiver's*
    .thread(), and a bare closure has no such thing. In testing, that
    silently let worker-thread code call dlg.accept() and touch widgets
    directly from a background thread, which is undefined in Qt and
    was reproducibly aborting the whole process (not just this dialog)
    if the window was closed while a request was in flight.

    Connecting worker.succeeded -> relay.succeeded (signal-to-signal)
    is safe and correctly queues, because the receiving signal belongs
    to `relay`, a genuine QObject Qt can inspect. relay.succeeded is
    then connected to the real closure with an ordinary connection —
    by the time THAT fires, we're already on the main thread, so a
    closure receiver is fine."""
    succeeded = Signal(dict)
    needs_two_factor = Signal(str)
    failed = Signal(str)


def open_login(parent, api: VRChatAPI, saved_username: str = "") -> dict | None:
    """Blocking modal (per Qt's exec()) — returns the current-user dict
    on success, or None if the person cancelled."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"{theme.TITLE_PREFIX} Log in to VRChat")
    dlg.setMinimumWidth(360)
    dlg.setModal(True)

    result = {"user": None}
    state = {"thread": None, "worker": None, "busy": False}

    def _closeEvent(event):
        # Refuse to close (native X button, Alt+F4, etc.) while a
        # request is actually in flight — destroying the dialog here
        # would destroy its child QThread mid-run, which Qt treats as
        # a fatal error (aborts the whole process, not just this
        # window). The Cancel button already disables itself during a
        # request for the same reason; this covers every other way to
        # close the window too.
        if state["busy"]:
            event.ignore()
            return
        event.accept()

    dlg.closeEvent = _closeEvent
    state["method"] = "totp"

    root = QVBoxLayout(dlg)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(8)

    title = QLabel("Log in to VRChat")
    title.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    title.setFont(theme.qt_font(12, bold=True))
    root.addWidget(title)

    note = QLabel(
        "This signs in as your own VRChat account, the same way the "
        "official app does, so the tool can read your friends list and "
        "your own current-instance info."
    )
    note.setWordWrap(True)
    note.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    note.setFont(theme.qt_font(8))
    root.addWidget(note)

    # ── Step 1: username/password ────────────────────────────────────
    step1 = QWidget()
    step1_layout = QVBoxLayout(step1)
    step1_layout.setContentsMargins(0, 8, 0, 0)
    step1_layout.setSpacing(6)

    user_edit = QLineEdit(saved_username)
    user_edit.setPlaceholderText("Username or email")
    user_edit.setStyleSheet(theme.line_edit_qss())
    step1_layout.addWidget(user_edit)

    pass_edit = QLineEdit()
    pass_edit.setPlaceholderText("Password")
    pass_edit.setEchoMode(QLineEdit.Password)
    pass_edit.setStyleSheet(theme.line_edit_qss())
    step1_layout.addWidget(pass_edit)

    root.addWidget(step1)

    # ── Step 2: 2FA code (hidden until needed) ───────────────────────
    step2 = QWidget()
    step2_layout = QVBoxLayout(step2)
    step2_layout.setContentsMargins(0, 8, 0, 0)
    step2_layout.setSpacing(6)

    tfa_label = QLabel("Enter the 6-digit code from your authenticator/email")
    tfa_label.setWordWrap(True)
    tfa_label.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
    tfa_label.setFont(theme.qt_font(9))
    step2_layout.addWidget(tfa_label)

    tfa_edit = QLineEdit()
    tfa_edit.setPlaceholderText("123456")
    tfa_edit.setStyleSheet(theme.line_edit_qss())
    step2_layout.addWidget(tfa_edit)

    root.addWidget(step2)
    step2.hide()

    status_lbl = QLabel("")
    status_lbl.setWordWrap(True)
    status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
    status_lbl.setFont(theme.qt_font(8))
    root.addWidget(status_lbl)

    btn_row = QHBoxLayout()
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setStyleSheet(theme.subtle_button_qss())
    btn_row.addWidget(cancel_btn)
    btn_row.addStretch(1)
    submit_btn = QPushButton("Log In")
    submit_btn.setStyleSheet(theme.accent_button_qss())
    submit_btn.setFont(theme.qt_font(9, bold=True))
    btn_row.addWidget(submit_btn)
    root.addLayout(btn_row)

    def _set_busy(busy: bool):
        state["busy"] = busy
        submit_btn.setEnabled(not busy)
        cancel_btn.setEnabled(not busy)
        submit_btn.setText("Working..." if busy else ("Log In" if step2.isHidden() else "Verify"))

    def _run_worker(worker, on_succeeded=None, on_needs_2fa=None, on_failed=None):
        thread = QThread(dlg)
        relay = _ResultRelay(dlg)  # constructed here, on the main thread — see class docstring
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        # Worker (background thread) -> relay: signal-to-signal, safe.
        worker.succeeded.connect(relay.succeeded)
        if hasattr(worker, "needs_two_factor"):
            worker.needs_two_factor.connect(relay.needs_two_factor)
        worker.failed.connect(relay.failed)

        # Relay (now on main thread) -> our real closures: safe, same-thread by this point.
        if on_succeeded is not None:
            relay.succeeded.connect(on_succeeded)
        if on_needs_2fa is not None:
            relay.needs_two_factor.connect(on_needs_2fa)
        if on_failed is not None:
            relay.failed.connect(on_failed)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        state["thread"] = thread
        state["worker"] = worker
        state["relay"] = relay  # keep a reference alive for the dialog's lifetime
        thread.start()

    def _stop_thread():
        thread = state["thread"]
        if thread is not None:
            thread.quit()
            thread.wait()  # run() already returned by the time any signal fires, so this is near-instant
        state["thread"] = None
        state["worker"] = None

    def _on_login_success(user: dict):
        _stop_thread()
        _set_busy(False)
        result["user"] = user
        dlg.accept()

    def _on_needs_2fa(method: str):
        _stop_thread()
        state["method"] = method
        status_lbl.setText("")
        step1.setEnabled(False)
        step2.show()
        _set_busy(False)
        tfa_edit.setFocus()

    def _on_login_failed(msg: str):
        _stop_thread()
        status_lbl.setText(msg)
        _set_busy(False)

    def _on_2fa_success(user: dict):
        _stop_thread()
        _set_busy(False)
        result["user"] = user
        dlg.accept()

    def _on_2fa_failed(msg: str):
        _stop_thread()
        status_lbl.setText(msg)
        _set_busy(False)

    def _submit():
        status_lbl.setText("")
        if step2.isVisible():
            code = tfa_edit.text().strip()
            if not code:
                status_lbl.setText("Enter your 2FA code.")
                return
            _set_busy(True)
            worker = _TwoFactorWorker(api, code, state["method"])
            _run_worker(worker, on_succeeded=_on_2fa_success, on_failed=_on_2fa_failed)
            return

        username = user_edit.text().strip()
        password = pass_edit.text()
        if not username or not password:
            status_lbl.setText("Enter your username/email and password.")
            return
        _set_busy(True)
        worker = _LoginWorker(api, username, password)
        _run_worker(worker, on_succeeded=_on_login_success, on_needs_2fa=_on_needs_2fa, on_failed=_on_login_failed)

    submit_btn.clicked.connect(_submit)
    cancel_btn.clicked.connect(dlg.reject)
    pass_edit.returnPressed.connect(_submit)
    tfa_edit.returnPressed.connect(_submit)

    dlg.exec()
    return result["user"]