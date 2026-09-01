"""
config.py
─────────
OSC Parameter Browser config I/O and defaults.
"""

import json
import os

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR  = os.path.dirname(SCRIPT_DIR)
CONFIG_DIR  = os.path.join(PARENT_DIR, "configs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "parameter_browser_config.json")


def get_defaults() -> dict:
    return {
        "theme_mode":  "new",
        "target_ip":   "127.0.0.1",
        "send_port":   9000,
        "listen_port": 9001,
        "inject_addr": "/avatar/parameters/",
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

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
