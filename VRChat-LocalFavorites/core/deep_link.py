"""
core/deep_link.py
────────────────────
Builds the vrchat.com URLs used to hand off to the installed VRChat
client, or to just open the relevant page on vrchat.com. VRChat
registers a protocol handler (its own "Installation Helper") that
intercepts these specific URLs and launches the game; if that
registration is missing or broken on someone's machine, the URL just
opens as a normal webpage in their browser instead of silently doing
nothing — vrchat.com's own launch page has a manual "Launch" button too,
so this degrades gracefully either way.

Verified URL shape (matches links VRChat's own site generates, and
what community tools like VRCX use):
    https://vrchat.com/home/launch?worldId=<worldId>&instanceId=<instanceId>

Pure backend, no Qt — ui code calls open_url() directly.
"""

from __future__ import annotations

import webbrowser


def launch_url(world_id: str, instance_id: str | None = None) -> str:
    """A join/launch link. With no instance_id, this creates or joins
    a fresh instance of the world; with one, it targets that specific
    instance if it's still open."""
    url = f"https://vrchat.com/home/launch?worldId={world_id}"
    if instance_id:
        url += f"&instanceId={instance_id}"
    return url


def world_page_url(world_id: str) -> str:
    return f"https://vrchat.com/home/world/{world_id}"


def avatar_page_url(avatar_id: str) -> str:
    return f"https://vrchat.com/home/avatar/{avatar_id}"


def user_page_url(user_id: str) -> str:
    return f"https://vrchat.com/home/user/{user_id}"


def open_url(url: str) -> bool:
    return webbrowser.open(url)
