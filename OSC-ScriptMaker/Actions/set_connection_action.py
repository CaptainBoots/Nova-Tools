"""
core/Actions/set_connection_action.py
─────────────────────────────────────────
Action module: changes the Listen (incoming) or Send (outgoing) host
and/or port at runtime — the same fields shown in the Scripts tab's
connection bar. Leaving host or port blank keeps that part unchanged.

Changing Listen restarts the OSC listener on the new address; changing
Send just updates the default outgoing host/port that send_osc/chatbox
actions fall back to when they don't specify their own override.
"""

ID = "set_connection"
LABEL = "Set Connection"
CATEGORY = "System"
DESCRIPTION = "Changes the Listen or Send host/port at runtime. Blank = keep current value."


def run(action, ctx):
    host = (action.host or "").strip()
    port = (action.port or "").strip()
    if action.conn_target == "listen":
        ctx.set_listen(host, port)
    else:
        ctx.set_send(host, port)
