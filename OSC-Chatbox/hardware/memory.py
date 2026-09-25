"""
hardware/memory.py
──────────────────
DRAM and VRAM individual stat readers. Native only — no LHM, no driver:
psutil for RAM everywhere, sysfs/nvidia-smi on Linux, nvidia-smi +
inbox performance counters + WMI on Windows.
"""

import subprocess
import sys


def detect_dram_type() -> str:
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["powershell", "-Command",
                 "(Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1).SMBIOSMemoryType"],
                encoding="utf-8", stderr=subprocess.DEVNULL, timeout=5,
            ).strip()
            return {"24": "DDR3", "26": "DDR4", "34": "DDR5", "35": "DDR5"}.get(out, "DDR")
        except Exception:
            return "DDR"
    return _linux_dram_type()


def _linux_dram_type() -> str:
    """Best-effort DDR generation on Linux, else plain "DDR".

    Tries dmidecode (needs root for /dev/mem on some distros, works
    rootless via sysfs on others), then DMI sysfs speed heuristics.
    Never raises, never blocks the UI — all calls have timeouts.
    """
    # ── dmidecode type 17 "DDR4"/"DDR5" strings ──────────────────────
    for cmd in (["dmidecode", "-t", "memory"],
                ["dmidecode", "-t", "17"]):
        try:
            out = subprocess.check_output(
                cmd, encoding="utf-8", stderr=subprocess.DEVNULL,
                timeout=5,
            )
            low = out.lower()
            # Check newest first so a mixed DDR4+DDR5 board reports DDR5.
            for tag in ("ddr5", "ddr4", "ddr3", "ddr2"):
                if tag in low:
                    return tag.upper()
            # Fallback: SMBIOS "Type: DDR4" may appear as "Type: 26" etc.
            import re as _re
            m = _re.search(r"type:\s*(\d+)", low)
            if m:
                return {"24": "DDR3", "26": "DDR4",
                        "34": "DDR5", "35": "DDR5"}.get(m.group(1), "DDR")
        except Exception:
            pass
    # ── DMI sysfs speed heuristic (no root needed) ───────────────────
    # /sys/devices/virtual/dmi/id doesn't expose RAM type directly, but
    # some kernels expose memory speed via /proc-adjacent paths. If we
    # can't tell, plain "DDR" is honest and matches old behaviour.
    try:
        import glob as _glob
        for speed_file in _glob.glob(
                "/sys/devices/system/edac/mc/mc*/dimm*/dimm_mem_type"):
            try:
                with open(speed_file) as f:
                    t = f.read().strip().lower()
                for tag in ("ddr5", "ddr4", "ddr3"):
                    if tag in t:
                        return tag.upper()
            except (OSError, ValueError):
                continue
    except Exception:
        pass
    return "DDR"


def get_vram_type(index: int = 0) -> str:
    try:
        from hardware.gpu import detect_gpu, detect_vram_type
        gpu_name = detect_gpu(index)
        return detect_vram_type(gpu_name)
    except Exception:
        return "GDDR6"


def _psutil_ram():
    import psutil
    vm = psutil.virtual_memory()
    return round(vm.used / (1024**3), 1), _fmt_gb(vm.total / (1024**3))


def _fmt_gb(gb: float) -> str:
    # Round to standard hardware capacities (e.g. 15.9 -> 16, 4.1 -> 4)
    rounded_std = round(gb)
    if abs(gb - rounded_std) < 0.4:
        return str(rounded_std)
    return f"{gb:.1f}"


def get_dram_used(data=None) -> float:
    # psutil works identically on both platforms, no admin needed.
    try:
        return _psutil_ram()[0]
    except Exception:
        return 0.0


def get_dram_total(data=None) -> str:
    try:
        import psutil
        return _fmt_gb(psutil.virtual_memory().total / (1024**3))
    except Exception:
        return "?"


def get_vram_used(index: int = 0, data=None) -> float:
    if sys.platform == "win32":
        return _windows_vram_used(index)
    return _linux_vram(index)[0]


def get_vram_total(index: int = 0, data=None) -> str:
    if sys.platform == "win32":
        total = _windows_vram_total(index)
    else:
        total = _linux_vram(index)[1]
    return _fmt_gb(total) if total else "?"


def _nvidia_vram(index: int = 0) -> tuple[float, float | None]:
    """(used GB, total GB|None) via nvidia-smi — exact, no admin needed."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=5,
        ).strip().splitlines()
        if 0 <= index < len(out):
            parts = out[index].split(",")
            used_mb = float(parts[0].strip())
            total_mb = float(parts[1].strip())
            if total_mb > 0:
                return round(used_mb / 1024.0, 1), total_mb / 1024.0
    except Exception:
        pass
    return 0.0, None


def _windows_vram_used(index: int = 0) -> float:
    """Used VRAM GB on Windows: nvidia-smi, else perf 'Dedicated Usage'."""
    used, _total = _nvidia_vram(index)
    if used > 0:
        return used
    try:
        from hardware.win32 import gpu_dedicated_bytes
        per_phys, total = gpu_dedicated_bytes("Dedicated Usage")
        if index in per_phys and per_phys[index] > 0:
            return round(per_phys[index] / (1024 ** 3), 1)
        if index == 0 and total > 0:
            return round(total / (1024 ** 3), 1)
    except Exception:
        pass
    return 0.0


def _windows_vram_total(index: int = 0):
    """Total VRAM GB on Windows (None = unknown/"?").

    nvidia-smi is exact; the inbox 'Dedicated Limit' perf counter is
    64-bit exact; Win32_VideoController.AdapterRAM is a last resort —
    it is a UInt32 that wraps mod 4 GB on big cards (and is 0 when
    unknown), so only sane values are trusted.
    """
    _used, total = _nvidia_vram(index)
    if total:
        return total
    try:
        from hardware.win32 import gpu_dedicated_bytes
        per_phys, grand = gpu_dedicated_bytes("Dedicated Limit")
        val = per_phys.get(index, grand if index == 0 else 0.0)
        if val and (1024 ** 3) <= val <= 257 * (1024 ** 3):
            return val / (1024 ** 3)
    except Exception:
        pass
    try:
        from hardware.win32 import video_controllers
        rows = video_controllers()
        if 0 <= index < len(rows):
            raw = rows[index].get("AdapterRAM")
            if raw and (1024 ** 3) <= raw <= 257 * (1024 ** 3):
                return raw / (1024 ** 3)
    except Exception:
        pass
    return None


def _linux_vram(index: int = 0):
    try:
        from hardware.gpu import _drm_cards_ordered
        cards = _drm_cards_ordered()
    except Exception:
        import glob
        cards = sorted(glob.glob("/sys/class/drm/card*/device"))
    if 0 <= index < len(cards):
        card = cards[index]
        # ── AMD discrete (amdgpu VRAM counters, bytes) ───────────────
        try:
            used  = int(open(f"{card}/mem_info_vram_used").read().strip())
            total = int(open(f"{card}/mem_info_vram_total").read().strip())
            if total > 0:
                return round(used / (1024**3), 1), total / (1024**3)
        except (OSError, ValueError):
            pass
        # ── Intel iGPU / AMD APU shared memory (GTT counters, bytes) ─
        # No dedicated VRAM — report shared graphics window so the
        # module shows something real instead of N/A.
        try:
            used = int(open(f"{card}/mem_info_gtt_used").read().strip())
            total = int(open(f"{card}/mem_info_gtt_total").read().strip())
            if total > 0:
                return round(used / (1024**3), 1), total / (1024**3)
        except (OSError, ValueError):
            pass
        # ── Generic hwmon-style used/total in bytes (some drivers) ───
        for used_f, total_f in (("mem_used", "mem_total"),):
            try:
                used = int(open(f"{card}/{used_f}").read().strip())
                total = int(open(f"{card}/{total_f}").read().strip())
                if total > 0:
                    return round(used / (1024**3), 1), total / (1024**3)
            except (OSError, ValueError):
                pass

    # NVIDIA fallback via nvidia-smi (shared helper, exact)
    used, total = _nvidia_vram(index)
    if total:
        return used, total
    # AMD rocm-smi fallback ("GPU Memory Usage" lines)
    try:
        import re as _re
        out = subprocess.check_output(
            ["rocm-smi", "--showmemuse"],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=5,
        )
        pairs = _re.findall(r"(\d+)\s*MB\s*/\s*(\d+)\s*MB", out)
        if 0 <= index < len(pairs):
            used_mb, total_mb = float(pairs[index][0]), float(pairs[index][1])
            return round(used_mb / 1024.0, 1), total_mb / 1024.0
    except Exception:
        pass
    return 0.0, None