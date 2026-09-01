"""
config.py
─────────
Gamepad config I/O and defaults.
"""

import json
import os

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR  = os.path.dirname(SCRIPT_DIR)
CONFIG_DIR  = os.path.join(PARENT_DIR, "configs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "gamepad_config.json")


def get_defaults() -> dict:
    return {"pads": [], "theme_mode": "new"}


def load_config() -> dict:
    defaults = get_defaults()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        if isinstance(loaded, dict):
            return {**defaults, **loaded}

        return defaults
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return defaults


def save_config(pads_data: list[dict], theme_mode: str = "new"):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"pads": pads_data, "theme_mode": theme_mode}, f, indent=2)
    print(f"[Config] Saved ({len(pads_data)} pads)")