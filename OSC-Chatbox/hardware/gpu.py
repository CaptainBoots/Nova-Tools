"""
hardware/gpu.py
───────────────
GPU discovery and per-GPU sensor readers.

GPU index is zero-based. The same index is used by the UI GPU modules and
by the per-GPU telemetry list in AppState.
"""

import json
import re
import subprocess
import sys
from typing import Optional

from core.gpu_ids import GPU_ID_MAP, AMBIGUOUS_IDS


_AMD_IGPU_KEYWORDS = (
    "radeon graphics",
    "vega",
    "raphael",
    "rembrandt",
    "phoenix",
    "hawk point",
)

_AMD_DGPU_KEYWORDS = (
    "radeon rx",
    "rx ",
)


def _vendor_priority(vid: str, name: str = "") -> int:
    """
    Lower is better for the legacy single-GPU fallback.
    """
    n = name.lower()

    if vid == "10de":
        return 0

    if vid == "1002":
        if any(
                k in n
                for k in _AMD_DGPU_KEYWORDS
        ):
            return 0

        if any(
                k in n
                for k in _AMD_IGPU_KEYWORDS
        ):
            return 2

        return 1

    return 3


def _command_lines(
        command: list[str],
        timeout: float = 5.0,
) -> list[str]:
    """
    Run a command safely and return non-empty output lines.

    This is deliberately best-effort: missing utilities such as lspci or
    nvidia-smi must never stop the application from running.
    """
    try:
        out = subprocess.check_output(
            command,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )

        return [
            line.strip()
            for line in out.splitlines()
            if line.strip()
        ]

    except (
            OSError,
            subprocess.SubprocessError,
            UnicodeError,
    ):
        return []


def _windows_gpu_records() -> list[dict]:
    """
    Discover GPUs using Windows WMI/CIM.

    Returns dictionaries containing Name and PNPDeviceID.
    """
    command = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,PNPDeviceID | "
        "ConvertTo-Json -Compress"
    )

    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                command,
            ],
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()

        raw = (
            json.loads(out)
            if out
            else []
        )

        if isinstance(raw, dict):
            raw = [raw]

        return (
            raw
            if isinstance(raw, list)
            else []
        )

    except Exception:
        return []


def _linux_display_lines() -> list[str]:
    """
    Discover display adapters through lspci.

    Supports VGA, 3D-controller and Display-controller devices.
    Falls back to a sysfs PCI-class scan when lspci is missing
    (minimal containers/distros) — class 0x03xxxx = display.
    """
    lines = [
        line
        for line in _command_lines(
            ["lspci", "-Dnn"]
        )
        if (
                "VGA compatible controller" in line
                or "3D controller" in line
                or "Display controller" in line
        )
    ]
    if lines:
        return lines
    return _sysfs_display_lines()


def _sysfs_display_lines() -> list[str]:
    """Best-effort display discovery without lspci.

    Scans /sys/bus/pci/devices/*/class for 0x03xxxx and builds
    lspci-like lines from the vendor/device sysfs files so the rest
    of the parsing pipeline keeps working unchanged.
    """
    import glob
    import os
    lines: list[str] = []
    for dev_path in sorted(glob.glob("/sys/bus/pci/devices/*")):
        try:
            with open(os.path.join(dev_path, "class")) as f:
                cls = f.read().strip().lower()
            if not cls.startswith("0x03"):
                continue
            with open(os.path.join(dev_path, "vendor")) as f:
                vid = f.read().strip().lower().replace("0x", "").zfill(4)[-4:]
            with open(os.path.join(dev_path, "device")) as f:
                did = f.read().strip().lower().replace("0x", "").zfill(4)[-4:]
            slot = os.path.basename(dev_path)
            # Human name: try modalias-adjacent product via lspci-less
            # lookup — use uevent DRIVER + PCI id as the display name
            # seed; detect_gpus() will resolve it via GPU_ID_MAP.
            name = ""
            for cand in ("label",):
                try:
                    with open(os.path.join(dev_path, cand)) as f:
                        name = f.read().strip()
                    if name:
                        break
                except OSError:
                    pass
            if not name:
                name = f"Display controller [{vid}:{did}]"
            lines.append(f"{slot} VGA compatible controller: {name} [{vid}:{did}]")
        except (OSError, ValueError):
            continue
    return lines


def _pci_devices() -> list[tuple[str, str, str]]:
    """
    Return:

        (vendor_id, device_id, OS_display_name)

    in OS discovery order.
    """
    devices: list[tuple[str, str, str]] = []


    # ── Windows ───────────────────────────────────────────────────────────

    if sys.platform == "win32":
        for item in _windows_gpu_records():
            pid = str(
                item.get(
                    "PNPDeviceID",
                    "",
                )
                or ""
            )

            match = re.search(
                r"VEN_([0-9A-Fa-f]{4}).*DEV_([0-9A-Fa-f]{4})",
                pid,
            )

            if not match:
                continue

            devices.append(
                (
                    match.group(1).lower(),
                    match.group(2).lower(),
                    str(
                        item.get(
                            "Name",
                            "",
                        )
                        or ""
                    ).strip(),
                )
            )

        return devices


    # ── Linux ─────────────────────────────────────────────────────────────

    for line in _linux_display_lines():
        match = re.search(
            r"\[([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\]",
            line,
        )

        if not match:
            continue

        name = line.split(
            ": ",
            1,
        )[-1]

        name = re.sub(
            r"\s*\[[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\]",
            "",
            name,
        ).strip()

        devices.append(
            (
                match.group(1).lower(),
                match.group(2).lower(),
                name,
            )
        )

    return devices


def _command_gpu_names() -> list[str]:
    """
    Best-effort command-line discovery for GPUs unknown to gpu_ids.py.

    Windows:
        PowerShell / Win32_VideoController

    Linux:
        lspci
        then nvidia-smi as a fallback
    """

    # ── Windows ───────────────────────────────────────────────────────────

    if sys.platform == "win32":
        names = []

        for item in _windows_gpu_records():
            name = str(
                item.get(
                    "Name",
                    "",
                )
                or ""
            ).strip()

            if name and name not in names:
                names.append(name)

        return names


    # ── Linux ─────────────────────────────────────────────────────────────

    names = []

    for line in _linux_display_lines():
        name = line.split(
            ": ",
            1,
        )[-1]

        name = re.sub(
            r"\s*\[[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\]",
            "",
            name,
        ).strip()

        if name and name not in names:
            names.append(name)

    if names:
        return names


    # NVIDIA fallback.
    return _command_lines(
        [
            "nvidia-smi",
            "--query-gpu=name",
            "--format=csv,noheader",
        ]
    )


def _gpu_name_from_os(
        pid: str,
) -> Optional[str]:
    """
    Ask the OS for the display name of a GPU with a PCI ID.
    """
    if not pid or ":" not in pid:
        return None

    vid, did = pid.split(
        ":",
        1,
    )


    # ── Windows ───────────────────────────────────────────────────────────

    if sys.platform == "win32":
        command = (
            "Get-CimInstance Win32_VideoController | "
            f"Where-Object {{ "
            f"$_ .PNPDeviceID -match "
            f"'VEN_{vid.upper()}.*DEV_{did.upper()}' "
            f"}} | "
            "Select-Object -ExpandProperty Name"
        )

        command = command.replace(
            "$_ .PNPDeviceID",
            "$_.PNPDeviceID",
        )

        lines = _command_lines(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                command,
            ]
        )

        return (
            lines[0]
            if lines
            else None
        )


    # ── Linux ─────────────────────────────────────────────────────────────

    for line in _linux_display_lines():
        if (
                f"[{vid}:{did}]"
                not in line.lower()
        ):
            continue

        name = line.split(
            ": ",
            1,
        )[-1]

        name = re.sub(
            r"\s*\[[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\]",
            "",
            name,
        ).strip()

        return name or None

    return None


def detect_gpus(data=None) -> list[str]:
    """
    Return all detected GPU names in the same order as the display devices.

    Pure OS/command discovery (no LHM, no driver):

        Windows PowerShell (Win32_VideoController)
        Linux lspci (+ sysfs fallback)
        NVIDIA nvidia-smi

    `data` is accepted for backward compatibility and ignored.
    """

    # ── OS/command discovery ─────────────────────────────────────────────

    devices = _pci_devices()

    if devices:
        result = []

        for vid, did, os_name in devices:
            pid = f"{vid}:{did}"

            if pid in AMBIGUOUS_IDS:
                name = (
                        _gpu_name_from_os(pid)
                        or os_name
                )
            else:
                name = (
                        GPU_ID_MAP.get(pid)
                        or os_name
                        or _gpu_name_from_os(pid)
                )

            result.append(
                name
                or f"Unknown GPU ({pid})"
            )

        return result


    return _command_gpu_names()


def _pci_id(
        index: int = 0,
) -> Optional[str]:
    """
    Return a PCI ID for the requested GPU index.

    Indexes other than zero preserve OS discovery order. Index zero keeps
    the old vendor-priority behaviour for compatibility with detect_gpu().
    """
    devices = _pci_devices()

    if not devices:
        return None


    if index != 0:
        if not (
                0 <= index < len(devices)
        ):
            return None

        return (
            f"{devices[index][0]}:"
            f"{devices[index][1]}"
        )


    ranked = [
        (
            _vendor_priority(
                vid,
                name,
            ),
            f"{vid}:{did}",
        )
        for vid, did, name in devices
    ]

    ranked.sort(
        key=lambda item: item[0]
    )

    return (
        ranked[0][1]
        if ranked
        else None
    )


def detect_gpu(
        index: int = 0,
) -> str:
    """
    Return one GPU name.

    index is zero-based.
    """
    names = detect_gpus()

    if 0 <= index < len(names):
        return names[index]


    pid = _pci_id(index)

    if pid:
        name = _gpu_name_from_os(pid)

        if name:
            return name

        if pid in GPU_ID_MAP:
            return GPU_ID_MAP[pid]

        return f"Unknown GPU ({pid})"


    return f"Unknown GPU ({index})"


def detect_vram_type(
        gpu_name: str,
) -> str:
    n = gpu_name.lower()

    if any(
            x in n
            for x in [
                "5090",
                "5080",
                "5070",
                "5060",
            ]
    ):
        return "GDDR7"

    if any(
            x in n
            for x in [
                "4090",
                "4080",
                "3090",
                "3080",
            ]
    ):
        return "GDDR6X"

    if any(
            x in n
            for x in [
                "1080 ti",
                "1080",
            ]
    ):
        return "GDDR5X"

    if any(
            x in n
            for x in [
                "1070",
                "1060",
                "1050",
                "1650",
                "1660",
                "980",
                "970",
                "960",
                "rx 580",
                "rx 570",
                "rx 480",
            ]
    ):
        return "GDDR5"

    if any(
            x in n
            for x in [
                "rx 9",
                "rx9",
                "rx 7",
                "rx7",
                "rx 6",
                "rx6",
                "rx 5",
                "rx5",
                "rtx",
            ]
    ):
        return "GDDR6"

    return "GDDR6"


# ── Native readers (no LHM, no driver) ───────────────────────────────────────

def get_gpu_temp(
        index: int = 0,
        data=None,
) -> int:
    """GPU temperature °C (0 = unknown/"N/A").

    Windows: nvidia-smi on NVIDIA; AMD/Intel have no inbox temp API,
    so they read 0 without a sensor driver. Linux: sysfs hwmon.
    """
    if sys.platform == "win32":
        return _nvidia_smi_stat("temp", index)
    return _linux_gpu_stat(
        "temp",
        index,
    )


def get_gpu_power(
        index: int = 0,
        data=None,
) -> int:
    """GPU board power W (0 = unknown/"N/A"). Same sources as temp."""
    if sys.platform == "win32":
        return _nvidia_smi_stat("power", index)
    return _linux_gpu_stat(
        "power",
        index,
    )


def _windows_gpu_load_perf(index: int = 0) -> int:
    """GPU load from Windows performance counters (no admin needed).

    Sums 3D-engine utilisation per physical adapter ("phys_N"); on
    single-GPU systems without phys tags the grand total is used for
    index 0. Sums can exceed 100 with several busy engines — clamped.
    """
    try:
        from hardware.win32 import gpu_engine_util
        per_phys, total = gpu_engine_util()
        if index in per_phys:
            return max(0, min(100, int(round(per_phys[index]))))
        if index == 0 and total > 0:
            return max(0, min(100, int(round(total))))
    except Exception:
        pass
    return 0


def get_gpu_load(
        index: int = 0,
        data=None,
) -> int:
    """GPU core load % (0 = idle or unknown).

    Windows: nvidia-smi on NVIDIA, else the inbox "\\GPU Engine"
    performance counters (works for AMD/Intel too, no admin needed).
    Linux: sysfs gpu_busy_percent / Intel freq ratio.
    """
    if sys.platform == "win32":
        v = _nvidia_smi_stat("load", index)
        if v > 0:
            return v
        return _windows_gpu_load_perf(index)
    return _linux_gpu_stat(
        "load",
        index,
    )


# ── Linux / command fallbacks ─────────────────────────────────────────────────

def _nvidia_smi_stat(
        kind: str,
        index: int,
) -> int:
    query = {
        "temp": "temperature.gpu",
        "power": "power.draw",
        "load": "utilization.gpu",
    }.get(kind)

    if not query:
        return 0

    rows = _command_lines(
        [
            "nvidia-smi",
            f"--query-gpu={query}",
            "--format=csv,noheader,nounits",
        ]
    )

    if not (
            0 <= index < len(rows)
    ):
        return 0

    try:
        cleaned = re.sub(
            r"[^0-9.+-]",
            "",
            rows[index],
        )

        return int(
            float(cleaned)
        )

    except ValueError:
        return 0


def _rocm_smi_stat(kind: str, index: int = 0) -> int:
    """AMD rocm-smi fallback (covers AMD GPUs where sysfs hwmon is
    unreadable due to permissions). Best-effort, returns 0."""
    query = {
        "temp": ["--showtemp", r"(\d+\.?\d*)\s*c"],
        "load": ["--showuse", r"(\d+)\s*%"],
        "power": ["--showpower", r"(\d+\.?\d*)\s*W"],
    }.get(kind)
    if not query:
        return 0
    rows = _command_lines(["rocm-smi", query[0]])
    if not (0 <= index < len(rows) or rows):
        return 0
    # rocm-smi prints per-GPU lines; pick index-th matching line.
    found: list[float] = []
    for line in rows:
        m = re.search(query[1], line, flags=re.IGNORECASE)
        if m:
            try:
                found.append(float(m.group(1)))
            except ValueError:
                pass
    if 0 <= index < len(found):
        return int(found[index])
    if found and index == 0:
        return int(found[0])
    return 0


def _intel_freq_load(card: str) -> int:
    """Intel iGPU load estimate from GT freq (0-100).

    Intel exposes no gpu_busy_percent; actual/max freq ratio is a
    rough but useful proxy and only needs sysfs reads."""
    try:
        cur = int(open(f"{card}/gt_cur_freq_mhz").read().strip())
        mx = int(open(f"{card}/gt_max_freq_mhz").read().strip())
        if mx > 0 and cur >= 0:
            return max(0, min(100, int(round(cur * 100.0 / mx))))
    except (OSError, ValueError):
        pass
    # Newer kernels: gt0/gt1 sub-nodes
    import glob as _glob
    for freq in sorted(_glob.glob(f"{card}/gt*/cur_freq_mhz")):
        try:
            cur = int(open(freq).read().strip())
            mxf = freq.replace("cur_freq_mhz", "max_freq_mhz")
            mx = int(open(mxf).read().strip())
            if mx > 0 and cur >= 0:
                return max(0, min(100, int(round(cur * 100.0 / mx))))
        except (OSError, ValueError):
            continue
    return 0


def _drm_cards_ordered() -> list[str]:
    """DRM card device paths ordered to match _pci_devices() order when
    possible (so GPU index 0 = first lspci GPU), else sysfs sort order.

    Matches via PCI slot (uevent PCI_SLOT_NAME) against the lspci
    domain:bus:device.function prefix.
    """
    import glob as _glob
    import os as _os
    cards = sorted(_glob.glob("/sys/class/drm/card*/device"))
    if len(cards) <= 1:
        return cards
    try:
        pci_order = [ln.split(" ")[0].lower() for ln in _linux_display_lines()]
    except Exception:
        return cards
    if not pci_order:
        return cards

    def _slot_of(card: str) -> str:
        for key in ("uevent",):
            try:
                with open(_os.path.join(card, key)) as f:
                    for line in f:
                        if line.startswith("PCI_SLOT_NAME="):
                            return line.split("=", 1)[1].strip().lower()
            except OSError:
                pass
        return ""

    ranked: list[tuple[int, str]] = []
    for card in cards:
        slot = _slot_of(card)
        # lspci lines look like "0000:03:00.0 ..."; slot is "0000:03:00.0".
        rank = len(pci_order)
        for i, prefix in enumerate(pci_order):
            if slot and slot == prefix:
                rank = i
                break
        ranked.append((rank, card))
    ranked.sort(key=lambda t: t[0])
    return [c for _, c in ranked]


def _hwmon_temp_c(hwmon: str) -> int | None:
    """Best temp from one hwmon dir: prefer edge/junction/package/core
    labels, else hottest tempN_input. Returns None if unreadable."""
    import glob as _glob
    best: tuple[int, int] | None = None  # (score, celsius)
    for temp_file in sorted(_glob.glob(f"{hwmon}/temp*_input")):
        try:
            raw = open(temp_file).read().strip()
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
        try:
            label = open(temp_file.replace("_input", "_label")).read().strip().lower()
        except (OSError, ValueError):
            label = ""
        if any(k in label for k in ("edge", "junction", "package", "core", "gpu", "hotspot", "tdie", "tctl")):
            score = 0
        elif "mem" in label or "vram" in label or "hbm" in label:
            score = 2  # memory temp — only if nothing better
        else:
            score = 1
        if best is None or (score, celsius) < (best[0], 0) or (score == best[0] and celsius > best[1]):
            if best is None or score < best[0] or (score == best[0] and celsius > best[1]):
                best = (score, celsius)
    return best[1] if best else None


def _hwmon_power_w(hwmon: str) -> int | None:
    """Best power from one hwmon dir. sysfs reports µW; some drivers
    report mW or W on exotic hw — sanity-clamp to 0-1200 W."""
    for power_file in ("power1_average", "power1_input",
                       "power2_average", "power2_input"):
        try:
            raw = open(f"{hwmon}/{power_file}").read().strip()
            if not raw:
                continue
            val = int(raw)
            if val <= 0:
                continue
            # Heuristic unit detect: sysfs standard is µW (>= 1_000_000
            # for a 1 W+ GPU). Values < 5000 are likely already Watts.
            if val >= 100000:
                watts = val / 1_000_000.0
            elif val >= 5000:
                watts = val / 1000.0  # mW driver quirk
            else:
                watts = float(val)
            if 0 < watts < 1200:
                return int(round(watts))
        except (OSError, ValueError):
            continue
    return None


def _linux_gpu_stat(
        kind: str,
        index: int = 0,
) -> int:
    import glob

    cards = _drm_cards_ordered()

    # Also check class-level hwmon (some NVIDIA/Intel setups expose the
    # GPU sensor at /sys/class/hwmon/hwmonN with no drm link).
    class_hwmons = sorted(glob.glob("/sys/class/hwmon/hwmon*"))

    if 0 <= index < len(cards):
        card = cards[index]

        if kind == "temp":
            scored: list[tuple[int, int]] = []
            for hwmon in glob.glob(f"{card}/hwmon/hwmon*"):
                v = _hwmon_temp_c(hwmon)
                if v is not None:
                    scored.append((0, v))
            # Fallback: class-level hwmon matching this card's vendor?
            if not scored and len(cards) == 1 and class_hwmons:
                for hwmon in class_hwmons:
                    try:
                        nm = open(f"{hwmon}/name").read().strip().lower()
                    except (OSError, ValueError):
                        continue
                    if any(k in nm for k in ("amdgpu", "nvidia", "i915", "xe", "nouveau")):
                        v = _hwmon_temp_c(hwmon)
                        if v is not None:
                            scored.append((1, v))
            if scored:
                scored.sort()
                return scored[0][1]

        elif kind == "power":
            for hwmon in glob.glob(f"{card}/hwmon/hwmon*"):
                v = _hwmon_power_w(hwmon)
                if v is not None:
                    return v

        elif kind == "load":
            try:
                return max(0, min(100, int(
                    open(f"{card}/gpu_busy_percent").read().strip()
                )))
            except (OSError, ValueError):
                pass
            intel = _intel_freq_load(card)
            if intel:
                return intel

    # ── CLI fallbacks (no sysfs match or index out of range) ──────────
    v = _nvidia_smi_stat(kind, index)
    if v:
        return v
    return _rocm_smi_stat(kind, index)