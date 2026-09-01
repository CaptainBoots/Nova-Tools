"""
core/Actions/random_action.py
─────────────────────────────────
Action module: picks one of its embedded sub-actions at random and
runs it. Sub-actions are single Actions (any kind except "random"
itself — one nesting level only, kept that way by the UI) rather than
full chains, to keep this predictable.
"""

import random

ID = "random"
LABEL = "Random Action"
CATEGORY = "Logic"
DESCRIPTION = "Runs one randomly-chosen action from a set you define — great for varied reactions."


def run(action, ctx):
    if not action.sub_actions:
        return
    sub = random.choice(action.sub_actions)
    ctx.run_sub_action(sub)