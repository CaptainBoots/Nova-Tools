"""
core/source.py
──────────────
OscSource: listens on a UDP port, caches latest value per OSC address.
"""

import threading

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer


class OscSource:
    """
    Listens on a UDP port and caches the latest value for every OSC address received.
    Thread-safe. snapshot() returns a point-in-time copy of the cache.
    """

    def __init__(self, name: str, port: int) -> None:
        self.name     = name
        self.port     = port
        self.running  = False
        self.rx_count = 0
        self._lock    = threading.Lock()
        self._values: dict[str, tuple] = {}
        self._server: ThreadingOSCUDPServer | None = None
        self._thread: threading.Thread | None = None

    def _handle(self, address: str, *args) -> None:
        with self._lock:
            self._values[address] = args
            self.rx_count += 1

    def snapshot(self) -> dict[str, tuple]:
        with self._lock:
            return dict(self._values)

    def start(self) -> bool:
        if self.running:
            return True
        try:
            d = Dispatcher()
            d.set_default_handler(self._handle)
            self._server = ThreadingOSCUDPServer(("127.0.0.1", self.port), d)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            self.running = True
            print(f"[Router] '{self.name}' listening on :{self.port}")
            return True
        except OSError as e:
            print(f"[Router] Cannot bind '{self.name}' on :{self.port} — {e}")
            return False

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
            except (OSError, RuntimeError):
                pass
        self._server = None
        self._thread = None
        self.running  = False
        with self._lock:
            self._values.clear()
        self.rx_count = 0