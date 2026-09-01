"""
core/Inputs/timer_input.py
────────────────────────────
Trigger module: fires repeatedly every N seconds. Doesn't need a
`matches()` — the engine's timer loop drives it directly — but exposes
`next_interval()` so the interval-parsing logic lives with the module
like every other input kind.
"""

ID = "timer"
LABEL = "Timer / Interval"
CATEGORY = "Logic"
DESCRIPTION = "Fires repeatedly on a fixed interval, independent of any OSC traffic."


def next_interval(trigger) -> float:
    try:
        seconds = float(trigger.interval_s or 1.0)
    except (TypeError, ValueError):
        seconds = 1.0
    return max(seconds, 0.1)