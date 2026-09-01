"""
core/Actions/run_program_action.py
──────────────────────────────────────
Action module: launches a local program/script, fire-and-forget
(never waited on — a hung child process must never stall a script
chain).
"""

import shlex
import subprocess

ID = "run_program"
LABEL = "Run Program"
CATEGORY = "System"
DESCRIPTION = "Launches a local program or script with optional arguments."


def run(action, ctx):
    if not action.program_path:
        return
    cmd = [action.program_path]
    if action.program_args:
        cmd += shlex.split(action.program_args)
    subprocess.Popen(cmd)