"""
state.py
────────
Single shared AppState object. All mutable runtime values live here.
Both the OSC loop (background thread) and the UI (main thread) access this.
Cross-thread fields are protected by a threading.Lock via helper methods.
"""

import threading
from dataclasses import dataclass, field

# ── Progress bar defaults ─────────────────────────────────────────────────────
DEFAULT_PROGRESS_FILLED = "\u2592"
DEFAULT_PROGRESS_BORDER = "\u2593"
DEFAULT_PROGRESS_EMPTY  = "\u2591"

# ── Sleep timing ──────────────────────────────────────────────────────────────
DEFAULT_SLEEP    = 1.0
SLOW_SLEEP       = 5.0
SPEED_SLEEP      = 0.1

# ── VRChat chatbox hard limit ─────────────────────────────────────────────────
CHATBOX_MAX_CHARS = 144


@dataclass
class AppState:
    # ── Loop control ──────────────────────────────────────────────────────────
    running:      bool  = False
    sleep_delay:  float = DEFAULT_SLEEP

    # ── Hardware telemetry ────────────────────────────────────────────────────
    cpu_name:    str   = "Unknown CPU"
    cpu_load:    int   = 0
    cpu_temp:    int   = 0
    cpu_power:   int   = 0
    gpu_name:    str   = "Unknown GPU"
    gpu_load:    int   = 0
    gpu_temp:    int   = 0
    gpu_power:   int   = 0
    dram_type:   str   = "DDR"
    dram_used:   float = 0.0
    dram_total:  str   = "?"
    vram_type:   str   = "GDDR"
    vram_used:   float = 0.0
    vram_total:  str   = "?"

    # ── Network ───────────────────────────────────────────────────────────────
    net_up:   float = 0.0
    net_down: float = 0.0

    # ── Weather ───────────────────────────────────────────────────────────────
    weather_temp:     str = "?"
    weather_humidity: str = "?"
    weather_desc:     str = "Unavailable"

    # ── Media ─────────────────────────────────────────────────────────────────
    media_info: dict = field(default_factory=dict)

    # ── Feature flags ─────────────────────────────────────────────────────────
    slow_mode:              bool = False
    speed_mode:             bool = False
    media_title_trim:       bool = True
    cat_mode:               bool = False

    # Dev Menu toggle. Deliberately NOT synced to/from cfg (same as
    # `testing`) — it's a session-only tool, not a persisted preference, so
    # nobody ends up broadcasting fake VRChat/media data after forgetting
    # they turned it on last time.
    fake_data:               bool = False

    # ── Progress bar chars ────────────────────────────────────────────────────
    progress_filled: str = DEFAULT_PROGRESS_FILLED
    progress_border: str = DEFAULT_PROGRESS_BORDER
    progress_empty:  str = DEFAULT_PROGRESS_EMPTY

    # ── Internal lock ─────────────────────────────────────────────────────────
    _lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False, compare=False
    )

    # ── Thread-safe update helpers ────────────────────────────────────────────
    def update_hardware(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)

    def update_network(self, up: float, down: float):
        with self._lock:
            self.net_up   = up
            self.net_down = down

    def update_weather(self, temp: str, humidity: str, desc: str):
        with self._lock:
            self.weather_temp     = temp
            self.weather_humidity = humidity
            self.weather_desc     = desc

    def update_media(self, info: dict):
        with self._lock:
            self.media_info = info

    def snapshot(self) -> dict:
        """Return a thread-safe copy of all state fields as a plain dict."""
        with self._lock:
            return {
                k: v for k, v in self.__dict__.items()
                if not k.startswith("_")
            }