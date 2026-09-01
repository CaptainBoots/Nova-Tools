"""
config.py
─────────
Config file I/O, defaults, and migration.

Config is a JSON file stored in a "configs" folder one directory above main.py.
Pages are stored as a list of {enabled, duration, slots} dicts.
"""

import json
import os
import sys

from core.state import (
    DEFAULT_PROGRESS_FILLED, DEFAULT_PROGRESS_BORDER, DEFAULT_PROGRESS_EMPTY,
)

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR  = os.path.dirname(SCRIPT_DIR)
CONFIG_DIR  = os.path.join(PARENT_DIR, "configs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "chatbox_config.json")
SPOTIFY_BLOB_FILE = os.path.join(CONFIG_DIR, "spotify_session.blob")


DEFAULT_PAGES = [
    {
        "enabled":  True,
        "duration": 20,
        "slots": [
            {"module": "custom_text", "text": "Boots's OSC Chatbox"},
            {"module": "time"},
            {"modules": [
                {"module": "custom_text", "text": "Download:"},
                {"module": "net_down"},
            ]},
            {"modules": [
                {"module": "custom_text", "text": "Upload:"},
                {"module": "net_up"},
            ]},
            {"module": "media_progress"},
            {"module": "media_title"},
        ],
    },
    {
        "enabled":  True,
        "duration": 20,
        "slots": [
            {"module": "custom_text", "text": "Hardware"},
            {"module": "time"},
            {"modules": [
                {"module": "cpu_name"},
                {"module": "cpu_load"},
            ]},
            {"modules": [
                {"module": "cpu_temp"},
                {"module": "cpu_power"},
            ]},
            {"modules": [
                {"module": "gpu_name", "text": "0"},
                {"module": "gpu_load", "text": "0"},
            ]},
            {"modules": [
                {"module": "gpu_temp", "text": "0"},
                {"module": "gpu_power", "text": "0"},
            ]},
        ],
    },
    {
        "enabled":  True,
        "duration": 20,
        "slots": [
            {"module": "custom_text", "text": "Memory"},
            {"module": "time"},
            {"module": "ram_used_of_total"},
            {"module": "vram_used_of_total", "text": "0"},
            {"module": "media_progress"},
            {"module": "media_title"},
        ],
    },
    {
        "enabled":  True,
        "duration": 20,
        "slots": [
            {"module": "custom_text", "text": "Local Weather"},
            {"module": "time"},
            {"modules": [
                {"module": "weather_temp"},
                {"module": "weather_humidity"},
            ]},
            {"module": "weather_desc"},
            {"module": "media_progress"},
            {"module": "media_title"},
        ],
    },
    {
        "enabled":  True,
        "duration": 20,
        "slots": [
            {"module": "custom_text", "text": "Now Playing"},
            {"module": "time"},
            {"module": "media_progress"},
            {"module": "media_title"},
            {"modules": [
                {"module": "media_time"},
                {"module": "media_artist"},
            ]},
            {"module": "media_album"},
            {"module": "media_detail"},
        ],
    },
    {
        "enabled":  True,
        "duration": 20,
        "slots": [
            {"module": "custom_text", "text": "VRChat Stats"},
            {"modules": [
                {"module": "custom_text", "text": "VRC FPS:"},
                {"module": "desktop_fps"},
            ]},
            {"modules": [
                {"module": "custom_text", "text": "VRC World:"},
                {"module": "vrc_world"},
            ]},
            {"modules": [
                {"module": "custom_text", "text": "VRC Player Count:"},
                {"module": "vrc_players"},
            ]},
            {"modules": [
                {"module": "custom_text", "text": "VRC Avatar Name:"},
                {"module": "vrc_avatar"},
            ]},
            {"modules": [
                {"module": "custom_text", "text": "VRC Ping:"},
                {"module": "vrc_ping"},
            ]},
        ],
    },
    {
        "enabled":  True,
        "duration": 20,
        "slots": [
            {"module": "custom_text", "text": "Steam VR Stats"},
            {"modules": [
                {"module": "custom_text", "text": "VR FPS:"},
                {"module": "vr_fps"},
            ]},
            {"modules": [
                {"module": "custom_text", "text": "VR Frametime:"},
                {"module": "vr_frame-time"},
            ]},
            {"module": "vr_headset"},
            {"module": "vr_all_battery"},
            {"module": "vr_connected"},
        ],
    },
]


def get_defaults() -> dict:
    return {
        "osc_ip":          "127.0.0.1",
        "osc_port":        9000,
        "interface":       _default_interface(),
        "temp_var1":       "space block",
        "lhm_api":         "http://localhost:8085/data.json",
        "location":        "0,0",
        "slow_mode":      False,
        "speed_mode":      False,
        "media_title_trim": True,
        "cat_mode":       False,
        "progress_filled": DEFAULT_PROGRESS_FILLED,
        "progress_border": DEFAULT_PROGRESS_BORDER,
        "progress_empty":  DEFAULT_PROGRESS_EMPTY,
        "theme_mode":      "new",
        "lhm_prompt":      "ask",
        "pages":           DEFAULT_PAGES,

        # Media priority list (Settings -> Media) — None means "use the
        # built-in default order from core/media_registry.py". Once the
        # person drags anything, this becomes their saved list of keys.
        "media_priority_order": None,

        # Spotify (Settings -> Media -> Spotify)
        "secure_storage_mode":  "keyring",   # "keyring" | "master_password" | "none"
        "spotify_client_id":    "",
        "pw_manager_item_name": "OSC-Chatbox Spotify",
    }


def _default_interface() -> str:
    try:
        import psutil
        ifaces = list(psutil.net_io_counters(pernic=True).keys())
        if sys.platform == "win32":
            for preferred in ("Ethernet", "Wi-Fi"):
                if preferred in ifaces:
                    return preferred
        for iface in ifaces:
            if not iface.lower().startswith("lo"):
                return iface
    except Exception:
        pass
    return "Ethernet" if sys.platform == "win32" else "eth0"


# ── Load / Save ───────────────────────────────────────────────────────────────

def load_config() -> dict:
    defaults = get_defaults()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        merged = {**defaults, **loaded}

        if not isinstance(merged.get("pages"), list) or not merged["pages"]:
            merged["pages"] = DEFAULT_PAGES
        else:
            for page in merged["pages"]:
                if "duration" not in page:
                    page["duration"] = 20

                if "slots" not in page:
                    page["slots"] = []

                if "enabled" not in page:
                    page["enabled"] = True

                # GPU and VRAM modules use their inline text field as a
                # zero-based GPU index.
                for slot in page.get("slots", []):
                    if not isinstance(slot, dict):
                        continue

                    modules = slot.get("modules")

                    if modules is None:
                        modules = [slot]

                    for sub_slot in modules or []:
                        if not isinstance(sub_slot, dict):
                            continue

                        module_id = str(sub_slot.get("module", ""))

                        if (
                                module_id.startswith("gpu_")
                                or module_id.startswith("vram_")
                        ):
                            if not str(sub_slot.get("text", "")).strip():
                                sub_slot["text"] = "0"

        return merged

    except (FileNotFoundError, json.JSONDecodeError):
        return defaults


def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def normalize_char(value, fallback: str) -> str:
    text = str(value).strip() if value else ""
    return text[0] if text else fallback