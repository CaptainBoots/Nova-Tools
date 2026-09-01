"""
core/Inputs/osc_input.py
─────────────────────────
Trigger module: fires when an incoming OSC message's address matches
the script's configured address (exact match, or a trailing "*"
wildcard prefix match, e.g. "/avatar/parameters/*").

The actual any/equals/greater/.../rising_edge condition check against
the message's value is shared logic (core/conditions.py) — this module
only answers "is this event even for this trigger at all?".
"""

ID = "osc"
LABEL = "OSC Message"
CATEGORY = "OSC"
DESCRIPTION = "Fires when a matching OSC address is received, e.g. /avatar/parameters/MyParam"


def matches(trigger, address: str, value) -> bool:
    pattern = (trigger.address or "").strip()
    if not pattern:
        return False
    if pattern == address:
        return True
    if pattern.endswith("*"):
        return address.startswith(pattern[:-1])
    return False