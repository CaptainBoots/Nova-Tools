"""
Actions/send_osc_action.py
───────────────────────────────────
Action module: sends an OSC message anywhere. Host and port live on
the action itself — every send_osc action is fully self-contained,
there's no shared "default out" to fall back to. The value can be a
fixed static value, the incoming trigger value forwarded as-is, or a
linear transform/remap of the trigger value (with optional invert /
bool threshold) — handy for turning one avatar parameter's range into
another's, or into a driving OSC signal for a different app.
"""

from core.conditions import cast_value, remap

ID = "send_osc"
LABEL = "Send OSC Message"
CATEGORY = "OSC"
DESCRIPTION = "Sends an OSC message to a host/port you set here — static value, forwarded, or remapped."


def run(action, ctx):
    host = (action.host or "127.0.0.1").strip()
    try:
        port = int(action.port or 9000)
    except (TypeError, ValueError):
        port = 9000
    value = _resolve_value(action, ctx.trigger_value)
    ctx.senders.send(host, port, action.address, value)


def _resolve_value(action, trigger_value):
    if action.value_mode == "forward":
        return cast_value(trigger_value)

    if action.value_mode == "transform":
        val = remap(trigger_value, action.in_min, action.in_max,
                    action.out_min, action.out_max, action.invert)
        if action.as_bool:
            mid = (float(action.out_min) + float(action.out_max)) / 2.0
            return bool(val >= mid)
        return val

    return cast_value(action.static_value)