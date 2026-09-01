"""
core/log_writer.py
────────────────────
Writes feed events (friend activity, instance activity) to append-only
daily log files on disk, and enforces a total-directory-size cap by
deleting the oldest file(s) once the cap is exceeded. Pure backend, no
Qt/Tk imports.

File naming: one file per (prefix, day), e.g.
    friends_feed_2026-08-26.log
    instance_log_2026-08-26.log
so a day's activity stays together and "oldest file" is a meaningful,
predictable unit to delete.
"""

from __future__ import annotations

import glob
import json
import os
import time


class RotatingDirLogWriter:
    def __init__(self, directory: str, prefix: str, max_bytes: int):
        """
        directory:  folder the log files live in (created if missing)
        prefix:     filename prefix, e.g. "friends_feed" or "instance_log"
        max_bytes:  total size cap for all files matching this prefix in
                    `directory`. When appending would exceed it, the
                    oldest matching file is deleted first (repeatedly,
                    if needed) before writing.
        """
        self.directory = directory
        self.prefix = prefix
        self.max_bytes = max_bytes
        os.makedirs(self.directory, exist_ok=True)

    def _matching_files(self) -> list[str]:
        return glob.glob(os.path.join(self.directory, f"{self.prefix}_*.log"))

    def _current_file_path(self) -> str:
        day = time.strftime("%Y-%m-%d")
        return os.path.join(self.directory, f"{self.prefix}_{day}.log")

    def _total_size(self) -> int:
        total = 0
        for path in self._matching_files():
            try:
                total += os.path.getsize(path)
            except OSError:
                pass
        return total

    def _enforce_cap(self, incoming_bytes: int):
        """Delete oldest files (by mtime) until there's room for
        incoming_bytes, or nothing is left to delete."""
        if self.max_bytes <= 0:
            return  # 0/negative means "no cap" — never delete
        while self._total_size() + incoming_bytes > self.max_bytes:
            files = self._matching_files()
            if not files:
                break
            oldest = min(files, key=os.path.getmtime)
            try:
                os.remove(oldest)
            except OSError:
                break

    def write_event(self, event: dict):
        """Append one JSON-line event, rotating the directory first if
        the cap would otherwise be exceeded."""
        line = json.dumps(event, ensure_ascii=False) + "\n"
        incoming = len(line.encode("utf-8"))
        self._enforce_cap(incoming)
        path = self._current_file_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    def read_recent(self, limit: int = 500) -> list[dict]:
        """Read up to `limit` most-recent events across all files
        matching this prefix, oldest-to-newest, for populating a feed
        tab on startup."""
        files = sorted(self._matching_files(), key=os.path.getmtime)
        events: list[dict] = []
        for path in files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue
        return events[-limit:]
