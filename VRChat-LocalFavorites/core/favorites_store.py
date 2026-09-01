"""
core/favorites_store.py
──────────────────────────
Local, unlimited favorites storage — the actual point of this tool
versus VRChat's own capped favorite slots (50 avatars, similar caps for
worlds/friends unless on VRC+). Organized as user-created GROUPS, any
number of them; each group is its own JSON file, so group management
maps directly onto plain files a person could also inspect, back up,
or hand-edit if they wanted to.

Layout on disk:
    <base_dir>/<category>/<group_name>.json

<category> is one of "worlds", "avatars", "players", "instances".
Each JSON file holds a list of item dicts. The same item id can appear
in more than one group — groups behave like tags, not a strict
single-parent folder hierarchy.

Pure backend — no Qt imports.
"""

from __future__ import annotations

import json
import os
import re
import time

CATEGORIES = ("worlds", "avatars", "players", "instances")

# Group names come from the person typing into a text field, and they
# become a filename directly — so this is the one place in this file
# that needs to be defensive about path traversal (e.g. "../../evil")
# or reserved characters, same principle as the artifact-storage key
# rules elsewhere in this codebase.
_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9 _\-\.]+")


def sanitize_group_name(name: str) -> str:
    name = (name or "").strip().replace("/", "_").replace("\\", "_")
    name = _UNSAFE_CHARS_RE.sub("", name)
    name = name.strip(". ")
    return name[:100] or "Unnamed"


class FavoritesStore:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        for category in CATEGORIES:
            os.makedirs(os.path.join(base_dir, category), exist_ok=True)

    def _category_dir(self, category: str) -> str:
        if category not in CATEGORIES:
            raise ValueError(f"Unknown category: {category}")
        return os.path.join(self.base_dir, category)

    def _group_path(self, category: str, group_name: str) -> str:
        safe = sanitize_group_name(group_name)
        return os.path.join(self._category_dir(category), f"{safe}.json")

    # ── Groups ──────────────────────────────────────────────────────

    def list_groups(self, category: str) -> list[str]:
        d = self._category_dir(category)
        return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))

    def create_group(self, category: str, group_name: str) -> str:
        safe = sanitize_group_name(group_name)
        path = self._group_path(category, safe)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump([], f)
        return safe

    def delete_group(self, category: str, group_name: str):
        path = self._group_path(category, group_name)
        if os.path.exists(path):
            os.remove(path)

    def rename_group(self, category: str, old_name: str, new_name: str) -> str:
        old_path = self._group_path(category, old_name)
        new_safe = sanitize_group_name(new_name)
        new_path = self._group_path(category, new_safe)
        if os.path.exists(old_path) and old_path != new_path and not os.path.exists(new_path):
            os.replace(old_path, new_path)
        return new_safe

    # ── Items within a group ────────────────────────────────────────

    def list_items(self, category: str, group_name: str) -> list[dict]:
        path = self._group_path(category, group_name)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []  # a corrupt group file degrades to "empty", never crashes the browser

    def _write_items(self, category: str, group_name: str, items: list[dict]):
        path = self._group_path(category, group_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)

    def add_item(self, category: str, group_name: str, item: dict) -> bool:
        """item must include an 'id' key. Returns False (no-op) if an
        item with that id is already in this group."""
        items = self.list_items(category, group_name)
        if any(existing.get("id") == item.get("id") for existing in items):
            return False
        item = {**item, "added_at": item.get("added_at") or time.strftime("%Y-%m-%d %H:%M:%S")}
        items.append(item)
        self._write_items(category, group_name, items)
        return True

    def remove_item(self, category: str, group_name: str, item_id: str):
        items = [i for i in self.list_items(category, group_name) if i.get("id") != item_id]
        self._write_items(category, group_name, items)

    def update_item(self, category: str, group_name: str, item_id: str, **fields):
        items = self.list_items(category, group_name)
        for i in items:
            if i.get("id") == item_id:
                i.update(fields)
                break
        self._write_items(category, group_name, items)

    def all_items(self, category: str) -> dict[str, list[dict]]:
        """group_name -> items, across every group in this category —
        used for dedupe checks and 'which groups contain this item'."""
        return {g: self.list_items(category, g) for g in self.list_groups(category)}

    def groups_containing(self, category: str, item_id: str) -> list[str]:
        return [g for g, items in self.all_items(category).items()
                if any(i.get("id") == item_id for i in items)]
