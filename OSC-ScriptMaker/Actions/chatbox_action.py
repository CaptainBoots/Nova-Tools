"""
Actions/chatbox_action.py
──────────────────────────────────
Action module: sends text either to the real VRChat chatbox
(/chatbox/input on whatever host:port you set — normally VRChat's OSC
in on 127.0.0.1:9000), or to one of 10 custom "channels" — a private
broadcast bus for routing text between your own tools/scripts without
touching VRChat's OSC traffic at all. Each channel is a fixed port far
away from VRChat's own range and any other tool in this suite, so
picking a channel can never collide with something else listening.

Both modes send the same message shape ([text, send_immediately,
play_sfx] to /chatbox/input) — a channel is just "the same kind of
message, delivered somewhere private instead."

"{value}" in the text is replaced with the trigger's value, so e.g.
a script watching a float parameter can chatbox its live value.
"""

ID = "chatbox"
LABEL = "Chatbox Message"
CATEGORY = "OSC"
DESCRIPTION = "Sends text to the real VRChat chatbox, or to a private channel for your own tools."

# 10 channels, each pinned to its own port, deliberately far from
# VRChat's own OSC ports (9000/9001) and every other port this suite
# uses by default, so a channel can never collide with real traffic.
CHATBOX_CHANNELS = {n: 9600 + (n - 1) for n in range(1, 11)}  # 9600–9609


def run(action, ctx):
    host = (action.host or "127.0.0.1").strip()

    if action.chatbox_target == "channel":
        channel = action.chatbox_channel if action.chatbox_channel in CHATBOX_CHANNELS else 1
        port = CHATBOX_CHANNELS[channel]
    else:
        try:
            port = int(action.port or 9000)
        except (TypeError, ValueError):
            port = 9000

    text = (action.text or "").replace("{value}", str(ctx.trigger_value))
    client = ctx.senders.get(host, port)
    client.send_message("/chatbox/input", [text, bool(action.send_immediately), bool(action.play_sfx)])