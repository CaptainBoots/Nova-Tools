"""
core/id_parser.py
────────────────────
Extracts VRChat IDs from either a bare ID or a pasted vrchat.com URL —
used by the "add favorite" dialog so pasting a link works the same as
typing the ID directly. Pure string parsing, no network calls.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs

_WORLD_RE = re.compile(r"wrld_[0-9a-fA-F-]+")
_AVATAR_RE = re.compile(r"avtr_[0-9a-fA-F-]+")
_USER_RE = re.compile(r"usr_[0-9a-fA-F-]+")


def extract_world_id(text: str) -> str | None:
    m = _WORLD_RE.search(text or "")
    return m.group(0) if m else None


def extract_avatar_id(text: str) -> str | None:
    m = _AVATAR_RE.search(text or "")
    return m.group(0) if m else None


def extract_user_id(text: str) -> str | None:
    m = _USER_RE.search(text or "")
    return m.group(0) if m else None


def extract_world_and_instance(text: str) -> tuple[str, str] | None:
    """Handles both a raw 'wrld_x:instance_id' location string and a
    pasted https://vrchat.com/home/launch?worldId=...&instanceId=...
    link. Returns None if no instance component could be found."""
    text = (text or "").strip()
    world_id = extract_world_id(text)
    if not world_id:
        return None

    # A pasted launch URL — query-string style.
    try:
        parsed = urlparse(text)
        qs = parse_qs(parsed.query)
        if qs.get("instanceId"):
            return world_id, qs["instanceId"][0]
    except ValueError:
        pass

    # A raw "wrld_x:instance_id" location string.
    marker = world_id + ":"
    if marker in text:
        instance_id = text.split(marker, 1)[1].split("&")[0].strip()
        if instance_id:
            return world_id, instance_id

    return None
