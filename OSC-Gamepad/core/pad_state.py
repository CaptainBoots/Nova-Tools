"""
core/pad_state.py
─────────────────
PadState: per-pad OSC connection and input loop.

Sends VRChat /input/* messages at 20Hz while held, and toggles
/avatar/parameters/* booleans on click.
"""

import threading
import time

from pythonosc import udp_client


class PadState:
    LOOP_INTERVAL = 0.05  # 20 Hz

    def __init__(self, host: str, port: int):
        self.host    = host
        self.port    = port
        self.client  = udp_client.SimpleUDPClient(host, port)

        self.axes_held: set[str] = set()
        self.btn_held:  set[str] = set()
        self.btn_sent1: set[str] = set()

        self.seated   = False
        self.crouched = False
        self.running  = True

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ── Input state ───────────────────────────────────────────────────────────

    def press_axis(self, action: str):
        self.axes_held.add(action)

    def release_axis(self, action: str):
        self.axes_held.discard(action)

    def press_btn(self, action: str):
        self.btn_held.add(action)

    def release_btn(self, action: str):
        self.btn_held.discard(action)
        self.btn_sent1.discard(action)

    def toggle_avatar_param(self, param: str) -> bool:
        if param == "seated":
            self.seated = not self.seated
            self._safe_send("/avatar/parameters/Seated", self.seated)
            return self.seated
        if param == "crouched":
            self.crouched = not self.crouched
            self._safe_send("/avatar/parameters/Crouching", self.crouched)
            return self.crouched
        return False

    # ── OSC send loop ─────────────────────────────────────────────────────────

    def _loop(self):
        while self.running:
            v = h = lh = lv = 0.0
            jump = grab = use = menu = voice = 0

            for axis in list(self.axes_held):
                if axis == "up":     v  =  1.0
                if axis == "down":   v  = -1.0
                if axis == "left":   h  = -1.0
                if axis == "right":  h  =  1.0
                if axis == "look_l": lh = -1.0
                if axis == "look_r": lh =  1.0
                if axis == "look_u": lv =  1.0
                if axis == "look_d": lv = -1.0

            for btn in ("jump", "grab", "use", "menu", "voice"):
                if btn not in self.btn_held:
                    continue
                if btn not in self.btn_sent1:
                    self.btn_sent1.add(btn)
                    if btn == "jump":  jump  = 1
                    if btn == "grab":  grab  = 1
                    if btn == "use":   use   = 1
                    if btn == "menu":  menu  = 1
                    if btn == "voice": voice = 1
                else:
                    if btn == "grab": grab = 1
                    if btn == "use":  use  = 1
                    if btn == "menu": menu = 1

            self._safe_send("/input/Vertical",              v)
            self._safe_send("/input/Horizontal",            h)
            self._safe_send("/input/LookHorizontal",        lh)
            self._safe_send("/input/LookVertical",          lv)
            self._safe_send("/input/Jump",                  jump)
            self._safe_send("/input/Grab",                  grab)
            self._safe_send("/input/Use",                   use)
            self._safe_send("/input/QuickMenuToggleLeft",   menu)
            self._safe_send("/input/Voice",                 voice)

            time.sleep(self.LOOP_INTERVAL)

    def _safe_send(self, address: str, value):
        try:
            self.client.send_message(address, value)
        except Exception:
            pass

    def stop(self):
        """Stops the OSC loop thread cleanly."""
        self.running = False
        self.btn_held.clear()
        self.axes_held.clear()
        # Allows thread execution loop to finish naturally