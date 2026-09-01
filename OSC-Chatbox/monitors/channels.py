"""monitors/channels.py — listens on 10 fixed OSC ports for /chatbox/input
messages coming from other tools (e.g. OSC-ScriptMaker's Chatbox Message
action in "Send to Chatbox (channel)" mode), completely independent of
VRChat's own OSC traffic. Same port contract as OSC-ScriptMaker's
CHATBOX_CHANNELS: channel 1 = 9600, channel 2 = 9601, ... channel 10 = 9609.
"""
import threading

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

BASE_PORT    = 9600
NUM_CHANNELS = 10

_data = {f"channel_{n}_text": "" for n in range(1, NUM_CHANNELS + 1)}
_lock = threading.Lock()


def _make_handler(n: int):
    def _on_message(address, *args):
        if args:
            with _lock:
                _data[f"channel_{n}_text"] = str(args[0])
    return _on_message


def _start_one(n: int, port: int):
    dispatcher = Dispatcher()
    dispatcher.map("/chatbox/input", _make_handler(n))
    dispatcher.set_default_handler(lambda *a: None)
    try:
        server = BlockingOSCUDPServer(("127.0.0.1", port), dispatcher)
        server.serve_forever()
    except Exception as e:
        print(f"[channels monitor] channel {n} (port {port}) error: {e}")


_started = False


def start():
    global _started
    if _started:
        return
    _started = True
    for n in range(1, NUM_CHANNELS + 1):
        port = BASE_PORT + (n - 1)
        threading.Thread(target=_start_one, args=(n, port), daemon=True).start()


def snapshot() -> dict:
    with _lock:
        return dict(_data)
