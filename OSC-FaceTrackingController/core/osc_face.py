"""
core/osc_face.py
──────────────────
OSC client + send logic extracted from the original monolithic
OscFaceController class. Handles VRCFT v1/v2 prefix compatibility and
per-parameter aliasing (e.g. JawForward also sends JawZ).
"""

import threading

from pythonosc import udp_client

DEFAULT_OSC_IP     = "127.0.0.1"
DEFAULT_OSC_PORT   = "9000"
DEFAULT_OSC_PREFIX = "/avatar/parameters/v2/"

PREFIX_PRESETS = {
    "VRCFT v2 (default)": "/avatar/parameters/v2/",
    "Direct / v1":        "/avatar/parameters/",
}


def normalize_prefix(prefix: str) -> str:
    prefix = (prefix or "").strip() or DEFAULT_OSC_PREFIX
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    if not prefix.endswith("/"):
        prefix += "/"
    return prefix


def prefix_variants(normalized_prefix: str) -> list[str]:
    """Also send to the v1/v2 counterpart prefix, so it works regardless
    of which VRCFT version the target app is expecting."""
    variants = [normalized_prefix]
    marker = "/avatar/parameters/"
    marker_pos = normalized_prefix.find(marker)
    if marker_pos == -1:
        return variants

    prefix_head = normalized_prefix[: marker_pos + len(marker)]
    prefix_tail = normalized_prefix[marker_pos + len(marker):]

    if prefix_tail.startswith("v2/"):
        alt = prefix_head + prefix_tail[len("v2/"):]
    else:
        alt = prefix_head + prefix_tail + "v2/"

    if alt not in variants:
        variants.append(alt)
    return variants


def param_payloads(param: str, value: float) -> list[tuple[str, float]]:
    """Some parameters have alternate/legacy names that also need the
    same value sent, for compatibility with different avatar setups."""
    payloads = [(param, value)]

    if param == "JawForward":
        payloads.append(("JawZ", value))
    elif param == "TongueBendDown":
        payloads.append(("TongueArchY", value))
    elif param == "TongueCurlUp":
        payloads.append(("TongueArchY", -value))
    elif param == "TongueSquish":
        payloads.append(("TongueShape", value))
    elif param == "TongueFlat":
        payloads.append(("TongueShape", -value))

    return payloads


class OscFaceClient:
    """Thin wrapper owning the UDP client + a lock, so sends from the UI
    thread are safe even if this ever gets called from more than one
    place at once."""

    def __init__(self):
        self._client: udp_client.SimpleUDPClient | None = None
        self._lock = threading.Lock()
        self.connected = False

    def connect(self, ip: str, port: int):
        with self._lock:
            self._client = udp_client.SimpleUDPClient(ip, port)
            self.connected = True

    def disconnect(self):
        with self._lock:
            self._client = None
            self.connected = False

    def send(self, prefix: str, param: str, value: float) -> bool:
        if not self.connected or self._client is None:
            return False
        prefixes = prefix_variants(normalize_prefix(prefix))
        payloads = param_payloads(param, value)
        sent_addresses: set[str] = set()
        try:
            with self._lock:
                for p in prefixes:
                    for param_name, param_value in payloads:
                        address = p + param_name
                        if address in sent_addresses:
                            continue
                        self._client.send_message(address, param_value)
                        sent_addresses.add(address)
            return True
        except (OSError, RuntimeError, ValueError):
            return False
