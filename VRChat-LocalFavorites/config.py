"""
config.py
──────────
Load/save config for VRChat Local Favorites. Always merge loaded
values over defaults so adding a new key later never resets an
existing user's saved config.
"""

from __future__ import annotations

import json
import os

APP_DIR = os.path.join(os.path.expanduser("~"), ".vrchat-local-favorites")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
SESSION_BLOB_FILE = os.path.join(APP_DIR, "session.blob")  # only used in "master_password" mode
FAVORITES_DIR = os.path.join(APP_DIR, "favorites")


def get_defaults() -> dict:
    return {
        "theme_mode": "rich_purple",
        "username": "",
        "favorites_dir": FAVORITES_DIR,
        "secure_storage_mode": "keyring",   # "keyring" | "master_password" | "none"
        "pw_manager_item_name": "VRChat Local Favorites",
        "keepass_db_path": "",
        "did_first_launch_import_prompt": False,
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
