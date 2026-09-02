"""
config.py
─────────
load_config / save_config / get_defaults, always merging saved JSON
over defaults (§6.17 of the porting guide) so a fresh key added in a
later version never wipes an existing user's config.
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path

APP_DIR_NAME = "OSC-ScriptMaker"


def _config_dir() -> Path:
    if platform.system() == "Windows":
        base = os.getenv("APPDATA") or str(Path.home())
        return Path(base) / "Nova-Tools" / APP_DIR_NAME
    return Path.home() / ".config" / "nova-tools" / APP_DIR_NAME


CONFIG_DIR = _config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_defaults() -> dict:
    return {
        "theme_mode": "rich_purple",
        "auto_start": False,
        "scripts": [],
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
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass