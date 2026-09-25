"""
hardware/cpu.py
───────────────
CPU name detection and individual sensor readers.

All public functions return a single scalar value so module registry
can call them independently. No LibreHardwareMonitor anywhere:
Linux reads /sys directly, Windows uses inbox APIs only
(hardware/win32.py) — anything with no inbox API reads 0 ("N/A").
"""

import re
import subprocess
import sys

from hardware.win32 import is_admin



def detect_cpu(testing: bool = False) -> str:
    if testing:
        return _clean("testing_cpu")
    else:
      if sys.platform == "win32":
          try:
              out = subprocess.check_output(
                  ["powershell", "-NoProfile", "-Command",
                   "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"],
                  encoding="utf-8", stderr=subprocess.DEVNULL, timeout=5,
              ).strip()
              return _clean(out)
          except Exception:
              return "CPU Unknown"
      try:
          with open("/proc/cpuinfo") as f:
              for line in f:
                  if line.startswith("model name"):
                      return _clean(line.split(":", 1)[1].strip())
      except OSError:
          pass
      return "CPU Unknown"


def _clean(text: str) -> str:
    text = text.split("@")[0]
    text = re.sub(r"\(.*?\)|\{.*?}", "", text)
    text = re.sub(r"\d+[-\s](?:core|thread|cpu)s?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:cpu|processor)\b", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


# ── Readers (native only — no LHM, no driver) ────────────────────────────────

def get_cpu_temp(data=None) -> int:
    if sys.platform == "win32":
        return _windows_cpu_temp()
    return _linux_cpu_temp()


def get_cpu_power(data=None) -> int:
    if sys.platform == "win32":
        return _windows_cpu_power()
    return _linux_cpu_power()


def get_cpu_load(data=None) -> int:
    # psutil works identically on both platforms, no admin needed.
    try:
        import psutil
        return int(psutil.cpu_percent(interval=None))
    except Exception:
        return 0


def _windows_cpu_temp() -> int:
    """Best-effort CPU temp from WMI thermal zones (tenths of Kelvin).

    The only inbox Windows source — populated on some boards/laptops,
    absent on most desktops. Returns 0 when unavailable ("N/A").
    """
    from hardware.win32 import run_powershell
    out = run_powershell(
        "Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/wmi "
        "-ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty CurrentTemperature"
    )
    best = 0
    for line in out.splitlines():
        try:
            raw = int(line.strip())
        except ValueError:
            continue
        celsius = raw / 10.0 - 273.15
        if 0 < celsius < 150 and celsius > best:
            best = int(celsius)
    return best


def _windows_cpu_power() -> int:
    """Windows has no inbox API for CPU Watts — always 0 ("N/A").

    Any sensor driver for this needs admin to install/load (see
    cpu_power_access()), so without one there is nothing honest to
    report and nothing is estimated.
    """
    return 0


def cpu_temp_access() -> str:
    """Why CPU temp may read as N/A: 'ok'|'denied'|'missing'.

    Windows: the WMI thermal zone is the only inbox source. If it is
    empty, a sensor driver is needed — which needs admin — so a
    non-elevated app is told 'denied' (ask for admin first) and an
    elevated-but-driverless one 'missing'.
    Linux: /sys thermal reads are world-readable, so this is 'ok' when
    a sensor is found, else 'missing'. Never raises.
    """
    if sys.platform == "win32":
        try:
            if _windows_cpu_temp() > 0:
                return "ok"
        except Exception:
            pass
        return "denied" if not is_admin() else "missing"
    try:
        return "ok" if _linux_cpu_temp() > 0 else "missing"
    except Exception:
        return "missing"


# ── Linux fallbacks ───────────────────────────────────────────────────────────
# Best-effort sysfs reading — must never raise, must never need root or
# extra packages. Returns 0 when nothing readable is found so the UI
# shows "N/A" instead of crashing the polling loop.

# hwmon chip names that are known to expose CPU/package temperatures.
# Deliberately broad: coretemp/k10temp/zenpower are the common ones, but
# many boards expose the CPU via nct6775/it87/nct6687/acpitz/cpu_thermal
# or a plain "acpi" thermal node. Unknown chips are still considered if
# their temp labels look CPU-ish (see _CPU_LABEL_KEYWORDS below).
_CPU_HWMON_KEYWORDS = (
    "k10temp", "coretemp", "zenpower", "zenpower3",
    "acpitz", "cpu_thermal", "cpu-thermal", "package",
    "nct6775", "nct6687", "it87", "it8686", "it8665",
    "aquacomputer", "gigabyte", "asus", "msi",
)

# hwmon chip names that may expose *CPU package power* (instantaneous µW).
# Shared by _linux_cpu_power() and cpu_power_access() so the access
# check never reports "ok" for a GPU/NVMe hwmon's power files.
_CPU_POWER_HWMON_KEYWORDS = (
    "zenpower", "k10temp", "coretemp", "nct6775", "it87",
    "cpu", "package", "soc",
)

_CPU_POWER_FILES = (
    "power1_average", "power1_input",
    "power2_average", "power2_input",
)

# tempN_label contents that strongly suggest "this input is the CPU".
# Matched case-insensitively against both the label file and the hwmon
# chip name. "package"/"tdie"/"tctl" are the package sensors;
# "core ..." are per-core sensors (used as fallback, max taken).
_CPU_LABEL_KEYWORDS = (
    "package", "tdie", "tctl", "cpu", "core", "ccd",
    "processor", "soc", "pkg",
)


def _read_first_line(path: str) -> str:
    """Read+strip a sysfs file, "" on any failure. Never raises.

    NOTE: deliberately `open()` + explicit `close()` instead of a
    `with` block — unit tests mock builtins.open with plain file
    mocks (no context-manager protocol), and both styles behave
    identically in production.
    """
    try:
        f = open(path)
        try:
            return f.read().strip()
        finally:
            try:
                f.close()
            except Exception:
                pass
    except (OSError, ValueError):
        return ""


def _linux_cpu_temp() -> int:
    import glob
    # Collect scored candidates: (score, value_celsius).
    # Lower score = better. Package sensors beat per-core, per-core
    # beats generic, generic beats thermal-zone fallback.
    candidates: list[tuple[int, int]] = []

    for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            name = _read_first_line(f"{hwmon}/name").lower()
        except Exception:
            continue
        name_hit = any(k in name for k in _CPU_HWMON_KEYWORDS)

        for temp_file in sorted(glob.glob(f"{hwmon}/temp*_input")):
            try:
                raw = _read_first_line(temp_file)
                if not raw:
                    continue
                val = int(raw)
                if val <= 0:
                    continue
                celsius = val // 1000 if val > 1000 else val
                if not (0 < celsius < 150):
                    continue
            except (OSError, ValueError):
                continue

            # Prefer inputs whose label looks like a CPU sensor.
            label = _read_first_line(
                temp_file.replace("_input", "_label")
            ).lower()
            label_hit = any(k in label for k in _CPU_LABEL_KEYWORDS)

            if label_hit and ("package" in label or "tdie" in label
                              or "tctl" in label or "pkg" in label):
                score = 0
            elif label_hit:
                score = 1
            elif name_hit:
                score = 2
            else:
                # Unknown chip + unlabeled input — keep as last resort
                # rather than ignoring entirely (some boards expose the
                # CPU this way with no label at all).
                score = 3
            candidates.append((score, celsius))

    if candidates:
        # Best score wins; within the same score take the max (hottest
        # core/package is what people expect to see).
        best_score = min(s for s, _ in candidates)
        return max(v for s, v in candidates if s == best_score)

    # Fallback to thermal zones (RPi "cpu-thermal", ACPI "x86_pkg_temp", …).
    for zone in glob.glob("/sys/class/thermal/thermal_zone*"):
        try:
            type_str = _read_first_line(f"{zone}/type").lower()
            if not any(k in type_str for k in (
                    "cpu", "package", "pkg", "acpi", "intel", "amd",
                    "thermal", "soc", "big", "little")):
                continue
            raw = _read_first_line(f"{zone}/temp")
            if not raw:
                continue
            val = int(raw)
            if val <= 0:
                continue
            celsius = val // 1000 if val > 1000 else val
            if 0 < celsius < 150:
                return celsius
        except (OSError, ValueError):
            pass
    return 0


_last_rapl_data = {
    "energy": None,
    "time": None,
    "file": None,
}


def _read_rapl_energy_uj(path: str) -> int | None:
    try:
        raw = _read_first_line(path)
        if not raw:
            return None
        val = int(raw)
        return val if val >= 0 else None
    except (OSError, ValueError):
        return None


def _linux_cpu_power() -> int:
    """True measured CPU package Watts on Linux — never estimated.

    Tries, in order:
      1. RAPL/powercap energy differential (needs read access to
         energy_uj — root-only on many distros).
      2. hwmon power1_average / power1_input (µW, e.g. zenpower) —
         instantaneous, no differential needed.
    Returns 0 on the first tick (baseline) or when nothing readable
    exists, so callers show "N/A". Pair with cpu_power_access() to
    explain a persistent N/A (usually: restart as admin).
    """
    import glob
    import time

    candidates: list[str] = []
    # Top-level domains first (package), then their sub-domains.
    # NOTE: no /name reads here on purpose — every extra file read
    # breaks the polling cadence on systems where reads are slow, and
    # keeps this mock-friendly for unit tests.
    top = sorted(glob.glob("/sys/class/powercap/intel-rapl/intel-rapl:*"))
    candidates += top
    for parent in top:
        # Skip nested (intel-rapl:0:0) in the first list — glob above
        # only matches one level, so collect the second level here.
        # Guard against mocks that return the parent itself.
        for child in sorted(glob.glob(f"{parent}/intel-rapl:*:*")):
            if child != parent and child not in candidates:
                candidates.append(child)
    # Generic powercap zones from other drivers (e.g. AMD energy driver
    # exposing a different top-level dir).
    candidates += sorted(glob.glob("/sys/class/powercap/*/energy_uj"))

    seen: set[str] = set()
    for energy_file in candidates:
        if not energy_file.endswith("energy_uj"):
            energy_file = f"{energy_file}/energy_uj"
        if energy_file in seen:
            continue
        seen.add(energy_file)
        current_energy = _read_rapl_energy_uj(energy_file)
        if current_energy is None:
            continue
        current_time = time.time()

        prev_energy = _last_rapl_data["energy"]
        prev_time = _last_rapl_data["time"]
        prev_file = _last_rapl_data.get("file")

        # If we switched files (e.g. a new domain appeared), re-baseline.
        # The first sight of a domain is also logged (path only, no
        # extra reads) so a suspicious reading can be traced to the
        # exact counter it came from — e.g. package vs core/dram.
        if prev_file is not None and prev_file != energy_file:
            prev_energy, prev_time = None, None
        if prev_file != energy_file:
            print(f"[sensors] CPU power source: {energy_file}")

        _last_rapl_data["energy"] = current_energy
        _last_rapl_data["time"] = current_time
        _last_rapl_data["file"] = energy_file

        if prev_energy is not None and prev_time is not None:
            time_diff = current_time - prev_time
            if time_diff > 0.05:
                energy_diff = current_energy - prev_energy
                # Counter wrap (energy_uj wraps at max_energy_range_uj):
                # treat negative deltas as wrap and skip this tick.
                if energy_diff >= 0:
                    power_watts = (energy_diff / time_diff) / 1_000_000.0
                    if 0 <= power_watts < 1000:
                        return int(round(power_watts))
        return 0

    # ── hwmon instantaneous power (µW) fallback, e.g. zenpower ────────
    for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
        hname = _read_first_line(f"{hwmon}/name").lower()
        if not any(k in hname for k in _CPU_POWER_HWMON_KEYWORDS):
            continue
        for power_file in _CPU_POWER_FILES:
            try:
                raw = _read_first_line(f"{hwmon}/{power_file}")
                if not raw:
                    continue
                microwatts = int(raw)
                if microwatts <= 0:
                    continue
                watts = microwatts / 1_000_000.0
                if 0 < watts < 1000:
                    return int(round(watts))
            except (OSError, ValueError):
                continue
    return 0


def cpu_power_access() -> str:
    """Why CPU wattage may read as N/A on Linux: 'ok'|'denied'|'missing'.

    'ok'      — some RAPL energy file or hwmon power file is readable,
                so _linux_cpu_power() can report real measured Watts.
    'denied'  — power sensor files EXIST but none are readable
                (typical: energy_uj is 0400 root-only on this distro).
                Fix: restart the app as admin (e.g. 'sudo python
                main.py'). Deliberately no estimation fallback — N/A
                stays honest until real Watts are available.
    'missing' — no RAPL/powercap interface at all (VM, container
                without passthrough, exotic driver). Wattage is
                genuinely unavailable on this hardware.

    Windows has no inbox API for CPU Watts at all, so there it is
    'denied' while not elevated (any sensor driver needs admin to
    install/load — ask for admin first) and 'missing' once elevated
    but still driverless. Never raises — safe to call at startup.
    """
    if sys.platform == "win32":
        # No inbox API exists — admin is necessary (driver install/load)
        # but not sufficient (a sensor driver must also exist).
        return "denied" if not is_admin() else "missing"
    import glob

    denied = False
    energy_files: list[str] = []
    for pattern in (
        "/sys/class/powercap/intel-rapl/intel-rapl:*/energy_uj",
        "/sys/class/powercap/intel-rapl/intel-rapl:*:*/energy_uj",
        "/sys/class/powercap/*/energy_uj",
        # Domain-dir form (mirrors _linux_cpu_power's candidate
        # building, which appends energy_uj itself).
        "/sys/class/powercap/intel-rapl/intel-rapl:*",
    ):
        for path in sorted(glob.glob(pattern)):
            cand = path if path.endswith("energy_uj") else f"{path}/energy_uj"
            if cand not in energy_files:
                energy_files.append(cand)

    for path in energy_files:
        try:
            with open(path, "rb") as fh:
                fh.read(1)
            return "ok"
        except PermissionError:
            denied = True
        except OSError:
            continue

    # hwmon instantaneous power (e.g. zenpower) — also real Watts.
    # Same chip-name filter as _linux_cpu_power(): a GPU/NVMe hwmon's
    # power files must NOT make CPU wattage report "ok".
    for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        try:
            hname = _read_first_line(f"{hwmon}/name").lower()
        except Exception:
            continue
        if not any(k in hname for k in _CPU_POWER_HWMON_KEYWORDS):
            continue
        for power_file in _CPU_POWER_FILES:
            try:
                with open(f"{hwmon}/{power_file}", "rb") as fh:
                    fh.read(1)
                return "ok"
            except PermissionError:
                denied = True
            except OSError:
                continue

    if denied or energy_files:
        # Sensor files exist but nothing was readable → permissions
        # (admin) issue. Re-checked on every Start, so a transiently
        # vanishing file can at worst nag once.
        return "denied"
    return "missing"