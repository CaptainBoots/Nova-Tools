"""
core/vrlog_tail.py
────────────────────
Tails VRChat's own local log file (the same file the game itself writes
to, under %USERPROFILE%\\AppData\\LocalLow\\VRChat\\VRChat\\ on Windows)
and turns lines into structured events for the "current instance" tabs.

This only ever reads the local player's own log about their own client
session — it has nothing to do with the remote API and nothing to do
with any other user's device. Pure backend, no Qt/Tk imports (per the
porting guide §3 point 3) — UI code polls `VRLogTail.poll()` on a timer
or background thread and turns the returned events into feed rows.
"""

from __future__ import annotations

import glob
import os
import re
import time
from dataclasses import dataclass, field

# ── Locating the log file ────────────────────────────────────────────

def default_log_dir() -> str:
    # %USERPROFILE%\AppData\LocalLow is not exposed by a single env var;
    # build it from USERPROFILE the same way VRChat itself resolves it.
    userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    return os.path.join(userprofile, "AppData", "LocalLow", "VRChat", "VRChat")


def find_latest_log(log_dir: str | None = None) -> str | None:
    """VRChat writes a new output_log_*.txt each session. Return the
    most recently modified one, or None if VRChat has never run / the
    folder doesn't exist."""
    log_dir = log_dir or default_log_dir()
    if not os.path.isdir(log_dir):
        return None
    candidates = glob.glob(os.path.join(log_dir, "output_log_*.txt"))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


# ── Event model ───────────────────────────────────────────────────────

@dataclass
class LogEvent:
    kind: str            # "world_join", "player_join", "player_left",
                          # "avatar_change", "instance_left"
    timestamp: str        # as printed in the log, e.g. "2026.08.26 14:03:11"
    display_name: str = ""
    world_id: str = ""
    instance_id: str = ""
    world_name: str = ""
    extra: dict = field(default_factory=dict)


# ── Line patterns ─────────────────────────────────────────────────────
# VRChat's log format has been stable for years; these patterns match
# the well-known lines VRCX and similar tools have long relied on.

_TS = r"(?P<ts>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})"

_RE_JOINING_WORLD = re.compile(
    _TS + r".*\[Behaviour\] Joining wrld_[0-9a-fA-F-]+:\S+"
)
_RE_JOINING_INSTANCE_ID = re.compile(
    _TS + r".*\[Behaviour\] Joining (?P<world_id>wrld_[0-9a-fA-F-]+):(?P<instance_id>\S+)"
)
_RE_ENTERING_ROOM = re.compile(
    _TS + r".*\[Behaviour\] Entering Room: (?P<world_name>.+)"
)
_RE_PLAYER_JOINED = re.compile(
    _TS + r".*\[Behaviour\] OnPlayerJoined (?P<name>.+?)(?:\s\(usr_[0-9a-fA-F-]+\))?$"
)
_RE_PLAYER_LEFT = re.compile(
    _TS + r".*\[Behaviour\] OnPlayerLeft (?P<name>.+?)(?:\s\(usr_[0-9a-fA-F-]+\))?$"
)
_RE_AVATAR_CHANGE = re.compile(
    _TS + r".*\[Behaviour\] (?:Switching|Avatar [Cc]hange).* to (?P<avatar>.+)"
)
_RE_LEFT_ROOM = re.compile(
    _TS + r".*\[Behaviour\] OnLeftRoom"
)


class VRLogTail:
    """Stateful incremental reader: call poll() repeatedly (e.g. every
    1-2s from a background thread) and it returns only the new events
    since the last call, following log rotation to a new session file
    automatically."""

    def __init__(self, log_dir: str | None = None):
        self._log_dir = log_dir or default_log_dir()
        self._path: str | None = None
        self._pos = 0
        self._current_world_name = ""
        self._current_world_id = ""
        self._current_instance_id = ""

    @property
    def current_location(self) -> tuple[str, str, str]:
        """(world_id, instance_id, world_name) for whatever this tail
        last saw the player join — empty strings if unknown yet."""
        return self._current_world_id, self._current_instance_id, self._current_world_name

    def _ensure_open_latest(self) -> bool:
        latest = find_latest_log(self._log_dir)
        if latest is None:
            return False
        if latest != self._path:
            # New session file (VRChat restarted, or first poll) —
            # start reading from the beginning of this session's file
            # so tab 3 can show the full current-instance history.
            self._path = latest
            self._pos = 0
        return True

    def poll(self) -> list[LogEvent]:
        if not self._ensure_open_latest():
            return []
        events: list[LogEvent] = []
        try:
            with open(self._path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._pos)
                new_text = f.read()
                self._pos = f.tell()
        except OSError:
            return []

        for line in new_text.splitlines():
            ev = self._parse_line(line)
            if ev is not None:
                events.append(ev)
        return events

    def _parse_line(self, line: str) -> LogEvent | None:
        m = _RE_JOINING_INSTANCE_ID.search(line)
        if m:
            self._current_world_id = m.group("world_id")
            self._current_instance_id = m.group("instance_id")
            return LogEvent(
                kind="world_join", timestamp=m.group("ts"),
                world_id=self._current_world_id,
                instance_id=self._current_instance_id,
            )

        m = _RE_ENTERING_ROOM.search(line)
        if m:
            self._current_world_name = m.group("world_name").strip()
            return LogEvent(
                kind="world_name", timestamp=m.group("ts"),
                world_name=self._current_world_name,
                world_id=self._current_world_id,
                instance_id=self._current_instance_id,
            )

        m = _RE_PLAYER_JOINED.search(line)
        if m:
            return LogEvent(
                kind="player_join", timestamp=m.group("ts"),
                display_name=m.group("name").strip(),
            )

        m = _RE_PLAYER_LEFT.search(line)
        if m:
            return LogEvent(
                kind="player_left", timestamp=m.group("ts"),
                display_name=m.group("name").strip(),
            )

        m = _RE_AVATAR_CHANGE.search(line)
        if m:
            return LogEvent(
                kind="avatar_change", timestamp=m.group("ts"),
                extra={"avatar": m.group("avatar").strip()},
            )

        m = _RE_LEFT_ROOM.search(line)
        if m:
            self._current_world_id = ""
            self._current_instance_id = ""
            self._current_world_name = ""
            return LogEvent(kind="instance_left", timestamp=m.group("ts"))

        return None
