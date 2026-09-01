"""
core/spotify_api.py
─────────────────────
Spotify Web API access for the "now playing" data, using the
Authorization Code + PKCE OAuth flow. This is the flow Spotify
recommends for desktop/native apps precisely because it needs no
client secret embedded in the app — only a public client_id (the user
enters their own, registered free at
https://developer.spotify.com/dashboard) and a redirect URI pointing
back to a short-lived localhost server this module spins up itself.

Deliberately no in-app browser/popup anywhere in this file: connecting
opens the person's own default system browser (webbrowser.open) to
Spotify's real login page, then a plain http.server on 127.0.0.1
catches the single redirect and shuts itself down immediately after.
Spotify's login page, 2FA, and password entry are entirely Spotify's
own UI — this app never sees a password, only the short-lived
authorization code Spotify redirects back with.

Pure backend — no Qt imports here, same separation as
core/vrchat_api.py-style modules in VRChat-Tools generally. The only
state kept in memory is the token dict; persistence across launches is
core/secure_store.py's job, not this module's.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
CURRENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"

# Only what's needed to read what's currently playing — deliberately
# not requesting anything that could modify the person's account
# (playback control, playlist edits, etc).
SCOPES = "user-read-currently-playing user-read-playback-state"

CALLBACK_HOST = "127.0.0.1"
CALLBACK_PATH = "/callback"

_CACHE_TTL_SEC = 2.0  # throttle polling Spotify's API on every single tick


class SpotifyAPIError(Exception):
    pass


class SpotifyAuthTimeout(SpotifyAPIError):
    """Nobody completed the browser authorization within the timeout."""


class SpotifyAuthDenied(SpotifyAPIError):
    """Spotify redirected back with an error= param (user hit Cancel,
    or denied the requested scopes)."""


# ── PKCE ──────────────────────────────────────────────────────────────────────

def _generate_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(64)).decode("ascii").rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


# ── Local redirect-catcher server ────────────────────────────────────────────
# A single-request HTTP server on localhost — this IS the "redirect_uri"
# Spotify sends the browser back to after the person approves/denies
# access on Spotify's own page. Never listens on anything but loopback,
# never serves more than the one expected request, and shuts itself
# down immediately after (or after `timeout_sec` with nothing received).

class _CallbackServer:
    def __init__(self, expected_state: str, timeout_sec: float = 120.0):
        self._expected_state = expected_state
        self._timeout_sec = timeout_sec
        self._result: dict = {}
        self._event = threading.Event()

        handler = self._make_handler()
        self._httpd = HTTPServer((CALLBACK_HOST, 0), handler)  # port 0 = OS picks a free one
        self.port = self._httpd.server_address[1]

    def _make_handler(self):
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != CALLBACK_PATH:
                    self.send_response(404)
                    self.end_headers()
                    return

                params = urllib.parse.parse_qs(parsed.query)
                state = (params.get("state") or [""])[0]
                code = (params.get("code") or [""])[0]
                error = (params.get("error") or [""])[0]

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                if error:
                    body = "<html><body><h2>Spotify authorization was cancelled or denied.</h2>You can close this tab and go back to OSC-Chatbox.</body></html>"
                elif state != outer._expected_state:
                    body = "<html><body><h2>This authorization link doesn't match — please try connecting again from OSC-Chatbox.</h2></body></html>"
                    error = "state_mismatch"
                else:
                    body = "<html><body><h2>Spotify connected.</h2>You can close this tab and go back to OSC-Chatbox.</body></html>"
                self.wfile.write(body.encode("utf-8"))

                outer._result["code"] = code
                outer._result["error"] = error
                outer._event.set()

            def log_message(self, fmt, *args):
                pass  # don't spam stdout with HTTP access logs for a one-shot local server

        return _Handler

    def wait_for_code(self) -> str:
        """Blocks (call from a background thread, not the UI thread)
        until the browser redirect arrives or timeout_sec elapses.
        Raises SpotifyAuthTimeout / SpotifyAuthDenied, or returns the
        authorization code string on success."""
        server_thread = threading.Thread(target=self._httpd.handle_request, daemon=True)
        server_thread.start()

        got_it = self._event.wait(self._timeout_sec)
        try:
            self._httpd.server_close()
        except OSError:
            pass

        if not got_it:
            raise SpotifyAuthTimeout("Timed out waiting for Spotify authorization in the browser.")
        if self._result.get("error"):
            raise SpotifyAuthDenied(f"Spotify authorization failed: {self._result['error']}")
        code = self._result.get("code")
        if not code:
            raise SpotifyAPIError("No authorization code received.")
        return code


def build_authorize_url(client_id: str, redirect_uri: str, code_challenge: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "scope": SCOPES,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


# ── Token exchange ────────────────────────────────────────────────────────────

def _post_form(url: str, fields: dict) -> dict:
    data = urllib.parse.urlencode(fields).encode("ascii")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SpotifyAPIError(f"Spotify token request failed ({exc.code}): {body}")
    except urllib.error.URLError as exc:
        raise SpotifyAPIError(f"Could not reach Spotify: {exc.reason}")


def exchange_code(client_id: str, code: str, code_verifier: str, redirect_uri: str) -> dict:
    """Returns {"access_token", "refresh_token", "expires_at"} —
    expires_at is a unix timestamp computed here from the response's
    relative expires_in, so callers never have to do that math."""
    resp = _post_form(TOKEN_URL, {
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    })
    return {
        "access_token": resp["access_token"],
        "refresh_token": resp.get("refresh_token", ""),
        "expires_at": time.time() + float(resp.get("expires_in", 3600)),
    }


def refresh_token(client_id: str, refresh_token_: str) -> dict:
    """Same return shape as exchange_code(). Spotify sometimes omits
    refresh_token on a refresh response (it means keep using the old
    one) — callers should keep the previous refresh_token if this
    dict's is empty."""
    resp = _post_form(TOKEN_URL, {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token_,
    })
    return {
        "access_token": resp["access_token"],
        "refresh_token": resp.get("refresh_token", ""),
        "expires_at": time.time() + float(resp.get("expires_in", 3600)),
    }


def connect_blocking(client_id: str, timeout_sec: float = 120.0) -> dict:
    """The whole PKCE dance, blocking — meant to be called from a
    background thread (see ui/spotify_section.py's worker), never the
    UI thread, since it opens a browser and then blocks on network
    I/O for up to timeout_sec. Returns the same dict shape as
    exchange_code()."""
    verifier, challenge = _generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    server = _CallbackServer(expected_state=state, timeout_sec=timeout_sec)
    redirect_uri = f"http://{CALLBACK_HOST}:{server.port}{CALLBACK_PATH}"
    url = build_authorize_url(client_id, redirect_uri, challenge, state)

    import webbrowser
    webbrowser.open(url)

    code = server.wait_for_code()
    return exchange_code(client_id, code, verifier, redirect_uri)


# ── Currently playing ──────────────────────────────────────────────────────────

def get_currently_playing(access_token: str) -> dict | None:
    """Returns None if nothing is playing (Spotify returns 204 for
    this) or on any request error — callers should treat None as
    "no data available right now", not necessarily "not connected".
    Raises SpotifyAPIError specifically for a 401 (expired/invalid
    token), so callers know a refresh is needed rather than just
    silently getting nothing."""
    req = urllib.request.Request(CURRENTLY_PLAYING_URL)
    req.add_header("Authorization", f"Bearer {access_token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 204:
                return None
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise SpotifyAPIError("expired_token")
        if exc.code == 204:
            return None
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    if not payload or not payload.get("item"):
        return None

    item = payload["item"]
    artists = ", ".join(a.get("name", "") for a in item.get("artists", []) if a.get("name"))
    album = item.get("album") or {}

    return {
        "title": item.get("name", "") or "",
        "artist": artists,
        "album": album.get("name", "") or "",
        "album_artist": artists,
        "track_number": item.get("track_number"),
        "track_count": album.get("total_tracks"),
        "source": "Spotify",
        "position_ms": payload.get("progress_ms", 0) or 0,
        "duration_ms": item.get("duration_ms", 0) or 0,
        "is_paused": not payload.get("is_playing", False),
    }


# ── Stateful session wrapper ────────────────────────────────────────────────
# Handles auto-refresh + a short cache so monitors/media.py's polling loop
# (ticking roughly once a second) doesn't hit Spotify's API on every single
# tick — a couple of req/sec would be fine per Spotify's rate limits, but
# there's no reason to.

class SpotifySession:
    def __init__(self, client_id: str, tokens: dict, on_tokens_changed=None):
        self._client_id = client_id
        self._tokens = dict(tokens)
        self._on_tokens_changed = on_tokens_changed  # callback(new_tokens: dict) -> persist it
        self._cache: dict | None = None
        self._cache_at = 0.0
        self._lock = threading.Lock()

    def _ensure_fresh_token(self) -> str:
        if time.time() < self._tokens.get("expires_at", 0) - 30:
            return self._tokens["access_token"]
        new_tokens = refresh_token(self._client_id, self._tokens["refresh_token"])
        if not new_tokens.get("refresh_token"):
            new_tokens["refresh_token"] = self._tokens["refresh_token"]
        self._tokens = new_tokens
        if self._on_tokens_changed:
            self._on_tokens_changed(new_tokens)
        return self._tokens["access_token"]

    def get_currently_playing_cached(self) -> dict | None:
        with self._lock:
            now = time.time()
            if now - self._cache_at < _CACHE_TTL_SEC:
                return self._cache
            try:
                token = self._ensure_fresh_token()
                result = get_currently_playing(token)
            except SpotifyAPIError:
                # Token refresh failed (revoked access, bad refresh
                # token, etc.) — surface as "nothing" rather than
                # raising into the polling loop; the Settings UI is
                # where a real "reconnect" prompt belongs, not here.
                result = None
            self._cache = result
            self._cache_at = now
            return result
