"""
core/engine.py
────────────────
Background engine for VRChat Social Logger. Owns:

  - A slow poll of the user's own friends list (via core.vrchat_api),
    diffed against the previous snapshot to detect location/status/
    avatar changes worth putting in the Friends Feed tab.
  - A fast tail of the local VRChat log (via core.vrlog_tail) for the
    Current Instance tabs.

Both streams are written to disk through core.log_writer with their own
directory size caps, and also handed to the UI layer via plain
callbacks. Per §6.16, this file must never touch a Qt widget directly —
the UI wires these callbacks to Qt Signals itself (see ui/*_tab.py).
"""

from __future__ import annotations

import threading
import time

from core.vrchat_api import VRChatAPI, VRChatAPIError, parse_location
from core.vrlog_tail import VRLogTail
from core.log_writer import RotatingDirLogWriter

FRIEND_POLL_INTERVAL_SEC = 60
LOG_TAIL_INTERVAL_SEC = 2


def _now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


class Engine:
    def __init__(
        self,
        api: VRChatAPI,
        get_config_cb,
        on_friend_event=None,
        on_instance_event=None,
        on_status=None,
        on_error=None,
    ):
        """
        api:               a logged-in VRChatAPI instance
        get_config_cb:     callable returning the live cfg dict, so
                            changes to log dir / size caps apply without
                            a restart
        on_friend_event:   callback(dict) — one Friends Feed event
        on_instance_event: callback(dict) — one Current Instance event
        on_status:         callback(str) — short status text, e.g.
                            "Polled 42 friends", surfaced in the footer
        on_error:          callback(str) — non-fatal error text
        """
        self._api = api
        self._get_config = get_config_cb
        self._on_friend_event = on_friend_event or (lambda e: None)
        self._on_instance_event = on_instance_event or (lambda e: None)
        self._on_status = on_status or (lambda s: None)
        self._on_error = on_error or (lambda s: None)

        self._tail = VRLogTail()
        self._friend_snapshot: dict[str, dict] = {}  # user_id -> last-seen friend dict

        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._friends_writer: RotatingDirLogWriter | None = None
        self._instance_writer: RotatingDirLogWriter | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Lifecycle ─────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        cfg = self._get_config()
        self._friends_writer = RotatingDirLogWriter(
            cfg.get("log_dir"), "friends_feed", cfg.get("friends_log_cap_bytes", 50 * 1024 * 1024),
        )
        self._instance_writer = RotatingDirLogWriter(
            cfg.get("log_dir"), "instance_log", cfg.get("instance_log_cap_bytes", 50 * 1024 * 1024),
        )
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._thread = None

    # ── Background loop ──────────────────────────────────────────────

    def _run(self):
        last_friend_poll = 0.0
        # First instance-log poll should backfill from wherever the log
        # already is, so seed current location without emitting a burst
        # of "join" events for lines already logged before launch.
        self._tail.poll()

        while not self._stop_event.is_set():
            now = time.monotonic()

            # Fast: local log tail
            try:
                events = self._tail.poll()
                for ev in events:
                    self._handle_log_event(ev)
            except Exception as exc:  # never let a parse hiccup kill the thread
                self._on_error(f"Log tail error: {exc}")

            # Slow: friends list poll
            if now - last_friend_poll >= FRIEND_POLL_INTERVAL_SEC:
                last_friend_poll = now
                try:
                    self._poll_friends()
                except VRChatAPIError as exc:
                    self._on_error(f"Friends poll failed: {exc}")
                except Exception as exc:
                    self._on_error(f"Friends poll error: {exc}")

            self._stop_event.wait(LOG_TAIL_INTERVAL_SEC)

    # ── Friends feed ──────────────────────────────────────────────────

    def _poll_friends(self):
        friends = self._api.get_all_friends()
        self._on_status(f"Polled {len(friends)} friends")

        new_snapshot = {}
        for friend in friends:
            uid = friend.get("id")
            if not uid:
                continue
            new_snapshot[uid] = friend
            prev = self._friend_snapshot.get(uid)
            for event in _diff_friend(prev, friend):
                self._emit_friend_event(event)

        # Friends who dropped out of the list entirely this poll (went
        # fully offline and were pruned, or unfriended) — treat as
        # going offline if we don't already know they're offline.
        for uid, prev in self._friend_snapshot.items():
            if uid not in new_snapshot and prev.get("location") != "offline":
                self._emit_friend_event({
                    "kind": "status", "display_name": prev.get("displayName", "?"),
                    "detail": "went offline",
                })

        self._friend_snapshot = new_snapshot

    def _emit_friend_event(self, event: dict):
        event = {"timestamp": _now_ts(), **event}
        if self._friends_writer is not None:
            self._friends_writer.write_event(event)
        self._on_friend_event(event)

    # ── Current instance log ─────────────────────────────────────────

    def _handle_log_event(self, ev):
        event = {
            "timestamp": ev.timestamp or _now_ts(),
            "kind": ev.kind,
            "display_name": ev.display_name,
            "world_id": ev.world_id,
            "instance_id": ev.instance_id,
            "world_name": ev.world_name,
            "extra": ev.extra,
        }
        if self._instance_writer is not None:
            self._instance_writer.write_event(event)
        self._on_instance_event(event)

    def get_current_location(self) -> tuple[str, str, str]:
        """(world_id, instance_id, world_name), read straight from the
        log tail's own tracked state — used by tab 1's info panel."""
        return self._tail.current_location

    def get_friends_snapshot(self) -> dict:
        """Copy of the most recent friends-list poll, keyed by user id —
        used by tab 1 to cross-reference which friends are in the
        current instance."""
        return dict(self._friend_snapshot)


def _diff_friend(prev: dict | None, cur: dict) -> list[dict]:
    """Compare a friend's previous snapshot to their current one and
    produce zero or more feed events. `prev` is None the first time a
    friend is seen this session (no event emitted for that — nothing
    actually changed, we just started watching)."""
    name = cur.get("displayName", "?")
    if prev is None:
        return []

    events = []

    prev_loc = prev.get("location")
    cur_loc = cur.get("location")
    if prev_loc != cur_loc:
        parsed = parse_location(cur_loc)
        if cur_loc in ("private", "traveling") or parsed is None:
            events.append({
                "kind": "location", "display_name": name,
                "detail": f"location hidden or traveling ({cur_loc or 'unknown'})",
            })
        else:
            world_id, instance_id = parsed
            events.append({
                "kind": "location", "display_name": name,
                "detail": "changed instance",
                "world_id": world_id, "instance_id": instance_id,
            })

    prev_status = prev.get("status")
    cur_status = cur.get("status")
    if prev_status != cur_status:
        events.append({
            "kind": "status", "display_name": name,
            "detail": f"status: {prev_status} -> {cur_status}",
        })

    prev_avatar = (prev.get("currentAvatarImageUrl") or prev.get("currentAvatarTags"))
    cur_avatar = (cur.get("currentAvatarImageUrl") or cur.get("currentAvatarTags"))
    if prev_avatar != cur_avatar:
        events.append({
            "kind": "avatar", "display_name": name,
            "detail": "changed avatar",
        })

    return events
