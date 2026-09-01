"""
core/keybind.py
────────────────
Cross-platform (Windows/Linux) key-press simulation, built on pynput.
No Qt here — this is pure backend logic, safe to call from any thread.

Usage:
    press_keys(["ctrl", "alt", "u"])          # quick tap
    press_keys(["ctrl", "alt", "u"], hold_ms=500)  # hold for 500ms then release
"""

from __future__ import annotations

import time

try:
    from pynput.keyboard import Controller, Key, KeyCode
    _controller = Controller()
    _AVAILABLE = True
except Exception:  # pragma: no cover - headless/CI environments without a display
    _controller = None
    _AVAILABLE = False
    Key = None
    KeyCode = None

# Friendly name -> pynput Key. Anything not in here is treated as a
# single printable character via KeyCode.from_char.
_NAMED_KEYS = {
    "ctrl": "ctrl_l", "control": "ctrl_l", "lctrl": "ctrl_l", "rctrl": "ctrl_r",
    "alt": "alt_l", "lalt": "alt_l", "ralt": "alt_r",
    "shift": "shift_l", "lshift": "shift_l", "rshift": "shift_r",
    "win": "cmd", "windows": "cmd", "super": "cmd", "cmd": "cmd", "meta": "cmd",
    "enter": "enter", "return": "enter",
    "esc": "esc", "escape": "esc",
    "tab": "tab",
    "space": "space", "spacebar": "space",
    "backspace": "backspace",
    "delete": "delete", "del": "delete",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "home": "home", "end": "end",
    "pageup": "page_up", "pagedown": "page_down",
    "capslock": "caps_lock",
    "insert": "insert",
}
for _n in range(1, 25):
    _NAMED_KEYS[f"f{_n}"] = f"f{_n}"


class KeybindError(Exception):
    pass


def is_available() -> bool:
    """False on a headless box with no input backend — callers should
    surface this rather than silently doing nothing."""
    return _AVAILABLE


def _resolve(key_name: str):
    name = (key_name or "").strip().lower()
    if not name:
        raise KeybindError("Empty key name")
    if name in _NAMED_KEYS:
        attr = _NAMED_KEYS[name]
        return getattr(Key, attr)
    if len(name) == 1:
        return KeyCode.from_char(name)
    # Fall back to treating an unrecognised multi-char name as a Key
    # attribute if pynput happens to have one (e.g. "menu", "print_screen").
    if hasattr(Key, name):
        return getattr(Key, name)
    raise KeybindError(f"Unknown key: {key_name!r}")


def press_keys(keys: list, hold_ms: int = 0):
    """Press `keys` together (modifiers first, in the order given), hold
    for `hold_ms` (0 = a short ~40ms tap), then release in reverse order.
    Safe to call from a background thread."""
    if not keys:
        return
    if not _AVAILABLE:
        raise KeybindError(
            "No input backend available (pynput could not initialise — "
            "likely no display/X server in this environment)."
        )

    resolved = [_resolve(k) for k in keys]

    pressed = []
    try:
        for k in resolved:
            _controller.press(k)
            pressed.append(k)
        time.sleep(max(hold_ms, 40) / 1000.0)
    finally:
        for k in reversed(pressed):
            try:
                _controller.release(k)
            except Exception:
                pass
