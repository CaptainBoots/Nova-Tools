"""
ui/worker_utils.py
────────────────────
Shared helper implementing the QObject-relay pattern established while
debugging VRChat-Social-Logger's login dialog: connecting a background
QThread's signal straight to a plain Python closure does NOT reliably
queue the call onto the main thread in PySide6 — only a genuine bound
QObject method does, since AutoConnection (and even an explicit
Qt.QueuedConnection) can only detect "queue this" by inspecting the
*receiver's* .thread(), and a bare closure has none. That silently let
worker-thread code touch widgets directly from a background thread,
which reproducibly aborted the whole process. Full writeup lives in
that project's ui/login_dialog.py, in the _ResultRelay class docstring.

run_worker() does the thread + relay wiring once, correctly, so every
dialog here just gets a plain function to call, a success closure, and
a failure closure — no thread lifecycle code to get wrong per-dialog.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, QThread


class _Relay(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _CallableWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            result = self._fn()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)


def run_worker(parent_qobject, fn, on_succeeded, on_failed, state: dict):
    """parent_qobject: a real QObject (typically the dialog) to parent
    the thread/relay to.
    fn: a zero-argument callable doing the blocking work (a network
    call, etc) — call it via a lambda/partial if it needs arguments.
    on_succeeded(result) / on_failed(message): ordinary closures — safe
    to touch widgets in these, since by the time they fire we're back
    on the main thread via the relay hop.
    state: a dict the CALLER owns and reuses across calls, to track the
    current thread/worker/relay for lifetime and for stop_worker()."""
    thread = QThread(parent_qobject)
    relay = _Relay(parent_qobject)
    worker = _CallableWorker(fn)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    worker.succeeded.connect(relay.succeeded)   # worker thread -> relay: signal-to-signal, safe
    worker.failed.connect(relay.failed)
    relay.succeeded.connect(on_succeeded)        # relay (main thread) -> real closure: safe
    relay.failed.connect(on_failed)

    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    state["thread"] = thread
    state["worker"] = worker
    state["relay"] = relay
    thread.start()


def stop_worker(state: dict):
    """Call from a success/failure handler (or before closing a dialog
    that isn't busy) to cleanly join the background thread. Safe to
    call when nothing is running."""
    thread = state.get("thread")
    if thread is not None:
        thread.quit()
        thread.wait()  # run() already returned by the time any signal fires, so this is near-instant
    state["thread"] = None
    state["worker"] = None


def install_busy_close_guard(dlg, state: dict):
    """Refuse to close `dlg` (native X button, Alt+F4, etc.) while
    state["busy"] is True — destroying a dialog while its child QThread
    is still running is a fatal error in Qt (aborts the whole process,
    not just the dialog). Callers should set state["busy"] themselves
    around each run_worker() call."""
    def _closeEvent(event):
        if state.get("busy"):
            event.ignore()
            return
        event.accept()
    dlg.closeEvent = _closeEvent
