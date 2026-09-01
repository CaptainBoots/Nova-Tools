"""
hardware/lhm.py
───────────────
LibreHardwareMonitor REST API fetch + shared sensor-tree walking helpers.
"""

import re
import sys
from typing import Generator, Optional

import requests

LHM_URL: str = "http://localhost:8085/data.json"


# ── Sensor-tree helpers (used by cpu.py, gpu.py, memory.py) ──────────────────

def numeric(value) -> float:
    s = re.sub(r"[^\d.-]", "", str(value))
    if not s or s in (".", "-"):
        raise ValueError(f"No numeric content: {value!r}")
    return float(s)


def walk_sensors(node) -> Generator:
    children = node.get("Children", [])
    if not children:
        yield node
    else:
        for child in children:
            yield from walk_sensors(child)


def hw_nodes(data) -> Generator:
    for top in data.get("Children", []):
        for hw in top.get("Children", []):
            yield hw


def is_cpu(text: str) -> bool:
    t = text.lower()
    return ("intel" in t or "amd" in t) and "radeon" not in t


def is_gpu(text: str) -> bool:
    t = text.lower()
    return any(x in t for x in ("radeon", "nvidia", "geforce", "rtx", "gtx", "rx "))


# ── Fetch ─────────────────────────────────────────────────────────────────────

def get_lhm_data() -> Optional[dict]:
    if sys.platform != "win32":
        return None
    try:
        r = requests.get(LHM_URL, timeout=2)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
