"""
core/fake_data.py
──────────────────
Pure fake-data generators shared by:

  1. dev_fakedata.py   — standalone launcher that monkeypatches the real
                          hardware/monitor modules before the app starts.
  2. core/osc_loop.py  — the live "Fake Data Mode" toggle in the Dev Menu,
                          which branches per-tick instead of patching.

Kept as plain functions with no side effects (no module patching here) so
both call sites can use the exact same numbers/behaviour without duplicating
logic. Every function mirrors the return shape of its real counterpart in
hardware/*.py or monitors/*.py so callers don't need to know which one they
got.
"""
import math
import time

_T0 = time.time()


def _wave(base, amp, period=20.0, phase=0.0, floor=None, ceil=None):
    """Smooth oscillating value so live readouts look like real telemetry
    instead of flat numbers or noisy random jitter."""
    t = time.time() - _T0
    v = base + amp * math.sin((t / period) * 2 * math.pi + phase)
    if floor is not None:
        v = max(floor, v)
    if ceil is not None:
        v = min(ceil, v)
    return v


# ── CPU ────────────────────────────────────────────────────────────────────────

def cpu_name() -> str:
    return "AMD Ryzen 9 7950X3D (fake)"


def cpu_temp() -> int:
    return int(_wave(55, 15, period=25, floor=0, ceil=100))


def cpu_power() -> int:
    return int(_wave(65, 25, period=18, floor=0))


def cpu_load() -> int:
    return int(_wave(30, 25, period=12, floor=0, ceil=100))


# ── GPU ────────────────────────────────────────────────────────────────────────

def gpu_names() -> list[str]:
    return ["NVIDIA GeForce RTX 4080 (fake)"]


def gpu_temp(index: int = 0) -> int:
    return int(_wave(60, 12, period=22, phase=index, floor=0, ceil=100))


def gpu_power(index: int = 0) -> int:
    return int(_wave(180, 60, period=15, phase=index, floor=0))


def gpu_load(index: int = 0) -> int:
    return int(_wave(45, 40, period=10, phase=index, floor=0, ceil=100))


def vram_type(gpu_name_: str = "") -> str:
    return "GDDR6X"


def vram_used(index: int = 0) -> float:
    return round(_wave(9, 3, period=20, phase=index, floor=0), 1)


def vram_total(index: int = 0) -> str:
    return "16"


# ── Memory ─────────────────────────────────────────────────────────────────────

def dram_type() -> str:
    return "DDR5"


def dram_used() -> float:
    return round(_wave(11, 3, period=30, floor=0), 1)


def dram_total() -> str:
    return "32"


# ── SteamVR telemetry ────────────────────────────────────────────────────────────

def steamvr_snapshot() -> dict:
    return {
        "vr_fps": int(_wave(90, 5, period=8, floor=0)),
        "vr_frametimes": round(_wave(9, 2, period=8, floor=0), 1),
        "vr_reprojection": round(_wave(0.03, 0.03, period=14, floor=0), 2),
        "vr_headset": "Valve Index (fake)",
        "vr_connected": True,
        "vr_hmd_battery": int(_wave(70, 20, period=120, floor=0, ceil=100)),
        "vr_hmd_charging": False,
        "vr_lc_battery": int(_wave(60, 20, period=100, floor=0, ceil=100)),
        "vr_lc_charging": False,
        "vr_rc_battery": int(_wave(55, 20, period=110, floor=0, ceil=100)),
        "vr_rc_charging": False,
        "vr_trackers": [
            {"battery": int(_wave(80, 10, period=90, floor=0, ceil=100)), "charging": False},
            {"battery": int(_wave(75, 10, period=95, floor=0, ceil=100)), "charging": False},
        ],
    }


# ── VRChat log/OSC state ──────────────────────────────────────────────────────────

_WORLDS = ["The Black Cat", "Midnight Rooftop", "Cyberpunk Bar", "Prism Point"]
_AVATARS = ["Novabeast", "Alastor Cosplay", "Chicken Companion Fit"]


def vrchat_snapshot() -> dict:
    t = time.time() - _T0
    return {
        "vrc_fps": int(_wave(72, 8, period=9, floor=0)),
        "vrc_world": _WORLDS[int(t // 40) % len(_WORLDS)],
        "vrc_player_count": int(_wave(12, 8, period=35, floor=1)),
        "vrc_avatar": _AVATARS[int(t // 60) % len(_AVATARS)],
        "vrc_ping": int(_wave(45, 20, period=17, floor=0)),
    }


# ── Media session ──────────────────────────────────────────────────────────────────

_TRACKS = [
    ("Bad Apple!!", "Alstroemeria Records", "Touhou Arrange Album", "Spotify"),
    ("Sandstorm", "Darude", "Before the Storm", "VLC"),
    ("Freedom Dive", "xi", "5argon Rebirth", "foobar2000"),
]


async def media_fetch() -> dict:
    t = time.time() - _T0
    idx = int(t // 45) % len(_TRACKS)
    title, artist, album, source = _TRACKS[idx]
    dur = 210_000
    pos = int((t % 45) / 45 * dur)
    return {
        "title": title, "artist": artist, "album": album, "album_artist": artist,
        "track_number": 1, "track_count": 12, "source": source,
        "position_ms": pos, "duration_ms": dur, "is_paused": False,
    }


# ── Weather ────────────────────────────────────────────────────────────────────────

def weather_fetch(lat_lon: str = "0,0") -> tuple:
    return (
        str(int(_wave(16, 6, period=200))),
        str(int(_wave(65, 15, period=150, floor=0, ceil=100))),
        "Partly cloudy (fake)",
    )


# ── Network throughput ────────────────────────────────────────────────────────────
# Matches monitors.network.sample()'s (cur_counters, up_bps, down_bps, now) shape.
# prev/interface are accepted and ignored since there's no real counter to diff.

def network_sample(prev, prev_time, interface):
    now = time.time()
    up = _wave(50_000, 45_000, period=6, floor=0)
    down = _wave(800_000, 700_000, period=5, floor=0)
    return prev, up, down, now


# ── OSC channel relay (channel_N_text from other tools) ────────────────────────────

def channels_snapshot(num_channels: int = 10) -> dict:
    t = int(time.time() - _T0)
    data = {f"channel_{n}_text": "" for n in range(1, num_channels + 1)}
    data["channel_1_text"] = f"Fake channel message @ {t}s"
    return data
