"""
core/Actions/keybind_action.py
─────────────────────────────────
Action module: simulates a key press (single key or combo, quick tap
or held for a duration).
"""

from core import keybind

ID = "keybind"
LABEL = "Press Keybind"
CATEGORY = "Input"
DESCRIPTION = "Presses a key or key combo (e.g. ctrl+alt+u), tap or held."


def run(action, ctx):
    keybind.press_keys(action.keys, action.hold_ms)