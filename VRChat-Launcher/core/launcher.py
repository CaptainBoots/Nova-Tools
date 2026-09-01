"""
core/launcher.py
──────────────────
Profile defaults and the VRChat multi-instance process-launching
backend, extracted from the original monolithic VRCLauncherApp.
No Qt/Tk imports here — this only knows about subprocess.Popen,
plain dicts, and os.path.

Profiles carry a stable "uid" separate from their position in the
list. The original Tk version tracked live processes by *list index*,
which silently mis-associates a running process with the wrong
profile the moment any earlier profile is removed (everything after
it shifts down by one). Using a uid that never changes for the
lifetime of a profile fixes that without changing any visible
behaviour.
"""

import itertools
import os
import subprocess

PROFILE_COLORS = [
    "#9D00FF", "#b44bff", "#4cf5ff", "#4cff91",
    "#ffd166", "#ff4c6a", "#a87fff", "#ff6eb4",
]

DEFAULT_LAUNCH_EXE = r"C:\Program Files (x86)\Steam\steamapps\common\VRChat\launch.exe"

LIMIT_NOTE = (
    "VRChat limits 3 simultaneous instances per public IP address.\n"
    "This is enforced server-side and cannot be bypassed via launch args.\n\n"
    "Workarounds:\n"
    "  • VPN per extra instance (each gets a different public IP)\n"
    "  • Run extra instances on a different network/hotspot\n\n"
    "The limit is per public IP, not per machine."
)

_uid_counter = itertools.count()


def next_uid() -> int:
    """Monotonically increasing id used to track a profile independent
    of its position in the list."""
    return next(_uid_counter)


def resync_uid_counter(profiles: list[dict]):
    """Call once after loading profiles from disk so newly-added
    profiles never collide with a uid loaded from a save file."""
    global _uid_counter
    highest = max((p.get("uid", -1) for p in profiles), default=-1)
    _uid_counter = itertools.count(highest + 1)


def default_profile(idx: int) -> dict:
    return {
        "uid": next_uid(),
        "name": f"Alt {idx}" if idx > 0 else "Main",
        "osc_ip": "127.0.0.1",
        "osc_port": 9000 + idx * 10,
        "listen_port": 9001 + idx * 10,
        "color": PROFILE_COLORS[idx % len(PROFILE_COLORS)],
        "exe_args": "",
    }


def build_launch_command(exe_path: str, profile: dict) -> str:
    cmd = f'"{exe_path}" --osc={profile["listen_port"]}:{profile["osc_port"]}'
    if profile.get("exe_args"):
        cmd += f' {profile["exe_args"]}'
    return cmd


class LauncherProcessManager:
    """Owns the live subprocess.Popen handles for each profile, keyed
    by the profile's stable uid rather than list position. The UI
    polls is_running()/is_running_any() on a timer and updates its own
    widgets; this class never touches Qt and is meant to be created
    once and handed to the UI across theme rebuilds, not recreated —
    recreating it would orphan the handles to any VRChat instances
    that are still actually running."""

    def __init__(self):
        self._procs: dict[int, subprocess.Popen] = {}

    def launch(self, uid: int, exe_path: str, profile: dict) -> subprocess.Popen:
        if not exe_path or not os.path.exists(exe_path):
            raise FileNotFoundError(exe_path)
        cmd = build_launch_command(exe_path, profile)
        proc = subprocess.Popen(cmd, shell=True)
        self._procs[uid] = proc
        return proc

    def kill(self, uid: int):
        proc = self._procs.get(uid)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        self._procs[uid] = None

    def kill_all(self):
        for uid in list(self._procs.keys()):
            self.kill(uid)

    def is_running(self, uid: int) -> bool:
        proc = self._procs.get(uid)
        if proc and proc.poll() is None:
            return True
        if uid in self._procs:
            self._procs[uid] = None
        return False

    def drop(self, uid: int):
        """Stop tracking a uid entirely — call when its profile is removed."""
        self.kill(uid)
        self._procs.pop(uid, None)
