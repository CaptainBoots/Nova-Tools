"""
core/Actions/wait_action.py
───────────────────────────────
Action module: pauses the current chain before the next action runs.
Safe to block here — each firing script runs on its own thread
(see script_engine.ScriptEngine._fire), so a wait never stalls the
OSC listener or any other script.
"""

import time

ID = "wait"
LABEL = "Wait"
CATEGORY = "Logic"
DESCRIPTION = "Pauses this script's action chain for a set duration before continuing."


def run(action, ctx):
    time.sleep(max(action.wait_ms, 0) / 1000.0)