"""monitors/network.py — network throughput sampling."""

import time

import psutil


def fmt_net(bps: float) -> str:
    bits = max(0, bps) * 8
    if bits >= 1_000_000:
        return f"{bits/1_000_000:.2f} Mb/s"
    return f"{bits/1_000:.1f} Kb/s"


def sample(prev, prev_time: float, interface: str):
    """
    Returns (cur_counters, up_bps, down_bps, now).
    Falls back to (prev, 0, 0, now) if interface missing.
    """
    now = time.time()
    try:
        cur     = psutil.net_io_counters(pernic=True)[interface]
        elapsed = now - prev_time
        if elapsed > 0:
            up   = (cur.bytes_sent - prev.bytes_sent) / elapsed
            down = (cur.bytes_recv - prev.bytes_recv) / elapsed
        else:
            up = down = 0.0
        return cur, up, down, now
    except (KeyError, ZeroDivisionError):
        return prev, 0.0, 0.0, now
