"""
core/osc_bridge.py
───────────────────
OSC client/parsing helpers plus a threaded UDP listener, extracted from
the original single-file app so the UI layer stays toolkit-agnostic.
"""

import socket
import struct
import threading
import time

try:
    from pythonosc import udp_client
    PYTHON_OSC = True
except ImportError:
    PYTHON_OSC = False


def make_client(ip: str, port: int):
    if not PYTHON_OSC:
        return None
    try:
        return udp_client.SimpleUDPClient(ip, port)
    except Exception:
        return None


def send_osc(client, addr: str, val) -> bool:
    if client is None:
        return False
    try:
        client.send_message(addr, val)
        return True
    except Exception:
        return False


def parse_osc(data: bytes):
    """Parse a single raw OSC packet. Returns (address, type_name, value)
    or None if it couldn't be parsed."""
    try:
        end = data.index(b'\x00')
        addr = data[:end].decode("utf-8", "replace")
        ap = (end + 4) & ~3
        rest = data[ap:]
        if not rest or rest[0:1] != b',':
            return None
        te = rest.index(b'\x00', 1)
        tags = rest[1:te].decode("ascii", "replace")
        tp = (te + 4) & ~3
        rest = rest[tp:]
        tag = tags[0] if tags else "?"
        if tag == 'f':
            val = round(struct.unpack_from(">f", rest)[0], 5)
        elif tag == 'i':
            val = struct.unpack_from(">i", rest)[0]
        elif tag == 'T':
            val = True
        elif tag == 'F':
            val = False
        elif tag == 's':
            se = rest.index(b'\x00')
            val = rest[:se].decode("utf-8", "replace")
        else:
            val = None
        type_name = {"f": "float", "i": "int", "T": "bool", "F": "bool", "s": "string"}.get(tag, "?")
        return addr, type_name, val
    except Exception:
        return None


class ParamListener:
    """Threaded UDP listener. Calls on_param(addr, val, typ, timestamp) for
    every successfully parsed packet, and on_error(message) if the socket
    fails to bind. Both callbacks may be called from the listener thread —
    callers are responsible for marshalling back to the UI thread."""

    def __init__(self, port: int, on_param, on_error):
        self.port = port
        self.running = False
        self._on_param = on_param
        self._on_error = on_error
        self._thread: threading.Thread | None = None

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)
        try:
            sock.bind(("0.0.0.0", self.port))
        except Exception as e:
            self._on_error(f"Bind failed: {e}")
            self.running = False
            return

        while self.running:
            try:
                data, _ = sock.recvfrom(4096)
                res = parse_osc(data)
                if res:
                    addr, typ, val = res
                    self._on_param(addr, val, typ, time.strftime("%H:%M:%S"))
            except socket.timeout:
                continue
            except Exception:
                break
        sock.close()
