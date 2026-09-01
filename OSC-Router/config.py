"""
config.py
─────────
Router config I/O and defaults.
"""

import json
import os

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR  = os.path.dirname(SCRIPT_DIR)
CONFIG_DIR  = os.path.join(PARENT_DIR, "configs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "router_config.json")


def get_defaults() -> dict:
    return {
        "theme_mode": "new",
        "sources": [
            {"name": "Chatbox",       "port": 9010},
            {"name": "Face Tracking", "port": 9011},
        ],
        "outputs": [
            {
                "name":    "VRChat",
                "ip":      "127.0.0.1",
                "port":    9000,
                "sources": ["Chatbox", "Face Tracking"],
            }
        ],
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
    print(f"[Config] Saved ({len(cfg.get('sources',[]))} sources, {len(cfg.get('outputs',[]))} outputs)")