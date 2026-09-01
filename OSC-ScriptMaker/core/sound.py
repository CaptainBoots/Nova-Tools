"""
core/sound.py
──────────────
Fire-and-forget sound playback. Windows uses the stdlib winsound module;
Linux shells out to whichever of paplay/aplay/ffplay is actually on the
system PATH. No extra pip dependency, no blocking.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess


def play_sound(path: str):
    if not path:
        return
    if not os.path.isfile(path):
        return

    system = platform.system()
    try:
        if system == "Windows":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return

        for cmd in (["paplay", path], ["aplay", path], ["ffplay", "-nodisp", "-autoexit", path]):
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    except Exception:
        pass
