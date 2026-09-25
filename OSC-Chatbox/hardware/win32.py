"""
hardware/win32.py
─────────────────
Shared Windows-native helpers. Everything here uses inbox Windows APIs
(WMI/CIM, performance counters, nvidia-smi) — no LibreHardwareMonitor,
no third-party driver, no admin required just to *read*.

Admin note: CPU temperature/power have no inbox Windows API at all, so
any sensor driver for them needs admin to install/load. The access
helpers in hardware/cpu.py report that as 'denied' while the app isn't
elevated, so the UI can ask for admin first instead of guessing.

All functions are best-effort: they never raise and return an empty /
zero value when the API is unavailable, so the polling loop keeps
running and the UI shows "N/A".
"""

import re
import subprocess
import sys


def is_admin() -> bool:
    """True when running elevated (Administrator / root). Never raises."""
    try:
        if sys.platform == "win32":
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        import os
        return os.geteuid() == 0
    except Exception:
        return False


def run_powershell(script: str, timeout: float = 8.0) -> str:
    """Run a PowerShell snippet, return stripped stdout ("" on failure)."""
    if sys.platform != "win32":
        return ""
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=timeout,
        )
        return out.strip()
    except Exception:
        return ""


def video_controllers() -> list[dict]:
    """Win32_VideoController rows in OS order.

    Each row: {"Name": str, "AdapterRAM": int|None (bytes),
    "PNPDeviceID": str}. AdapterRAM is a UInt32 and wraps mod 4 GB on
    big cards (and is 0 when unknown) — callers must sanity-check it.
    """
    out = run_powershell(
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,PNPDeviceID | ConvertTo-Json -Compress"
    )
    if not out:
        return []
    try:
        import json
        raw = json.loads(out)
    except Exception:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    rows: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            ram = item.get("AdapterRAM")
            ram = int(ram) if ram is not None else None
        except (TypeError, ValueError):
            ram = None
        rows.append({
            "Name": str(item.get("Name") or "").strip(),
            "AdapterRAM": ram,
            "PNPDeviceID": str(item.get("PNPDeviceID") or ""),
        })
    return rows


def _perf_samples(counter_path: str) -> list[tuple[str, float]]:
    """[(instance path, value)] for a '\\GPU ...(*)' perf counter.

    Values are formatted with the invariant culture so decimal parsing
    never depends on the OS display language.
    """
    script = (
        f"(Get-Counter '{counter_path}' -ErrorAction SilentlyContinue)"
        ".CounterSamples | ForEach-Object { $_.Path + '=' + "
        "[string]::Format([cultureinfo]::InvariantCulture, '{0:R}', $_.CookedValue) }"
    )
    out = run_powershell(script)
    samples: list[tuple[str, float]] = []
    for line in out.splitlines():
        if "=" not in line:
            continue
        path, _, val = line.rpartition("=")
        try:
            samples.append((path, float(val.strip())))
        except ValueError:
            continue
    return samples


def _phys_index(path: str) -> int | None:
    """Physical GPU index from a counter instance path ('..._phys_0...')."""
    m = re.search(r"phys_(\d+)", path, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def gpu_engine_util() -> tuple[dict[int, float], float]:
    """3D-engine utilisation: ({phys_index: summed %}, grand total %).

    Sums across engine types (3D/copy/video) per adapter and clamps at
    the call site — a sum over 100 just means several engines busy.
    One Get-Counter call, shared by all GPU indexes.
    """
    per: dict[int, float] = {}
    total = 0.0
    for path, val in _perf_samples("\\GPU Engine(*)\\Utilization Percentage"):
        val = max(0.0, val)
        total += val
        idx = _phys_index(path)
        if idx is not None:
            per[idx] = per.get(idx, 0.0) + val
    return per, total


def gpu_dedicated_bytes(counter: str) -> tuple[dict[int, float], float]:
    """Byte counter under '\\GPU Adapter Memory(*)': ({phys: bytes}, total).

    `counter` is e.g. 'Dedicated Usage' (used VRAM) or 'Dedicated Limit'
    (total VRAM) — both 64-bit, no AdapterRAM-style 4 GB wrap.
    """
    per: dict[int, float] = {}
    total = 0.0
    for path, val in _perf_samples(f"\\GPU Adapter Memory(*)\\{counter}"):
        if val < 0:
            continue
        total += val
        idx = _phys_index(path)
        if idx is not None:
            per[idx] = per.get(idx, 0.0) + val
    return per, total
