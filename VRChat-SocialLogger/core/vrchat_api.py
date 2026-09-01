"""
core/vrchat_api.py
───────────────────
Thin wrapper around the official VRChat REST API (api.vrchat.cloud).
No Qt/Tk imports here — this only knows about `requests`, cookies, and
plain dicts, per the porting guide's "core/ has no Qt" rule (§3 point 3).

Scope, deliberately: this client only ever calls endpoints that act on
the *logged-in user's own* data — their own auth session, their own
friends list (which VRChat already shares with them), and metadata for
an instance the user themself is currently in or otherwise already
holds a valid ID for. It never enumerates or crawls public instances,
never looks up an arbitrary user by id/URL, and never accepts a batch
of instance ids — see the tool's help text for why that boundary is
deliberate, not just unimplemented.

Auth uses VRChat's cookie-based session login (username/password,
optionally followed by a 2FA code), the same flow the official website
and VRCX use. The `auth` cookie is persisted (encrypted at rest is out
of scope for this pass — see config.py) so the person doesn't have to
log in every launch.
"""

from __future__ import annotations

import requests

API_BASE = "https://api.vrchat.cloud/api/1"

# VRChat's API requires a descriptive User-Agent identifying the
# application and a contact point; requests without one are routinely
# rejected with 403. Keep this in sync with main.VERSION.
USER_AGENT = "VRChat-Social-Logger/1.0 (github.com/CaptainBoots/VRChat-Tools)"


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
    # Deliberately dict-in/dict-out, with no file handling of its own —
    # persistence (and how securely it's done) is core.secure_store's
    # job, not this API client's. See ui/app.py for how the two are
    # wired together.

    def export_cookies(self) -> dict:
        """Just the two cookies that make up a VRChat session — never
        the account password, which this class never retains anyway."""
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
        """Attempt to establish a session. Returns the current-user dict
        on immediate success. Raises TwoFactorRequired if a second
        factor is needed — call verify_two_factor() next."""
        resp = self._session.get(
            f"{API_BASE}/auth/user", auth=(username, password), timeout=15,
        )
        if resp.status_code == 401:
            raise VRChatAPIError("Invalid username or password.", 401)
        if not resp.ok:
            raise VRChatAPIError(f"Login failed: {resp.status_code} {resp.text[:200]}", resp.status_code)

        data = resp.json()
        requires = data.get("requiresTwoFactorAuth")
        if requires:
            # requires is a list like ["totp"] or ["emailOtp"]
            method = requires[0] if requires else "totp"
            raise TwoFactorRequired(method)

        self._current_user = data
        return data

    def verify_two_factor(self, code: str, method: str = "totp") -> dict:
        endpoint = "otp" if method == "otp" else ("emailotp" if method == "emailOtp" else "totp")
        result = self._request(
            "POST", f"/auth/twofactorauth/{endpoint}/verify", json={"code": code},
        )
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

    # ── Friends ───────────────────────────────────────────────────────

    def get_friends(self, offline: bool = False, n: int = 100, offset: int = 0) -> list[dict]:
        """Friends VRChat's own API already shares with the logged-in
        user — this never touches any other user's data."""
        params = {"offline": str(offline).lower(), "n": n, "offset": offset}
        return self._request("GET", "/auth/user/friends", params=params)

    def get_all_friends(self) -> list[dict]:
        """Paginate through online + offline friends fully."""
        friends = []
        for offline in (False, True):
            offset = 0
            while True:
                page = self.get_friends(offline=offline, n=100, offset=offset)
                if not page:
                    break
                friends.extend(page)
                if len(page) < 100:
                    break
                offset += 100
        return friends

    # ── World / instance ─────────────────────────────────────────────

    def get_world(self, world_id: str) -> dict:
        return self._request("GET", f"/worlds/{world_id}")

    def get_instance(self, world_id: str, instance_id: str) -> dict:
        """Metadata (population, region, instance type, etc.) for a
        single instance. Callers must already hold a valid world_id +
        instance_id — e.g. from the local game log of an instance the
        person is actually in. This method takes exactly one instance,
        deliberately — no list/batch variant is provided."""
        return self._request("GET", f"/instances/{world_id}:{instance_id}")


def describe_instance_type(instance_id: str) -> str:
    """Best-effort human label from the instance id's own suffix tags
    (~private, ~hidden, ~friends, ~group, or none = public). This is
    the same convention VRChat's client and other community tools rely
    on; not documented as a stable contract by VRChat, so treat the
    result as advisory, not authoritative."""
    if not instance_id:
        return "Unknown"
    if "~private" in instance_id:
        if "canRequestInvite" in instance_id:
            return "Invite+ (requestable)"
        return "Invite Only"
    if "~hidden" in instance_id:
        return "Friends+"
    if "~friends" in instance_id:
        return "Friends Only"
    if "~group" in instance_id:
        if "~groupAccessType(public)" in instance_id:
            return "Group Public"
        return "Group"
    return "Public"


def parse_location(location: str) -> tuple[str, str] | None:
    """Split a VRChat 'location' string (as seen in friend data or the
    local log, e.g. 'wrld_abc123:12345~region(us)') into
    (world_id, instance_id). Returns None for sentinel values like
    'private', 'offline', or 'traveling'."""
    if not location or location in ("private", "offline", "traveling"):
        return None
    if ":" not in location:
        return None
    world_id, instance_id = location.split(":", 1)
    return world_id, instance_id
