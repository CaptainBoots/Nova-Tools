"""
config.py
─────────
VRChat Launcher config I/O and defaults. The original tool had no
persistence at all — profiles, the launch.exe path, and the theme
were all lost on every restart. This adds it.
"""

import json
import os

from core.launcher import DEFAULT_LAUNCH_EXE, default_profile, resync_uid_counter

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR  = os.path.dirname(SCRIPT_DIR)
CONFIG_DIR  = os.path.join(PARENT_DIR, "configs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "launcher_config.json")


def get_defaults() -> dict:
    return {
        "theme_mode": "rich_purple",
        "launch_exe": DEFAULT_LAUNCH_EXE,
        "profiles": [default_profile(i) for i in range(3)],
    }


def load_config() -> dict:
    defaults = get_defaults()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        merged = {**defaults, **loaded}
        if not merged.get("profiles"):
            merged["profiles"] = defaults["profiles"]
        resync_uid_counter(merged["profiles"])
        return merged
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        resync_uid_counter(defaults["profiles"])
        return defaults


def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        print(f"[Config] Save failed: {e}")
