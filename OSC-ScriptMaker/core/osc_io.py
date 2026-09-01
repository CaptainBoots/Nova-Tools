"""
core/osc_io.py
────────────────
Thin OSC input/output layer built on python-osc. No Qt — a listener is
just a background thread calling a plain callback; senders are cached
UDP clients keyed by (host, port).
"""

from __future__ import annotations

import threading

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient


class OSCListener:
    """Wraps a ThreadingOSCUDPServer on its own daemon thread. `on_message`
    is called as on_message(address: str, value) for every incoming OSC
    message (only the first argument is forwarded — that covers every
    VRChat OSC use case this tool targets)."""

    def __init__(self, host: str, port: int, on_message):
        self._on_message = on_message
        self._dispatcher = Dispatcher()
        self._dispatcher.set_default_handler(self._handle)
        self._server = ThreadingOSCUDPServer((host, port), self._dispatcher)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._running = False

    def _handle(self, address, *args):
        value = args[0] if args else None
        try:
            self._on_message(address, value)
        except Exception:
            # A single misbehaving script must never take down the listener.
            pass

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        if not self._running:
            return
        self._running = False
        try:
            self._server.shutdown()
            self._server.server_close()
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def host(self) -> str:
        return self._server.server_address[0]

    @property
    def port(self) -> int:
        return self._server.server_address[1]


class OSCSenderPool:
    """Caches SimpleUDPClient instances per (host, port) so repeated sends
    don't reopen a socket every time."""

    def __init__(self):
        self._clients: dict[tuple[str, int], SimpleUDPClient] = {}
        self._lock = threading.Lock()

    def get(self, host: str, port: int) -> SimpleUDPClient:
        key = (host, port)
        with self._lock:
            client = self._clients.get(key)
            if client is None:
                client = SimpleUDPClient(host, port)
                self._clients[key] = client
            return client

    def send(self, host: str, port: int, address: str, value):
        client = self.get(host, port)
        client.send_message(address, value)

    def close_all(self):
        with self._lock:
            self._clients.clear()