"""
modules/registry.py
───────────────────
Every chatbox module is defined here as a simple render function.

A module is a dict:
  {
    "id":       str,
    "label":    str,
    "category": str,
    "render":   callable,
    "has_text": bool,
  }

GPU and VRAM modules use their optional text field as a zero-based GPU index.

Examples:

    GPU Name (Index) [0] -> first GPU
    GPU Name (Index) [1] -> second GPU
    GPU Name (Index) [2] -> third GPU
"""

from monitors.media import progress_bar, fmt_time, clean_value, detail_line
from monitors.network import fmt_net


# ── Render helpers ────────────────────────────────────────────────────────────

def _fmt(val, suffix="", fallback="N/A") -> str:
    try:
        f = float(val)
    except (TypeError, ValueError):
        return fallback

    if f <= 0:
        return fallback

    return (
        f"{int(f)}{suffix}"
        if f == int(f)
        else f"{f:.1f}{suffix}"
    )


def _gpu_index(slot) -> int:
    """
    Read the GPU index from the module's text field.

    Invalid values safely fall back to GPU 0.
    Negative values are clamped to 0.
    """
    try:
        return max(
            0,
            int(str(slot.get("text", "0")).strip() or "0")
        )
    except (TypeError, ValueError):
        return 0


def _gpu_data(snap, slot):
    """
    Return the selected GPU's telemetry dictionary.

    If the requested index does not exist, return None rather than
    accidentally displaying another GPU's data.
    """
    gpus = snap.get("gpus") or []
    index = _gpu_index(slot)

    if 0 <= index < len(gpus):
        return gpus[index]

    return None


# ── Render functions ──────────────────────────────────────────────────────────

def _render_time(snap, slot):
    import time
    return time.strftime("%H:%M")


def _render_custom(snap, slot):
    return slot.get("text", "")


def _render_divider(snap, slot):
    return "─" * 15


# ── CPU ───────────────────────────────────────────────────────────────────────

def _render_cpu_name(snap, slot):
    return snap.get("cpu_name", "CPU Unknown")


def _render_cpu_load(snap, slot):
    return _fmt(snap.get("cpu_load"), "%")


def _render_cpu_temp(snap, slot):
    return _fmt(snap.get("cpu_temp"), "℃")


def _render_cpu_power(snap, slot):
    return _fmt(snap.get("cpu_power"), "w")


# ── GPU ───────────────────────────────────────────────────────────────────────

def _render_gpu_name(snap, slot):
    gpu = _gpu_data(snap, slot)

    if gpu:
        return gpu.get("name", "GPU Unknown")

    return "GPU Unknown"


def _render_gpu_load(snap, slot):
    gpu = _gpu_data(snap, slot)

    return _fmt(
        gpu.get("load") if gpu else None,
        "%",
    )


def _render_gpu_temp(snap, slot):
    gpu = _gpu_data(snap, slot)

    return _fmt(
        gpu.get("temp") if gpu else None,
        "℃",
    )


def _render_gpu_power(snap, slot):
    gpu = _gpu_data(snap, slot)

    return _fmt(
        gpu.get("power") if gpu else None,
        "w",
    )


# ── VRAM ──────────────────────────────────────────────────────────────────────

def _render_vram_used(snap, slot):
    gpu = _gpu_data(snap, slot)

    if not gpu:
        return "N/A"

    return f"{gpu.get('vram_used', 0.0):.1f}GB"


def _render_vram_total(snap, slot):
    gpu = _gpu_data(snap, slot)

    if not gpu:
        return "N/A"

    return f"{gpu.get('vram_total', '?')}GB"


def _render_vram_combined(snap, slot):
    gpu = _gpu_data(snap, slot)

    if not gpu:
        return "N/A"

    return (
        f"{gpu.get('vram_type', 'GDDR')} "
        f"{gpu.get('vram_used', 0.0):.1f}GB/"
        f"{gpu.get('vram_total', '?')}GB"
    )


# ── RAM ───────────────────────────────────────────────────────────────────────

def _render_ram_used(snap, slot):
    return f"{snap.get('dram_used', 0.0):.1f}GB"


def _render_ram_total(snap, slot):
    return f"{snap.get('dram_total', '?')}GB"


def _render_ram_combined(snap, slot):
    return (
        f"{snap.get('dram_type', 'DDR')} "
        f"{snap.get('dram_used', 0.0):.1f}GB/"
        f"{snap.get('dram_total', '?')}GB"
    )


# ── SteamVR ───────────────────────────────────────────────────────────────────

def _render_fps_vr(snap, slot):
    v = snap.get("vr_fps")
    return f"{v}" if v else "N/A"


def _render_vr_frametime(snap, slot):
    v = snap.get("vr_frametimes")
    return f"{v}ms" if v else "N/A"


def _render_vr_reprojection(snap, slot):
    v = snap.get("vr_reprojection")

    if v is None:
        return "Reproj: N/A"

    return f"Reproj: {int(v * 100)}%"


def _render_vr_headset(snap, slot):
    return snap.get("vr_headset") or "Headset: N/A"


def _render_vr_connected(snap, slot):
    return "🟢 VR On" if snap.get("vr_connected") else "🔴 VR Off"


# ── VR Battery helpers ───────────────────────────────────────────────────────

def _batt_str(pct, charging):
    if pct is None:
        return "N/A"

    icon = "⚡" if charging else "🔋"

    return f"{icon}{pct}%"


def _render_vr_hmd_battery(snap, slot):
    return (
        f"HMD: "
        f"{_batt_str(snap.get('vr_hmd_battery'), snap.get('vr_hmd_charging'))}"
    )


def _render_vr_lc_battery(snap, slot):
    return (
        f"LC: "
        f"{_batt_str(snap.get('vr_lc_battery'), snap.get('vr_lc_charging'))}"
    )


def _render_vr_rc_battery(snap, slot):
    return (
        f"RC: "
        f"{_batt_str(snap.get('vr_rc_battery'), snap.get('vr_rc_charging'))}"
    )


def _render_vr_all_battery(snap, slot):
    parts = [
        f"HMD:{_batt_str(snap.get('vr_hmd_battery'), snap.get('vr_hmd_charging'))}",
        f"LC:{_batt_str(snap.get('vr_lc_battery'), snap.get('vr_lc_charging'))}",
        f"RC:{_batt_str(snap.get('vr_rc_battery'), snap.get('vr_rc_charging'))}",
    ]

    return "  ".join(parts)


# ── Tracker battery ───────────────────────────────────────────────────────────

_MAX_TRACKERS = 10


def _make_tracker_render(idx):
    def _render(snap, slot):
        trackers = snap.get("vr_trackers", [])

        if idx >= len(trackers):
            return f"T{idx + 1}: N/A"

        t = trackers[idx]

        return _batt_str(
            t.get("battery"),
            t.get("charging"),
        )

    return _render


_TRACKER_MODULES = [
    {
        "id": f"vr_tracker_{i + 1}_battery",
        "label": f"Tracker {i + 1} Battery (Beta)",
        "category": "VR Trackers",
        "render": _make_tracker_render(i),
        "has_text": False,
    }
    for i in range(_MAX_TRACKERS)
]


# ── Channels (cross-tool broadcast, e.g. OSC-ScriptMaker's Chatbox Message
#    action in "Send to Chatbox (channel)" mode) ───────────────────────────────

_NUM_CHANNELS = 10


def _make_channel_render(n):
    def _render(snap, slot):
        text = snap.get(f"channel_{n}_text", "")
        return text if text else f"Channel {n}: N/A"

    return _render


_CHANNEL_MODULES = [
    {
        "id": f"channel_{n}",
        "label": f"Channel {n}",
        "category": "Channels",
        "render": _make_channel_render(n),
        "has_text": False,
    }
    for n in range(1, _NUM_CHANNELS + 1)
]


# ── VRChat ────────────────────────────────────────────────────────────────────

def _render_fps_desktop(snap, slot):
    v = snap.get("vrc_fps")
    return f"{v}" if v else "N/A"


def _render_vrc_world(snap, slot):
    return snap.get("vrc_world") or "N/A"


def _render_vrc_players(snap, slot):
    n = snap.get("vrc_player_count", 0)
    return f"{n}"


def _render_vrc_avatar(snap, slot):
    return snap.get("vrc_avatar") or "N/A"


def _render_vrc_ping(snap, slot):
    v = snap.get("vrc_ping")
    return f"{v}ms" if v else "N/A"


# ── Network ───────────────────────────────────────────────────────────────────

def _render_net_down(snap, slot):
    return f"{fmt_net(snap.get('net_down', 0.0))} ↓"


def _render_net_up(snap, slot):
    return f"{fmt_net(snap.get('net_up', 0.0))} ↑"


# ── Weather ───────────────────────────────────────────────────────────────────

def _render_weather_temp(snap, slot):
    temp = snap.get("weather_temp", "?")
    return f"{temp}°C" if temp != "?" else "?"


def _render_weather_humidity(snap, slot):
    humidity = snap.get("weather_humidity", "?")
    return f"{humidity}%" if humidity != "?" else "?"


def _render_weather_desc(snap, slot):
    return snap.get("weather_desc", "Unavailable")


def _render_weather_full(snap, slot):
    temp = snap.get("weather_temp", "?")
    temp_str = f"{temp}°C" if temp != "?" else "?"

    humidity = snap.get("weather_humidity", "?")
    humidity_str = f"{humidity}%" if humidity != "?" else "?"

    desc = snap.get("weather_desc", "Unavailable")

    return f"{temp_str} {desc} {humidity_str}"


# ── Media ─────────────────────────────────────────────────────────────────────

def _render_media_title(snap, slot):
    return snap.get("media_title_clean") or "Nothing Playing"


def _render_media_artist(snap, slot):
    return clean_value(
        snap.get("media_info", {}).get("artist")
    ) or "Unknown Artist"


def _render_media_album(snap, slot):
    return clean_value(
        snap.get("media_info", {}).get("album")
    ) or "Unknown Album"


def _render_media_source(snap, slot):
    return clean_value(
        snap.get("media_info", {}).get("source")
    ) or "Unknown Source"


def _render_media_progress(snap, slot):
    return snap.get("progress_bar_str", "")


def _render_media_time(snap, slot):
    return snap.get("media_time_str", "0:00 / 0:00")


def _render_media_detail(snap, slot):
    return detail_line(snap.get("media_info", {}))


# ── Fun ───────────────────────────────────────────────────────────────────────

def _render_ascii_cat(snap, slot):
    return "/|_/|\n(＞.＜)\n|     \\\n      | || |ノ"

def _render_ascii_dog_1(snap, slot):
    return "  __      _\no''')}____//\n `_/      )\n (_(_/-(_/"

def _render_ascii_dog_2(snap, slot):
    return (
        f"""
        __
   (___()'`;
    /,    /`
   \\"--\\"
"""
    )

def _render_ascii_fish(snap, slot):
    return "<`)))><"

def _render_ascii_bad_dragon(snap, slot):
    return (
        f""" 
      ≥
 ∠..- 
"""
    )


# ── Module registry ───────────────────────────────────────────────────────────

MODULES = [

    # ── Basic ─────────────────────────────────────────────────────────────────

    {
        "id": "custom_text",
        "label": "Custom Text",
        "category": "Basic",
        "render": _render_custom,
        "has_text": True,
    },

    {
        "id": "time",
        "label": "Current Time",
        "category": "Basic",
        "render": _render_time,
        "has_text": False,
    },

    {
        "id": "divider",
        "label": "Divider",
        "category": "Basic",
        "render": _render_divider,
        "has_text": False,
    },


    # ── CPU ───────────────────────────────────────────────────────────────────

    {
        "id": "cpu_name",
        "label": "CPU Name",
        "category": "CPU",
        "render": _render_cpu_name,
        "has_text": False,
    },

    {
        "id": "cpu_load",
        "label": "CPU Load %",
        "category": "CPU",
        "render": _render_cpu_load,
        "has_text": False,
    },

    {
        "id": "cpu_temp",
        "label": "CPU Temp ℃",
        "category": "CPU",
        "render": _render_cpu_temp,
        "has_text": False,
    },

    {
        "id": "cpu_power",
        "label": "CPU Power W",
        "category": "CPU",
        "render": _render_cpu_power,
        "has_text": False,
    },


    # ── GPU ───────────────────────────────────────────────────────────────────

    {
        "id": "gpu_name",
        "label": "GPU Name (Index)",
        "category": "GPU",
        "render": _render_gpu_name,
        "has_text": True,
    },

    {
        "id": "gpu_load",
        "label": "GPU Load % (Index)",
        "category": "GPU",
        "render": _render_gpu_load,
        "has_text": True,
    },

    {
        "id": "gpu_temp",
        "label": "GPU Temp ℃ (Index)",
        "category": "GPU",
        "render": _render_gpu_temp,
        "has_text": True,
    },

    {
        "id": "gpu_power",
        "label": "GPU Power W (Index)",
        "category": "GPU",
        "render": _render_gpu_power,
        "has_text": True,
    },


    # ── VRAM ──────────────────────────────────────────────────────────────────

    {
        "id": "vram_used",
        "label": "VRAM Used GB (Index)",
        "category": "Memory",
        "render": _render_vram_used,
        "has_text": True,
    },

    {
        "id": "vram_total",
        "label": "VRAM Total GB (Index)",
        "category": "Memory",
        "render": _render_vram_total,
        "has_text": True,
    },

    {
        "id": "vram_used_of_total",
        "label": "VRAM Used/Total (Index)",
        "category": "Memory",
        "render": _render_vram_combined,
        "has_text": True,
    },


    # ── RAM ───────────────────────────────────────────────────────────────────

    {
        "id": "ram_used",
        "label": "RAM Used GB",
        "category": "Memory",
        "render": _render_ram_used,
        "has_text": False,
    },

    {
        "id": "ram_total",
        "label": "RAM Total GB",
        "category": "Memory",
        "render": _render_ram_total,
        "has_text": False,
    },

    {
        "id": "ram_used_of_total",
        "label": "RAM Used/Total",
        "category": "Memory",
        "render": _render_ram_combined,
        "has_text": False,
    },


    # ── VR ────────────────────────────────────────────────────────────────────

    {
        "id": "vr_fps",
        "label": "SteamVR FPS",
        "category": "VR",
        "render": _render_fps_vr,
        "has_text": False,
    },

    {
        "id": "vr_frame-time",
        "label": "VR Frame Time",
        "category": "VR",
        "render": _render_vr_frametime,
        "has_text": False,
    },

    {
        "id": "vr_reprojection",
        "label": "VR Reprojection %",
        "category": "VR",
        "render": _render_vr_reprojection,
        "has_text": False,
    },

    {
        "id": "vr_headset",
        "label": "VR Headset Name",
        "category": "VR",
        "render": _render_vr_headset,
        "has_text": False,
    },

    {
        "id": "vr_connected",
        "label": "VR Connected Status",
        "category": "VR",
        "render": _render_vr_connected,
        "has_text": False,
    },


    # ── VR Battery ────────────────────────────────────────────────────────────

    {
        "id": "vr_hmd_battery",
        "label": "Headset Battery",
        "category": "VR",
        "render": _render_vr_hmd_battery,
        "has_text": False,
    },

    {
        "id": "vr_lc_battery",
        "label": "Left Controller Batt",
        "category": "VR",
        "render": _render_vr_lc_battery,
        "has_text": False,
    },

    {
        "id": "vr_rc_battery",
        "label": "Right Controller Batt",
        "category": "VR",
        "render": _render_vr_rc_battery,
        "has_text": False,
    },

    {
        "id": "vr_all_battery",
        "label": "All Batteries",
        "category": "VR",
        "render": _render_vr_all_battery,
        "has_text": False,
    },


    # ── VRChat ────────────────────────────────────────────────────────────────

    {
        "id": "desktop_fps",
        "label": "Desktop FPS (Beta)",
        "category": "VRChat",
        "render": _render_fps_desktop,
        "has_text": False,
    },

    {
        "id": "vrc_world",
        "label": "World Name",
        "category": "VRChat",
        "render": _render_vrc_world,
        "has_text": False,
    },

    {
        "id": "vrc_players",
        "label": "Player Count",
        "category": "VRChat",
        "render": _render_vrc_players,
        "has_text": False,
    },

    {
        "id": "vrc_avatar",
        "label": "Avatar Name",
        "category": "VRChat",
        "render": _render_vrc_avatar,
        "has_text": False,
    },

    {
        "id": "vrc_ping",
        "label": "VRChat Ping (Beta)",
        "category": "VRChat",
        "render": _render_vrc_ping,
        "has_text": False,
    },


    # ── Network ───────────────────────────────────────────────────────────────

    {
        "id": "net_down",
        "label": "Download Speed",
        "category": "Network",
        "render": _render_net_down,
        "has_text": False,
    },

    {
        "id": "net_up",
        "label": "Upload Speed",
        "category": "Network",
        "render": _render_net_up,
        "has_text": False,
    },


    # ── Weather ───────────────────────────────────────────────────────────────

    {
        "id": "weather_temp",
        "label": "Weather Temp",
        "category": "Weather",
        "render": _render_weather_temp,
        "has_text": False,
    },

    {
        "id": "weather_humidity",
        "label": "Weather Humidity",
        "category": "Weather",
        "render": _render_weather_humidity,
        "has_text": False,
    },

    {
        "id": "weather_desc",
        "label": "Weather Description",
        "category": "Weather",
        "render": _render_weather_desc,
        "has_text": False,
    },

    {
        "id": "weather_full",
        "label": "Weather Full Line",
        "category": "Weather",
        "render": _render_weather_full,
        "has_text": False,
    },


    # ── Media ─────────────────────────────────────────────────────────────────

    {
        "id": "media_title",
        "label": "Media Title",
        "category": "Media",
        "render": _render_media_title,
        "has_text": False,
    },

    {
        "id": "media_artist",
        "label": "Media Artist",
        "category": "Media",
        "render": _render_media_artist,
        "has_text": False,
    },

    {
        "id": "media_album",
        "label": "Media Album",
        "category": "Media",
        "render": _render_media_album,
        "has_text": False,
    },

    {
        "id": "media_source",
        "label": "Media Source App",
        "category": "Media",
        "render": _render_media_source,
        "has_text": False,
    },

    {
        "id": "media_progress",
        "label": "Media Progress Bar",
        "category": "Media",
        "render": _render_media_progress,
        "has_text": False,
    },

    {
        "id": "media_time",
        "label": "Media Time",
        "category": "Media",
        "render": _render_media_time,
        "has_text": False,
    },

    {
        "id": "media_detail",
        "label": "Media Detail Line",
        "category": "Media",
        "render": _render_media_detail,
        "has_text": False,
    },


    # ── Fun ───────────────────────────────────────────────────────────────────

    {
        "id": "ascii_cat",
        "label": "ASCII Cat",
        "category": "Fun",
        "render": _render_ascii_cat,
        "has_text": False,
    },

    {
        "id": "ascii_dog_1",
        "label": "ASCII Dog 1",
        "category": "Fun",
        "render": _render_ascii_dog_1,
        "has_text": False,
    },

    {
        "id": "ascii_dog_2",
        "label": "ASCII Dog 2",
        "category": "Fun",
        "render": _render_ascii_dog_2,
        "has_text": False,
    },

    {
        "id": "ascii_fish",
        "label": "ASCII Fish",
        "category": "Fun",
        "render": _render_ascii_fish,
        "has_text": False,
    },

    {
        "id": "ascii_bad_dragon",
        "label": "ASCII Bad dragon (Beta)",
        "category": "Fun",
        "render": _render_ascii_bad_dragon,
        "has_text": False,
    },
]


# Append dynamic tracker modules.
MODULES.extend(_TRACKER_MODULES)

# Append dynamic channel modules.
MODULES.extend(_CHANNEL_MODULES)


# Fast lookup by id.
MODULE_BY_ID: dict[str, dict] = {
    m["id"]: m for m in MODULES
}


# Palette grouped by category.
CATEGORIES: dict[str, list[dict]] = {}

for _m in MODULES:
    CATEGORIES.setdefault(
        _m["category"],
        []
    ).append(_m)


def render_slot(slot: dict, snap: dict) -> str:
    """
    Render a single slot against a state snapshot.

    Supports nested horizontal modules if 'modules' is a list.
    """

    if "modules" in slot and isinstance(slot["modules"], list):
        sub_texts = []

        for sub_slot in slot["modules"]:
            mod = MODULE_BY_ID.get(
                sub_slot.get("module", "")
            )

            if mod:
                try:
                    text = mod["render"](
                        snap,
                        sub_slot,
                    )

                    if text:
                        sub_texts.append(text)

                except Exception:
                    sub_texts.append(
                        f"[{sub_slot.get('module', '?')} error]"
                    )

        return " ".join(sub_texts)


    mod = MODULE_BY_ID.get(
        slot.get("module", "")
    )

    if mod is None:
        return ""


    try:
        return mod["render"](
            snap,
            slot,
        )

    except Exception:
        return f"[{slot.get('module', '?')} error]"


def render_page(page: dict, snap: dict) -> str:
    """Render all slots in a page and join with newlines."""

    lines = []

    for slot in page.get("slots", []):
        line = render_slot(
            slot,
            snap,
        )

        if line:
            lines.append(line)

    return "\n".join(lines)