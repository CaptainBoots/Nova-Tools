"""
core/Inputs/variable_input.py
────────────────────────────────
Trigger module: fires when a script-maker "variable" (set by another
script's Set Variable action) changes. This is how scripts chain to
each other without needing a real OSC round-trip.
"""

ID = "variable"
LABEL = "Variable Changed"
CATEGORY = "Logic"
DESCRIPTION = "Fires when a script-maker variable is updated by a Set Variable action."


def matches(trigger, var_name: str, value) -> bool:
    name = (trigger.var_name or "").strip()
    return bool(name) and name == var_name