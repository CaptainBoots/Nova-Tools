"""
core/registry.py
──────────────────
The one place that lists every trigger (Inputs/) and action (Actions/)
module. Each kind still lives in its own small file under the
top-level Actions/ or Inputs/ folder — this file just aggregates them,
so the engine and the UI's dropdowns both read from here instead of
hardcoding kinds anywhere else.

Adding a new action kind:
  1. Write Actions/my_thing_action.py with ID / LABEL / CATEGORY /
     DESCRIPTION, plus a run(action, ctx) function (ctx is an
     ActionContext — see Actions/context.py).
  2. Add it to the ACTIONS list below.

Adding a new trigger kind:
  1. Write Inputs/my_thing_input.py with ID / LABEL / CATEGORY /
     DESCRIPTION, plus a matches(trigger, key, value) -> bool function
     (or next_interval() for a timer-style kind that doesn't need one).
  2. Add it to the INPUTS list below.

Nothing else needs changing in the engine or UI for either.
"""

from Actions import (
    chatbox_action,
    keybind_action,
    play_sound_action,
    random_action,
    run_program_action,
    send_osc_action,
    set_variable_action,
    wait_action,
)
from Actions.context import ActionContext
from Inputs import osc_input, timer_input, variable_input

# ── Actions ──────────────────────────────────────────────────────────────

ACTIONS = [
    {"id": keybind_action.ID, "label": keybind_action.LABEL, "category": keybind_action.CATEGORY,
     "description": keybind_action.DESCRIPTION, "module": keybind_action},
    {"id": send_osc_action.ID, "label": send_osc_action.LABEL, "category": send_osc_action.CATEGORY,
     "description": send_osc_action.DESCRIPTION, "module": send_osc_action},
    {"id": chatbox_action.ID, "label": chatbox_action.LABEL, "category": chatbox_action.CATEGORY,
     "description": chatbox_action.DESCRIPTION, "module": chatbox_action},
    {"id": run_program_action.ID, "label": run_program_action.LABEL, "category": run_program_action.CATEGORY,
     "description": run_program_action.DESCRIPTION, "module": run_program_action},
    {"id": wait_action.ID, "label": wait_action.LABEL, "category": wait_action.CATEGORY,
     "description": wait_action.DESCRIPTION, "module": wait_action},
    {"id": set_variable_action.ID, "label": set_variable_action.LABEL, "category": set_variable_action.CATEGORY,
     "description": set_variable_action.DESCRIPTION, "module": set_variable_action},
    {"id": play_sound_action.ID, "label": play_sound_action.LABEL, "category": play_sound_action.CATEGORY,
     "description": play_sound_action.DESCRIPTION, "module": play_sound_action},
    {"id": random_action.ID, "label": random_action.LABEL, "category": random_action.CATEGORY,
     "description": random_action.DESCRIPTION, "module": random_action},
]

ACTION_BY_ID: dict = {a["id"]: a for a in ACTIONS}

ACTION_CATEGORIES: dict = {}
for _a in ACTIONS:
    ACTION_CATEGORIES.setdefault(_a["category"], []).append(_a)

# Kinds allowed inside a "random" action's sub-action list — everything
# except "random" itself, so nesting stays one level deep.
NON_NESTABLE_KINDS = [a["id"] for a in ACTIONS if a["id"] != random_action.ID]


def run_action(action, ctx: ActionContext):
    entry = ACTION_BY_ID.get(action.kind)
    if entry is None:
        raise ValueError(f"Unknown action kind: {action.kind!r}")
    entry["module"].run(action, ctx)


# ── Inputs ───────────────────────────────────────────────────────────────

INPUTS = [
    {"id": osc_input.ID, "label": osc_input.LABEL, "category": osc_input.CATEGORY,
     "description": osc_input.DESCRIPTION, "module": osc_input},
    {"id": timer_input.ID, "label": timer_input.LABEL, "category": timer_input.CATEGORY,
     "description": timer_input.DESCRIPTION, "module": timer_input},
    {"id": variable_input.ID, "label": variable_input.LABEL, "category": variable_input.CATEGORY,
     "description": variable_input.DESCRIPTION, "module": variable_input},
]

INPUT_BY_ID: dict = {i["id"]: i for i in INPUTS}

INPUT_CATEGORIES: dict = {}
for _i in INPUTS:
    INPUT_CATEGORIES.setdefault(_i["category"], []).append(_i)


def input_matches(trigger, key: str, value) -> bool:
    """key is the OSC address for kind=='osc', the variable name for
    kind=='variable'. Timer triggers don't go through this — the engine's
    timer loop drives them directly via timer_interval()."""
    entry = INPUT_BY_ID.get(trigger.kind)
    if entry is None or not hasattr(entry["module"], "matches"):
        return False
    return entry["module"].matches(trigger, key, value)


def timer_interval(trigger) -> float:
    return timer_input.next_interval(trigger)