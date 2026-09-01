"""
core/vrchat_api.py
───────────────────
Thin wrapper around the official VRChat REST API (api.vrchat.cloud),
for VRChat Local Favorites. Same auth pattern as VRChat-Social-Logger's
copy of this file (cookie-based session, 2FA support, dict-in/dict-out
cookie handling so core.secure_store owns persistence) — extended here
with the lookups this tool actually needs: fetching a single world,
avatar, or user by ID; searching users/avatars by name; selecting an
avatar on the logged-in account; and reading the account's own
*official* VRChat favorites once, for the optional first-launch import.

Scope, deliberately, same boundary as Social Logger: every method here
acts on the logged-in user's own account or fetches a single named
item the person already has an ID/URL for. There is no "list every
public instance" or "scan users" capability — search_users() is a
single query against VRChat's own search endpoint, the same one the
official site's search box uses, not a crawl.
"""

from __future__ import annotations

import requests

API_BASE = "https://api.vrchat.cloud/api/1"
USER_AGENT = "VRChat-Local-Favorites/1.0 (github.com/CaptainBoots/VRChat-Tools)"


class VRChatAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class TwoFactorRequired(Exception):
    """Raised by login() when the account needs a second factor before
    the session is actually authenticated. Call verify_two_factor()
    with the code the person enters, using the same VRChatAPI instance
    (it keeps the partially-authenticated session cookie)."""
    def __init__(self, method: str):
        super().__init__(f"Two-factor required ({method})")
        self.method = method  # "totp", "otp", or "emailOtp"


class VRChatAPI:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        self._current_user: dict | None = None

    # ── Cookie import/export ─────────────────────────────────────────
    # Dict-in/dict-out, no file handling of its own — persistence lives
    # in core.secure_store, wired together in ui/app.py.

    def export_cookies(self) -> dict:
        return {c.name: c.value for c in self._session.cookies if c.name in ("auth", "twoFactorAuth")}

    def import_cookies(self, cookies: dict):
        for name, value in cookies.items():
            self._session.cookies.set(name, value, domain="api.vrchat.cloud")

    def clear_cookies(self):
        self._session.cookies.clear()
        self._current_user = None

    # ── Low-level request helper ─────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self._session.request(method, f"{API_BASE}{path}", timeout=15, **kwargs)
        if resp.status_code == 401:
            raise VRChatAPIError("Not authenticated (401) — log in again.", 401)
        if not resp.ok:
            raise VRChatAPIError(f"{method} {path} failed: {resp.status_code} {resp.text[:200]}", resp.status_code)
        if not resp.content:
            return {}
        return resp.json()

    # ── Auth ──────────────────────────────────────────────────────────

    def is_logged_in(self) -> bool:
        return self._session.cookies.get("auth") is not None

    def login(self, username: str, password: str) -> dict:
        resp = self._session.get(f"{API_BASE}/auth/user", auth=(username, password), timeout=15)
        if resp.status_code == 401:
            raise VRChatAPIError("Invalid username or password.", 401)
        if not resp.ok:
            raise VRChatAPIError(f"Login failed: {resp.status_code} {resp.text[:200]}", resp.status_code)
        data = resp.json()
        requires = data.get("requiresTwoFactorAuth")
        if requires:
            raise TwoFactorRequired(requires[0] if requires else "totp")
        self._current_user = data
        return data

    def verify_two_factor(self, code: str, method: str = "totp") -> dict:
        endpoint = "otp" if method == "otp" else ("emailotp" if method == "emailOtp" else "totp")
        result = self._request("POST", f"/auth/twofactorauth/{endpoint}/verify", json={"code": code})
        if not result.get("verified"):
            raise VRChatAPIError("Two-factor code rejected.")
        return self.get_current_user()

    def get_current_user(self) -> dict:
        data = self._request("GET", "/auth/user")
        self._current_user = data
        return data

    def logout(self):
        try:
            self._request("PUT", "/logout")
        except VRChatAPIError:
            pass
        self.clear_cookies()

    # ── Worlds ────────────────────────────────────────────────────────

    def get_world(self, world_id: str) -> dict:
        return self._request("GET", f"/worlds/{world_id}")

    def get_instance(self, world_id: str, instance_id: str) -> dict:
        return self._request("GET", f"/instances/{world_id}:{instance_id}")

    def search_worlds(self, query: str, n: int = 20) -> list[dict]:
        return self._request("GET", "/worlds", params={"search": query, "n": n})

    # ── Avatars ───────────────────────────────────────────────────────

    def get_avatar(self, avatar_id: str) -> dict:
        return self._request("GET", f"/avatars/{avatar_id}")

    def select_avatar(self, avatar_id: str) -> dict:
        """Switches the logged-in account into this avatar. Only works
        for an avatar you own, or one already in your real (capped)
        VRChat avatar favorites — VRChat's own permission rule, not
        this tool's. Callers should catch VRChatAPIError and offer the
        avatar's web page as a fallback rather than treating this as
        fatal."""
        return self._request("PUT", f"/avatars/{avatar_id}/select")

    def search_avatars(self, query: str, n: int = 20) -> list[dict]:
        """VRChat only allows searching your own or featured avatars —
        this can't be used to browse other people's private avatars."""
        return self._request("GET", "/avatars", params={"search": query, "n": n, "releaseStatus": "all"})

    # ── Users ─────────────────────────────────────────────────────────

    def get_user(self, user_id: str) -> dict:
        return self._request("GET", f"/users/{user_id}")

    def search_users(self, query: str, n: int = 20) -> list[dict]:
        """A single query against VRChat's own user search — the same
        thing the site's search box does. Not a crawl or a location
        lookup; returns public profile info only."""
        return self._request("GET", "/users", params={"search": query, "n": n})

    # ── Official favorites (for the optional first-launch import) ────

    def get_favorites(self, fav_type: str | None = None, tag: str | None = None,
                       n: int = 100, offset: int = 0) -> list[dict]:
        params = {"n": n, "offset": offset}
        if fav_type:
            params["type"] = fav_type
        if tag:
            params["tag"] = tag
        return self._request("GET", "/favorites", params=params)

    def get_all_favorites(self, fav_type: str | None = None) -> list[dict]:
        results = []
        offset = 0
        while True:
            page = self.get_favorites(fav_type=fav_type, n=100, offset=offset)
            if not page:
                break
            results.extend(page)
            if len(page) < 100:
                break
            offset += 100
        return results

    def get_favorite_groups(self, fav_type: str | None = None) -> list[dict]:
        params = {}
        if fav_type:
            params["type"] = fav_type
        return self._request("GET", "/favorite/groups", params=params)


def describe_instance_type(instance_id: str) -> str:
    """Best-effort human label from the instance id's own suffix tags —
    same convention as the Social Logger's copy of this helper."""
    if not instance_id:
        return "Unknown"
    if "~private" in instance_id:
        return "Invite+ (requestable)" if "canRequestInvite" in instance_id else "Invite Only"
    if "~hidden" in instance_id:
        return "Friends+"
    if "~friends" in instance_id:
        return "Friends Only"
    if "~group" in instance_id:
        return "Group Public" if "~groupAccessType(public)" in instance_id else "Group"
    return "Public"


def parse_location(location: str) -> tuple[str, str] | None:
    if not location or location in ("private", "offline", "traveling"):
        return None
    if ":" not in location:
        return None
    world_id, instance_id = location.split(":", 1)
    return world_id, instance_id
