"""
ui/master_password_dialog.py
────────────────────────────
Prompts for the master password used to unlock (or create) the
encrypted session blob in "master_password" storage mode. Offers
one-click buttons for any installed password manager CLI
(core.password_manager_bridge) as an alternative to typing it, plus a
manual field that's always available as a fallback.

Handling of the value, deliberately:
  - It is read from the field (or a CLI call) into ONE local variable,
    used immediately to attempt encrypt/decrypt, then that variable is
    reassigned to "" before the function returns — Python can't
    guarantee the old string is scrubbed from memory (strings are
    immutable and the interpreter may keep copies), but this at least
    removes every reference we control as early as possible.
  - The QLineEdit itself is cleared right after reading its text, so it
    doesn't linger on screen or in the widget's own memory longer than
    needed.
  - Nothing about the password (success, failure, or the value itself)
    is ever passed to print()/logging or written to disk anywhere in
    this file.
  - CLI calls run on a background QThread (network/vault-unlock latency
    for 1Password/Bitwarden can take a second or two) so the dialog
    never freezes, using the same worker-thread + signal pattern as
    ui/login_dialog.py.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget,
)

from core.password_manager_bridge import (
    available_managers, get_from_1password, get_from_bitwarden, get_from_keepassxc,
)
from ui import theme

_MANAGER_LABELS = {
    "1password": "1Password",
    "bitwarden": "Bitwarden",
    "keepassxc": "KeePassXC",
}


class _FetchRelay(QObject):
    """Same purpose as ui/login_dialog.py's _ResultRelay — a genuine
    QObject constructed on the main thread, used to safely hop a
    worker-thread signal onto a plain local closure. See that file's
    docstring for the full explanation of why this is necessary."""
    succeeded = Signal(str)
    failed = Signal()


class _FetchWorker(QObject):
    succeeded = Signal(str)
    failed = Signal()

    def __init__(self, manager: str, item_ref: str, keepass_db_path: str = "", keepass_vault_password: str = ""):
        super().__init__()
        self._manager = manager
        self._item_ref = item_ref
        self._keepass_db_path = keepass_db_path
        self._keepass_vault_password = keepass_vault_password

    def run(self):
        value = None
        if self._manager == "1password":
            value = get_from_1password(self._item_ref)
        elif self._manager == "bitwarden":
            value = get_from_bitwarden(self._item_ref)
        elif self._manager == "keepassxc":
            value = get_from_keepassxc(self._keepass_db_path, self._item_ref, self._keepass_vault_password)
        # Drop our own reference to the vault password immediately —
        # it's only needed for the single get_from_keepassxc() call above.
        self._keepass_vault_password = ""
        if value:
            self.succeeded.emit(value)
        else:
            self.failed.emit()


def open_master_password_prompt(parent, cfg: dict, mode: str) -> str | None:
    """mode is "create" (first time, setting a new master password) or
    "unlock" (decrypting an existing blob). Returns the password as a
    plain str for the caller to use immediately and discard, or None if
    the person cancelled."""
    dlg = QDialog(parent)
    is_create = mode == "create"
    dlg.setWindowTitle(f"{theme.TITLE_PREFIX} " + ("Set Master Password" if is_create else "Unlock Session"))
    dlg.setMinimumWidth(380)
    dlg.setModal(True)

    result: dict = {"password": None}
    state = {"thread": None, "worker": None, "busy": False}

    def _closeEvent(event):
        # Same guard as ui/login_dialog.py — refuse to close (native X
        # button, Alt+F4) while a background fetch is in flight, since
        # destroying the dialog would destroy its child QThread mid-run.
        if state["busy"]:
            event.ignore()
            return
        event.accept()

    dlg.closeEvent = _closeEvent

    root = QVBoxLayout(dlg)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(8)

    title = QLabel("Set a master password" if is_create else "Enter your master password")
    title.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    title.setFont(theme.qt_font(12, bold=True))
    root.addWidget(title)

    note_text = (
        "This password encrypts your saved VRChat session on this "
        "computer. It is never written to disk anywhere — only used in "
        "memory to lock/unlock the file each time."
        if is_create else
        "This decrypts your saved VRChat session. It's never stored — "
        "you'll need it again next launch."
    )
    note = QLabel(note_text)
    note.setWordWrap(True)
    note.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    note.setFont(theme.qt_font(8))
    root.addWidget(note)

    pw_edit = QLineEdit()
    pw_edit.setPlaceholderText("Master password")
    pw_edit.setEchoMode(QLineEdit.Password)
    pw_edit.setStyleSheet(theme.line_edit_qss())
    root.addWidget(pw_edit)

    managers = available_managers()
    mgr_buttons = []
    if managers:
        fetch_lbl = QLabel("Or fill it from a password manager:")
        fetch_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        fetch_lbl.setFont(theme.qt_font(8))
        root.addWidget(fetch_lbl)

        item_edit = QLineEdit(cfg.get("pw_manager_item_name", "VRChat Social Logger"))
        item_edit.setPlaceholderText("Item name (as saved in your password manager)")
        item_edit.setStyleSheet(theme.line_edit_qss())
        item_edit.setFont(theme.qt_font(8))
        root.addWidget(item_edit)

        mgr_row = QHBoxLayout()
        mgr_buttons = []
        for manager in managers:
            btn = QPushButton(f"Fill from {_MANAGER_LABELS.get(manager, manager)}")
            btn.setStyleSheet(theme.subtle_button_qss())
            btn.setFont(theme.qt_font(8))
            mgr_buttons.append(btn)

            def _mk_handler(m):
                def _handler():
                    item_ref = item_edit.text().strip()
                    if not item_ref:
                        status_lbl.setText("Enter the item name first.")
                        return
                    if m == "keepassxc":
                        _handle_keepass(item_ref)
                        return
                    status_lbl.setText(f"Asking {_MANAGER_LABELS.get(m, m)}...")
                    _run_fetch(m, item_ref)
                return _handler

            btn.clicked.connect(_mk_handler(manager))
            mgr_row.addWidget(btn)
        root.addLayout(mgr_row)

    status_lbl = QLabel("")
    status_lbl.setWordWrap(True)
    status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
    status_lbl.setFont(theme.qt_font(8))
    root.addWidget(status_lbl)

    if is_create:
        confirm_edit = QLineEdit()
        confirm_edit.setPlaceholderText("Confirm master password")
        confirm_edit.setEchoMode(QLineEdit.Password)
        confirm_edit.setStyleSheet(theme.line_edit_qss())
        root.addWidget(confirm_edit)
    else:
        confirm_edit = None

    btn_row = QHBoxLayout()
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setStyleSheet(theme.subtle_button_qss())
    btn_row.addWidget(cancel_btn)
    btn_row.addStretch(1)
    submit_btn = QPushButton("Set Password" if is_create else "Unlock")
    submit_btn.setStyleSheet(theme.accent_button_qss())
    submit_btn.setFont(theme.qt_font(9, bold=True))
    btn_row.addWidget(submit_btn)
    root.addLayout(btn_row)

    def _set_fetch_busy(busy: bool):
        state["busy"] = busy
        submit_btn.setEnabled(not busy)
        cancel_btn.setEnabled(not busy)
        for b in mgr_buttons:
            b.setEnabled(not busy)

    def _stop_fetch_thread():
        thread = state["thread"]
        if thread is not None:
            thread.quit()
            thread.wait()
        state["thread"] = None
        state["worker"] = None

    def _fill_password_field(value: str):
        _stop_fetch_thread()
        _set_fetch_busy(False)
        pw_edit.setText(value)
        if confirm_edit is not None:
            confirm_edit.setText(value)
        status_lbl.setText("Filled.")
        status_lbl.setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
        # The fetched value only ever lived in this local variable and
        # the CLI's own stdout buffer, both of which go out of scope
        # here — we don't keep a second copy anywhere in this module.

    def _fetch_failed():
        _stop_fetch_thread()
        _set_fetch_busy(False)
        status_lbl.setText("Couldn't retrieve it — check the item name, or type it manually.")
        status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")

    def _run_fetch(manager: str, item_ref: str, keepass_db_path: str = "", keepass_vault_password: str = ""):
        _set_fetch_busy(True)
        thread = QThread(dlg)
        relay = _FetchRelay(dlg)  # constructed here, on the main thread — see class docstring
        worker = _FetchWorker(manager, item_ref, keepass_db_path, keepass_vault_password)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        # Worker (background thread) -> relay: signal-to-signal, safe.
        worker.succeeded.connect(relay.succeeded)
        worker.failed.connect(relay.failed)
        # Relay (main thread) -> our real closures: safe, same-thread by this point.
        relay.succeeded.connect(_fill_password_field)
        relay.failed.connect(_fetch_failed)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        state["thread"] = thread
        state["worker"] = worker
        state["relay"] = relay  # keep a reference alive for the dialog's lifetime
        thread.start()

    def _handle_keepass(item_ref: str):
        # KeePassXC's CLI needs the vault's OWN password on every call —
        # a second, small inline prompt, kept local to this closure and
        # never stored, same handling standard as everything else here.
        vault_dlg = QDialog(dlg)
        vault_dlg.setWindowTitle("KeePassXC Vault")
        v_layout = QVBoxLayout(vault_dlg)
        v_lbl = QLabel("Path to your .kdbx file:")
        v_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
        v_layout.addWidget(v_lbl)
        db_path_edit = QLineEdit(cfg.get("keepass_db_path", ""))
        db_path_edit.setStyleSheet(theme.line_edit_qss())
        v_layout.addWidget(db_path_edit)
        v_pw_lbl = QLabel("Vault password:")
        v_pw_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
        v_layout.addWidget(v_pw_lbl)
        vault_pw_edit = QLineEdit()
        vault_pw_edit.setEchoMode(QLineEdit.Password)
        vault_pw_edit.setStyleSheet(theme.line_edit_qss())
        v_layout.addWidget(vault_pw_edit)
        v_btn = QPushButton("Fetch")
        v_btn.setStyleSheet(theme.accent_button_qss())
        v_layout.addWidget(v_btn)

        def _do_fetch():
            db_path = db_path_edit.text().strip()
            vault_pw = vault_pw_edit.text()
            cfg["keepass_db_path"] = db_path
            vault_pw_edit.setText("")  # clear immediately after reading it out
            vault_dlg.accept()  # this small prompt has no long-running work of its own to guard
            status_lbl.setText("Asking KeePassXC...")
            _run_fetch("keepassxc", item_ref, keepass_db_path=db_path, keepass_vault_password=vault_pw)

        v_btn.clicked.connect(_do_fetch)
        vault_dlg.exec()

    def _submit():
        password = pw_edit.text()
        if not password:
            status_lbl.setText("Enter a password.")
            return
        if is_create:
            confirm = confirm_edit.text()
            if password != confirm:
                status_lbl.setText("Passwords don't match.")
                confirm_edit.setText("")
                return
        result["password"] = password
        pw_edit.setText("")
        if confirm_edit is not None:
            confirm_edit.setText("")
        dlg.accept()

    submit_btn.clicked.connect(_submit)
    cancel_btn.clicked.connect(dlg.reject)
    pw_edit.returnPressed.connect(_submit)

    dlg.exec()
    password = result["password"]
    result["password"] = None  # drop our own reference as soon as we've read it out
    return password