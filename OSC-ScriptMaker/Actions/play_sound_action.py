"""
core/Actions/play_sound_action.py
─────────────────────────────────────
Action module: plays a local sound file, fire-and-forget.
"""

from core.sound import play_sound

ID = "play_sound"
LABEL = "Play Sound"
CATEGORY = "System"
DESCRIPTION = "Plays a local sound file."


def run(action, ctx):
    play_sound(action.sound_path)