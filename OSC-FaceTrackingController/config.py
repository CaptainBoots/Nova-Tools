"""
config.py
─────────
OSC Face Tracking Controller config I/O and defaults.
"""

import json
import os

from core.osc_face import DEFAULT_OSC_IP, DEFAULT_OSC_PORT, DEFAULT_OSC_PREFIX

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR  = os.path.dirname(SCRIPT_DIR)
CONFIG_DIR  = os.path.join(PARENT_DIR, "configs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "face_tracking_config.json")


def get_defaults() -> dict:
    return {
        "theme_mode": "new",
        "osc_ip":     DEFAULT_OSC_IP,
        "osc_port":   DEFAULT_OSC_PORT,
        "osc_prefix": DEFAULT_OSC_PREFIX,
    }


def load_config() -> dict:
    defaults = get_defaults()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        return {**defaults, **loaded}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return defaults


def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        print(f"[Config] Save failed: {e}")
