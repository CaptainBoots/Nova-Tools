"""
osc_loop.py
───────────
Background OSC loop that runs on a daemon thread.

  start_loop(cfg, state, status_cb, preview_cb)
  stop_loop()

All mutable state lives in AppState (state.py).
Page layout is read from cfg["pages"] each tick so live edits take effect.
"""

import asyncio
import threading
import time
from typing import Callable, Optional

import psutil
from pythonosc.udp_client import SimpleUDPClient

import hardware.lhm as lhm_mod

from hardware.cpu import (
    detect_cpu,
    get_cpu_temp,
    get_cpu_power,
    get_cpu_load,
)

from hardware.gpu import (
    detect_gpus,
    detect_gpu,
    detect_vram_type,
    get_gpu_temp,
    get_gpu_power,
    get_gpu_load,
)

from hardware.lhm import get_lhm_data

from hardware.memory import (
    detect_dram_type,
    get_dram_used,
    get_dram_total,
    get_vram_used,
    get_vram_total,
)

from core.registry import render_page

from monitors import media as media_mod
from monitors.media import (
    clean_title,
    clean_value,
    estimate_position,
)

from monitors.network import sample as net_sample
from monitors.weather import fetch as weather_fetch

from monitors import steamvr, vrchat
from monitors import channels

from core import fake_data as fake

from core.state import (
    AppState,
    CHATBOX_MAX_CHARS,
)


# ── Polling intervals ─────────────────────────────────────────────────────────

_LHM_INTERVAL     = 1.0
_WEATHER_INTERVAL = 300
_MEDIA_INTERVAL   = 1.0


_loop_thread: Optional[threading.Thread] = None


def start_loop(
        cfg: dict,
        state: AppState,
        status_cb: Callable[[str], None],
        preview_cb: Callable[[str], None],
):
    global _loop_thread

    state.running = True

    _loop_thread = threading.Thread(
        target=_run,
        args=(
            cfg,
            state,
            status_cb,
            preview_cb,
        ),
        daemon=True,
    )

    _loop_thread.start()


def stop_loop(state: AppState):
    state.running = False


def _run(
        cfg,
        state: AppState,
        status_cb,
        preview_cb,
):
    # ── Validate interface ────────────────────────────────────────────────────

    interface = cfg.get(
        "interface",
        "Ethernet",
    )

    all_stats = psutil.net_io_counters(
        pernic=True
    )

    if not state.fake_data and interface not in all_stats:
        status_cb(
            f"Error: interface '{interface}' not found"
        )

        state.running = False

        return


    # ── Set LHM URL from config ───────────────────────────────────────────────

    lhm_mod.LHM_URL = cfg.get(
        "lhm_api",
        "http://localhost:8085/data.json",
    )


    # ── One-time hardware detection ───────────────────────────────────────────
    #
    # Fake Data Mode (Dev Menu) is only read here at Start time — CPU/GPU
    # *names* lock in for the life of this loop run either way, same as
    # real detection normally would. Toggling the flag later still updates
    # every per-tick reading (temps/load/power/VRAM/media/VR/VRChat/weather/
    # network) live, every loop iteration re-checks it — just Stop/Start
    # again if you also want fake names.

    if state.fake_data:
        state.cpu_name = fake.cpu_name()
    else:
        state.cpu_name = detect_cpu(
            testing=getattr(
                state,
                "testing",
                False,
            )
        )

    state.dram_type = fake.dram_type() if state.fake_data else detect_dram_type()


    # Get LHM before building the GPU list.
    #
    # On Windows, this means the GPU names can use the same GPU-node order
    # that the sensor readers use. If LHM does not contain GPU nodes,
    # detect_gpus() falls back to PowerShell/lspci/nvidia-smi.

    init_lhm = None if state.fake_data else get_lhm_data()

    gpu_names = fake.gpu_names() if state.fake_data else detect_gpus(
        init_lhm
    )


    if not gpu_names:
        gpu_names = [
            detect_gpu(0)
        ]


    # Build one telemetry dictionary per GPU.

    state.gpus = []

    for index, name in enumerate(
            gpu_names
    ):
        state.gpus.append(
            {
                "name": name,

                "load": 0,
                "temp": 0,
                "power": 0,

                "vram_type": (
                    fake.vram_type(name)
                    if state.fake_data
                    else detect_vram_type(name)
                ),

                "vram_used": 0.0,

                "vram_total": (
                    fake.vram_total(index)
                    if state.fake_data
                    else get_vram_total(init_lhm, index)
                ),
            }
        )


    # Keep the original single-GPU state fields working.
    # They represent GPU 0.

    if state.gpus:
        state.gpu_name = state.gpus[0][
            "name"
        ]

        state.vram_type = state.gpus[0][
            "vram_type"
        ]

        state.vram_total = state.gpus[0][
            "vram_total"
        ]

    else:
        state.gpu_name = "Unknown GPU"
        state.vram_type = "GDDR"
        state.vram_total = "?"


    state.dram_total = fake.dram_total() if state.fake_data else get_dram_total(
        init_lhm
    )


    print(
        "CPU: "
        f"{state.cpu_name}  "
        "GPUs: "
        f"{', '.join(g['name'] for g in state.gpus) or 'Unknown GPU'}"
    )

    print(
        f"RAM: {state.dram_total}GB  "
        f"VRAM: {state.vram_total}GB"
    )


    # ── LHM background poller ─────────────────────────────────────────────────

    lhm_cache = {
        "data": init_lhm,
        "lock": threading.Lock(),
    }


    def _poll_lhm():
        while state.running:
            if not state.fake_data:
                data = get_lhm_data()

                if data:
                    with lhm_cache["lock"]:
                        lhm_cache["data"] = data

            time.sleep(
                _LHM_INTERVAL
            )


    threading.Thread(
        target=_poll_lhm,
        daemon=True,
    ).start()


    # ── Media background poller ───────────────────────────────────────────────

    media_cache = {
        "info": media_mod.empty(),
        "lock": threading.Lock(),
    }


    def _poll_media():
        async def _loop():
            while state.running:
                info = await (
                    fake.media_fetch()
                    if state.fake_data
                    else media_mod.fetch()
                )

                with media_cache["lock"]:
                    media_cache["info"] = (
                        info
                        if isinstance(info, dict)
                        else media_mod.empty()
                    )

                await asyncio.sleep(
                    _MEDIA_INTERVAL
                )

        asyncio.run(_loop())


    threading.Thread(
        target=_poll_media,
        daemon=True,
    ).start()


    # ── OSC client ────────────────────────────────────────────────────────────

    client = SimpleUDPClient(
        cfg.get(
            "osc_ip",
            "127.0.0.1",
        ),
        int(
            cfg.get(
                "osc_port",
                9000,
            )
        ),
    )


    # ── Network baseline ──────────────────────────────────────────────────────

    prev_net = all_stats.get(interface)
    prev_time = time.time()


    # ── Weather ───────────────────────────────────────────────────────────────

    def _do_weather():
        loc = cfg.get("location", "0,0")
        t, h, d = fake.weather_fetch(loc) if state.fake_data else weather_fetch(loc)

        state.update_weather(
            t,
            h,
            d,
        )


    _do_weather()

    last_weather = time.time()


    # ── Page rotation state ───────────────────────────────────────────────────

    page_index = 0
    page_start_time = time.time()

    media_pos_state: dict = {}


    status_cb("Running")


    # ── Main loop ─────────────────────────────────────────────────────────────

    while state.running:
        try:
            now = time.time()


            # ── Sleep mode ────────────────────────────────────────────────────

            if state.slow_mode:
                sleep = 5.0

            elif state.speed_mode:
                sleep = 0.1

            else:
                sleep = 1.0

            state.sleep_delay = sleep


            # ── Hardware sensors ──────────────────────────────────────────────

            with lhm_cache["lock"]:
                lhm_data = lhm_cache["data"]


            if state.fake_data or lhm_data:

                # Read every GPU independently.
                #
                # This is the important part that makes the UI's GPU index
                # actually control which GPU supplies the stats.

                gpu_stats = []

                for index, gpu in enumerate(
                        state.gpus
                ):
                    gpu_copy = dict(gpu)

                    if state.fake_data:
                        gpu_copy["load"]  = fake.gpu_load(index)
                        gpu_copy["temp"]  = fake.gpu_temp(index)
                        gpu_copy["power"] = fake.gpu_power(index)
                        gpu_copy["vram_used"] = fake.vram_used(index)
                    else:
                        gpu_copy["load"] = get_gpu_load(
                            lhm_data,
                            index,
                        )

                        gpu_copy["temp"] = get_gpu_temp(
                            lhm_data,
                            index,
                        )

                        gpu_copy["power"] = get_gpu_power(
                            lhm_data,
                            index,
                        )

                        gpu_copy["vram_used"] = get_vram_used(
                            lhm_data,
                            index,
                        )


                    if (
                            gpu_copy.get(
                                "vram_total",
                                "?",
                            )
                            == "?"
                    ):
                        gpu_copy["vram_total"] = (
                            fake.vram_total(index)
                            if state.fake_data
                            else get_vram_total(lhm_data, index)
                        )


                    gpu_stats.append(
                        gpu_copy
                    )


                # Keep the old single-GPU fields synchronized with GPU 0.
                # Existing modules/code using those fields therefore continue
                # to work.

                state.update_hardware(
                    cpu_temp=(
                        fake.cpu_temp() if state.fake_data
                        else get_cpu_temp(lhm_data)
                    ),

                    cpu_power=(
                        fake.cpu_power() if state.fake_data
                        else get_cpu_power(lhm_data)
                    ),

                    cpu_load=(
                        fake.cpu_load() if state.fake_data
                        else get_cpu_load(lhm_data)
                    ),

                    gpu_temp=(
                        gpu_stats[0]["temp"]
                        if gpu_stats
                        else 0
                    ),

                    gpu_power=(
                        gpu_stats[0]["power"]
                        if gpu_stats
                        else 0
                    ),

                    gpu_load=(
                        gpu_stats[0]["load"]
                        if gpu_stats
                        else 0
                    ),

                    gpus=gpu_stats,

                    dram_used=(
                        fake.dram_used() if state.fake_data
                        else get_dram_used(lhm_data)
                    ),

                    vram_used=(
                        gpu_stats[0]["vram_used"]
                        if gpu_stats
                        else 0.0
                    ),
                )


                # Retry VRAM totals if they were unavailable at startup.

                if gpu_stats:
                    state.vram_total = gpu_stats[0].get(
                        "vram_total",
                        state.vram_total,
                    )


                if state.dram_total == "?":
                    state.dram_total = (
                        fake.dram_total() if state.fake_data
                        else get_dram_total(lhm_data)
                    )


            # ── Network ───────────────────────────────────────────────────────

            (
                prev_net,
                up,
                down,
                prev_time,
            ) = (fake.network_sample if state.fake_data else net_sample)(
                prev_net,
                prev_time,
                interface,
            )

            state.update_network(
                up,
                down,
            )


            # ── Weather ───────────────────────────────────────────────────────

            if (
                    now - last_weather
                    >= _WEATHER_INTERVAL
            ):
                _do_weather()
                last_weather = now


            # ── Media snapshot ────────────────────────────────────────────────

            with media_cache["lock"]:
                media_info = dict(
                    media_cache["info"]
                )


            estimate_position(
                media_info,
                media_pos_state,
                now,
            )

            state.update_media(
                media_info
            )


            # ── Build snap dict ───────────────────────────────────────────────

            snap = state.snapshot()

            snap["media_info"] = media_info


            # Merge SteamVR and VRChat monitor data.

            snap.update(
                fake.steamvr_snapshot() if state.fake_data else steamvr.snapshot()
            )

            snap.update(
                fake.vrchat_snapshot() if state.fake_data else vrchat.snapshot()
            )

            snap.update(
                fake.channels_snapshot() if state.fake_data else channels.snapshot()
            )


            # Pre-build media title.

            raw_title = clean_value(
                media_info.get(
                    "title"
                )
            )

            snap["media_title_clean"] = (
                clean_title(raw_title)
                if state.media_title_trim
                else raw_title
            )

            # Pre-build media progress bar string[cite: 3]
            snap["progress_bar_str"] = media_mod.progress_bar(
                pos_ms=media_info.get("position_ms", 0),
                dur_ms=media_info.get("duration_ms", 0),
                filled="█",
                border="▒",
                empty="░",
                length=15
            )

            # Pre-build media time string[cite: 3]
            snap["media_time_str"] = media_mod.fmt_time(
                media_info.get("position_ms", 0),
                media_info.get("duration_ms", 0)
            )


            # ── Forced text override ──────────────────────────────────────────

            forced = snap.get(
                "forced_text",
                "",
            ).strip()


            if forced:
                text = forced

            else:

                # ── Page rotation ─────────────────────────────────────────────

                pages = cfg.get(
                    "pages",
                    [],
                )

                enabled = [
                    p
                    for p in pages
                    if p.get(
                        "enabled",
                        True,
                    )
                ]


                if not enabled:
                    text = "No pages enabled"

                else:
                    current_page = enabled[
                        page_index % len(enabled)
                        ]

                    duration = float(
                        current_page.get(
                            "duration",
                            cfg.get(
                                "switch_interval",
                                20,
                            ),
                        )
                    )


                    if (
                            now - page_start_time
                            >= duration
                    ):
                        page_index = (
                                             page_index + 1
                                     ) % len(enabled)

                        page_start_time = now

                        current_page = enabled[
                            page_index % len(enabled)
                            ]


                    text = render_page(
                        current_page,
                        snap,
                    )


            text = text[
                :CHATBOX_MAX_CHARS
            ]

            preview_cb(text)

            client.send_message(
                "/chatbox/input",
                [
                    text,
                    True,
                ],
            )

            print(text)


        except Exception as e:
            print(
                f"[OSC] Error: {e}"
            )


        time.sleep(
            state.sleep_delay
        )


    status_cb("Stopped")