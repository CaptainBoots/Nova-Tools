"""
core/Actions/set_variable_action.py
───────────────────────────────────────
Action module: writes a script-maker variable, either a static value
or the current trigger value forwarded through. Any script with a
"Variable Changed" trigger on the same name will fire as a result —
this is the mechanism scripts use to chain off each other.
"""

from core.conditions import cast_value

ID = "set_variable"
LABEL = "Set Variable"
CATEGORY = "Logic"
DESCRIPTION = "Sets a script-maker variable — other scripts can trigger off it changing."


def run(action, ctx):
    if not action.var_name:
        return
    value = ctx.trigger_value if action.var_value_mode == "forward" else cast_value(action.var_static_value)
    ctx.set_variable(action.var_name, value)