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
from hardware.lhm import hw_nodes, is_gpu, numeric


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
    """
    return [
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

    When LHM data is supplied, its GPU-node order is preferred because the
    Windows sensor readers use that same node list. This keeps names and
    sensor indexes aligned.

    If LHM does not provide GPU nodes, detection falls back to:

        Windows PowerShell
        Linux lspci
        NVIDIA nvidia-smi
    """

    # ── Prefer LHM GPU node ordering ──────────────────────────────────────

    if data:
        names = []

        try:
            for hw in hw_nodes(data):
                if is_gpu(
                        hw.get(
                            "Text",
                            "",
                        )
                ):
                    text = str(
                        hw.get(
                            "Text",
                            "",
                        )
                    ).strip()

                    if text:
                        names.append(text)

        except Exception:
            names = []

        if names:
            return names


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


# ── LHM readers ───────────────────────────────────────────────────────────────

def _gpu_nodes(data) -> list[dict]:
    try:
        return [
            hw
            for hw in hw_nodes(data)
            if is_gpu(
                hw.get(
                    "Text",
                    "",
                )
            )
        ]
    except Exception:
        return []


def _selected_gpu_nodes(
        data,
        index: int,
) -> list[dict]:
    nodes = _gpu_nodes(data)

    if 0 <= index < len(nodes):
        return [nodes[index]]

    return []


def get_gpu_temp(
        data,
        index: int = 0,
) -> int:
    if sys.platform != "win32":
        return _linux_gpu_stat(
            "temp",
            index,
        )

    try:
        for hw in _selected_gpu_nodes(
                data,
                index,
        ):
            for cat in hw.get(
                    "Children",
                    [],
            ):
                if (
                        "temperature"
                        not in cat.get(
                    "Text",
                    "",
                ).lower()
                ):
                    continue

                for sensor in cat.get(
                        "Children",
                        [],
                ):
                    st = sensor.get(
                        "Text",
                        "",
                    ).lower()

                    if (
                            "distance" in st
                            or "memory" in st
                    ):
                        continue

                    if (
                            "gpu core" in st
                            or "gpu temperature" in st
                    ):
                        try:
                            return int(
                                numeric(
                                    sensor.get(
                                        "Value",
                                        0,
                                    )
                                )
                            )
                        except ValueError:
                            pass

    except Exception:
        pass

    return 0


def get_gpu_power(
        data,
        index: int = 0,
) -> int:
    if sys.platform != "win32":
        return _linux_gpu_stat(
            "power",
            index,
        )

    try:
        for hw in _selected_gpu_nodes(
                data,
                index,
        ):
            for cat in hw.get(
                    "Children",
                    [],
            ):
                if (
                        "power"
                        not in cat.get(
                    "Text",
                    "",
                ).lower()
                ):
                    continue

                for sensor in cat.get(
                        "Children",
                        [],
                ):
                    st = sensor.get(
                        "Text",
                        "",
                    ).lower()

                    if any(
                            x in st
                            for x in (
                                    "gpu package",
                                    "gpu total",
                                    "board power",
                                    "gpu power",
                                    "power",
                            )
                    ):
                        try:
                            val = numeric(
                                sensor.get(
                                    "Value",
                                    0,
                                )
                            )
                            if val > 0:
                                return int(val)
                        except ValueError:
                            pass

    except Exception:
        pass

    return _nvidia_smi_stat("power", index)


def get_gpu_load(
        data,
        index: int = 0,
) -> int:
    if sys.platform != "win32":
        return _linux_gpu_stat(
            "load",
            index,
        )

    try:
        for hw in _selected_gpu_nodes(
                data,
                index,
        ):
            for cat in hw.get(
                    "Children",
                    [],
            ):
                if (
                        "load"
                        not in cat.get(
                    "Text",
                    "",
                ).lower()
                ):
                    continue

                for sensor in cat.get(
                        "Children",
                        [],
                ):
                    if (
                            "gpu core"
                            in sensor.get(
                        "Text",
                        "",
                    ).lower()
                    ):
                        try:
                            return int(
                                numeric(
                                    sensor.get(
                                        "Value",
                                        0,
                                    )
                                )
                            )
                        except ValueError:
                            pass

    except Exception:
        pass

    return 0


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


def _linux_gpu_stat(
        kind: str,
        index: int = 0,
) -> int:
    import glob

    cards = sorted(
        glob.glob(
            "/sys/class/drm/card*/device"
        )
    )


    if 0 <= index < len(cards):
        card = cards[index]


        if kind == "temp":
            for hwmon in glob.glob(
                    f"{card}/hwmon/hwmon*"
            ):
                try:
                    return (
                            int(
                                open(
                                    f"{hwmon}/temp1_input"
                                ).read().strip()
                            )
                            // 1000
                    )

                except (
                        OSError,
                        ValueError,
                ):
                    pass


        elif kind == "power":
            for hwmon in glob.glob(
                    f"{card}/hwmon/hwmon*"
            ):
                for power_file in (
                        "power1_average",
                        "power1_input",
                ):
                    try:
                        return (
                                int(
                                    open(
                                        f"{hwmon}/{power_file}"
                                    ).read().strip()
                                )
                                // 1_000_000
                        )

                    except (
                            OSError,
                            ValueError,
                    ):
                        pass


        elif kind == "load":
            try:
                return int(
                    open(
                        f"{card}/gpu_busy_percent"
                    ).read().strip()
                )

            except (
                    OSError,
                    ValueError,
            ):
                pass


    return _nvidia_smi_stat(
        kind,
        index,
    )