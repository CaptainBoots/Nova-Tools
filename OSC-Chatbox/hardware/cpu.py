"""
hardware/cpu.py
───────────────
CPU name detection and individual sensor readers.

All public functions return a single scalar value so module registry
can call them independently.
"""

import re
import subprocess
import sys

from hardware.lhm import hw_nodes, is_cpu, numeric, get_lhm_data #ignore



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


# ── LHM readers ───────────────────────────────────────────────────────────────

def _best_sensor(data, category_kw: str, primary_kw: tuple, secondary_kw: tuple) -> int:
    best = {"p": None, "s": None}
    try:
        for hw in hw_nodes(data):
            if not is_cpu(hw.get("Text", "")):
                continue
            for cat in hw.get("Children", []):
                if category_kw not in cat.get("Text", "").lower():
                    continue
                for sensor in cat.get("Children", []):
                    st = sensor.get("Text", "").lower()
                    try:
                        val = numeric(sensor.get("Value", 0))
                    except ValueError:
                        continue
                    if any(p in st for p in primary_kw):
                        best["p"] = val
                    elif any(s in st for s in secondary_kw) and best["s"] is None:
                        best["s"] = val
    except Exception:
        pass
    r = best["p"] if best["p"] is not None else best["s"]
    return int(r) if r is not None else 0


def get_cpu_temp(data) -> int:
    if sys.platform != "win32":
        return _linux_cpu_temp()
    return _best_sensor(
        data, "temperature",
        ("cpu package", "tdie"),
        ("core average", "cpu core", "core max"),
    )


def get_cpu_power(data) -> int:
    if sys.platform != "win32":
        return _linux_cpu_power()
    return _best_sensor(
        data, "power",
        ("cpu package",),
        ("cpu cores", "cpu total", "package"),
    )


def get_cpu_load(data) -> int:
    if sys.platform != "win32":
        try:
            import psutil
            return int(psutil.cpu_percent(interval=None))
        except Exception:
            return 0
    try:
        for hw in hw_nodes(data):
            if not is_cpu(hw.get("Text", "")):
                continue
            for cat in hw.get("Children", []):
                if "load" not in cat.get("Text", "").lower():
                    continue
                for sensor in cat.get("Children", []):
                    if "cpu total" in sensor.get("Text", "").lower():
                        return int(numeric(sensor.get("Value", 0)))
    except Exception:
        pass
    return 0


# ── Linux fallbacks ───────────────────────────────────────────────────────────

def _linux_cpu_temp() -> int:
    import glob
    for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            name = open(f"{hwmon}/name").read().strip().lower()
        except OSError:
            continue
        if not any(k in name for k in ("k10temp", "coretemp")):
            continue
        try:
            val = int(open(f"{hwmon}/temp1_input").read().strip())
            return val // 1000
        except (OSError, ValueError):
            pass
    return 0


def _linux_cpu_power() -> int:
    import glob
    for rapl in glob.glob("/sys/class/powercap/intel-rapl/intel-rapl:0"):
        try:
            return int(open(f"{rapl}/energy_uj").read().strip()) // 1_000_000
        except (OSError, ValueError):
            pass
    return 0