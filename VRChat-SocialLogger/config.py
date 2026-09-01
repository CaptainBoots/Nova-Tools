"""
config.py
──────────
Load/save config for VRChat Social Logger. Always merge loaded values
over defaults (§6.17) so adding a new key later never resets an
existing user's saved config.
"""

from __future__ import annotations

import json
import os

APP_DIR = os.path.join(os.path.expanduser("~"), ".vrchat-social-logger")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
SESSION_BLOB_FILE = os.path.join(APP_DIR, "session.blob")  # only used in "master_password" mode
DEFAULT_LOG_DIR = os.path.join(APP_DIR, "logs")


def get_defaults() -> dict:
    return {
        "theme_mode": "rich_purple",
        "username": "",             # remembered for convenience, never the password
        "log_dir": DEFAULT_LOG_DIR,
        "friends_log_cap_bytes": 50 * 1024 * 1024,   # 50 MB
        "instance_log_cap_bytes": 50 * 1024 * 1024,  # 50 MB
        "auto_start": False,        # start the engine automatically on launch
        # How the VRChat session is remembered between launches:
        #   "keyring"         — OS credential store (default)
        #   "master_password" — encrypted blob, password typed each launch
        #   "none"            — never remembered, log in fresh every time
        "secure_storage_mode": "keyring",
        "pw_manager_item_name": "VRChat Social Logger",
        "keepass_db_path": "",
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
    os.makedirs(APP_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
