"""monitors/media.py — Media session info fetch + helpers."""

import re
import subprocess
import sys
from typing import Optional

from core import media_registry

# ── Platform import ───────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        import winrt.windows.media.control as wmc
    except ImportError:
        wmc = None
else:
    wmc = None


# ── Global State Tracking ──────────────────────────────────────────────────────
# Keeps track of the last source ID that was actively playing across function calls
_LAST_PLAYING_SOURCE: Optional[str] = None


# ── Priority Configuration ────────────────────────────────────────────────────
# Apps ordered by strict preference. If multiple items are playing simultaneously,
# items appearing earlier in this list take precedence.
#
# Defaults to core/media_registry.py's built-in order; Settings -> Media lets
# the person drag this into any order they want, via set_priority_order()
# below. Anything in the registry that's missing from a custom order (e.g.
# a newly-added registry entry the person's saved order predates) is appended
# at the end automatically, so old saved orders never silently drop entries.
_PRIORITY_ORDER: list[str] = media_registry.default_order()


def set_priority_order(order: list[str] | None):
    """Called once at Start (reading cfg["media_priority_order"]) and again
    live whenever the person reorders the list in Settings — no restart
    needed, fetch() reads _PRIORITY_ORDER fresh on every call."""
    global _PRIORITY_ORDER
    if not order:
        _PRIORITY_ORDER = media_registry.default_order()
        return
    known = set(media_registry.default_order())
    ordered = [k for k in order if k in known]
    missing = [k for k in media_registry.default_order() if k not in ordered]
    _PRIORITY_ORDER = ordered + missing


def get_priority_order() -> list[str]:
    return list(_PRIORITY_ORDER)


# ── Spotify Web API integration ──────────────────────────────────────────────
# Optional — only used once the person connects Spotify in Settings -> Media
# -> Spotify. Provides "now playing" data straight from Spotify's own API,
# which works identically on every OS and doesn't depend on Spotify (or a
# browser tab) registering an SMTC/MPRIS session at all — see the Settings
# section's docstring for why that matters.
_spotify_session_provider = None  # callable -> core.spotify_api.SpotifySession | None


def set_spotify_session_provider(provider):
    global _spotify_session_provider
    _spotify_session_provider = provider


def _spotify_candidate() -> Optional[dict]:
    if _spotify_session_provider is None:
        return None
    session = _spotify_session_provider()
    if session is None:
        return None
    info = session.get_currently_playing_cached()
    if info is None:
        return None
    return info


def _get_priority_score(raw_id: str) -> int:
    """Returns an integer representing priority. Lower numbers = Higher priority."""
    if not raw_id:
        return len(_PRIORITY_ORDER) + 1
    entry_id = media_registry.id_for_raw(raw_id)
    if entry_id is None:
        return len(_PRIORITY_ORDER)  # Default fallback priority
    try:
        return _PRIORITY_ORDER.index(entry_id)
    except ValueError:
        return len(_PRIORITY_ORDER)


def empty() -> dict:
    return {
        "title": "", "artist": "", "album": "", "album_artist": "",
        "track_number": None, "track_count": None, "source": "",
        "position_ms": 0, "duration_ms": 0, "is_paused": False,
    }


def clean_value(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("none", "unknown", "null") else s


def clean_title(raw: str) -> str:
    if not raw:
        return ""
    t = re.sub(r"\(.*?\)|\[.*?]|\{.*?}", "", raw)
    junk = r"\b(official|video|lyrics|audio|hd|4k|remastered|live|visualizer|explicit|clean|version|mix)\b"
    t = re.sub(junk, "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(ft\.|feat\.|featuring).*", "", t, flags=re.IGNORECASE)
    parts = [p.strip() for p in re.split(r"[-–|•]", t) if len(p.strip()) > 2]
    t = parts[0] if parts else t
    return re.sub(r"\s+", " ", t).strip()


def source_name(raw: str) -> str:
    if not raw:
        return ""
    entry_id = media_registry.id_for_raw(raw)
    if entry_id:
        return media_registry.label_for(entry_id)

    # Advanced Regex Cleanup Fallback
    name = raw.split("!")[-1]
    name = name.split("/")[-1].split("\\")[-1]
    name = name.replace(".exe", "")
    name = name.split(".")[0] if "." in name and "_" in name else name
    name = re.sub(r"_[a-z0-9]{13}$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[0-9a-f]{8,}", "", name, flags=re.IGNORECASE)

    cleaned = re.sub(r"[._-]+", " ", name).strip()
    return cleaned.title() if cleaned else "System Media"


def progress_bar(pos_ms: float, dur_ms: float, filled: str, border: str, empty: str, length: int = 15) -> str:
    if dur_ms <= 0:
        return empty * length
    pct = min(max(pos_ms / dur_ms, 0), 1)
    n   = int(length * pct)
    if 0 < n < length:
        return filled * n + border + empty * (length - n - 1)
    return filled * n + empty * (length - n)


def fmt_time(pos_ms, dur_ms) -> str:
    try:
        ps = max(0, int(float(pos_ms) / 1000))
        ds = max(0, int(float(dur_ms) / 1000))
    except (TypeError, ValueError):
        return ""
    if ds <= 0:
        return ""
    def clk(s):
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    return f"{clk(ps)} / {clk(ds)}"


def _ms(value, fallback: float = 0.0) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return fallback


def estimate_position(info: dict, pos_state: dict, now: float) -> float:
    raw_pos   = _ms(info.get("position_ms"))
    duration  = _ms(info.get("duration_ms"))
    is_paused = bool(info.get("is_paused", False))

    signature = (
        clean_value(info.get("title")),
        clean_value(info.get("artist")),
        clean_value(info.get("album")),
        clean_value(info.get("track_number")),
        duration,
    )

    if not signature[0]:
        pos_state.clear()
        info["position_ms"] = 0
        return 0

    prev_sig  = pos_state.get("signature")
    prev_pos  = _ms(pos_state.get("position_ms"))
    prev_raw  = pos_state.get("raw_position_ms")
    prev_seen = pos_state.get("seen_at", now)

    if signature != prev_sig:
        estimated = raw_pos
    else:
        elapsed_ms = max(0.0, (now - prev_seen) * 1000.0)
        raw_delta  = raw_pos - _ms(prev_raw) if prev_raw is not None else None
        raw_stale  = raw_delta is not None and abs(raw_delta) <= 250.0

        if is_paused:
            estimated = prev_pos if raw_stale else raw_pos
        elif raw_stale:
            estimated = prev_pos + elapsed_ms
        else:
            estimated = raw_pos

    if duration > 0:
        estimated = min(estimated, duration)

    pos_state["signature"]       = signature
    pos_state["position_ms"]     = estimated
    pos_state["raw_position_ms"] = raw_pos
    pos_state["seen_at"]         = now
    info["position_ms"] = estimated
    return estimated


def detail_line(info: dict) -> str:
    parts = []
    album = clean_value(info.get("album"))
    track = info.get("track_number")
    count = info.get("track_count")
    src   = clean_value(info.get("source"))
    t     = fmt_time(info.get("position_ms", 0), info.get("duration_ms", 0))

    if track:
        parts.append(f"Track {track}/{count}" if count else f"Track {track}")
    if t:
        parts.append(t)
    if src:
        parts.append(src)
    return " | ".join(parts)


async def _windows_candidate() -> Optional[tuple[str, bool, dict]]:
    """Returns (raw_id, is_playing, info) for whatever SMTC session wins
    Windows-side priority among ITSELF (not yet compared against Spotify's
    Web API result — that merge happens in fetch()), or None if nothing's
    available at all."""
    if wmc is None:
        return None
    try:
        mgr = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
        sessions = mgr.get_sessions()
        if not sessions:
            return None

        playing_sessions = []
        paused_sessions = []

        for s in sessions:
            raw_id = getattr(s, "source_app_user_model_id", "") or ""
            playback = s.get_playback_info()
            status = playback.playback_status if playback else None

            if status == wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
                playing_sessions.append((s, raw_id))
            else:
                paused_sessions.append((s, raw_id))

        target_session = None
        target_raw_id = ""
        is_playing = False

        if playing_sessions:
            playing_sessions.sort(key=lambda item: _get_priority_score(item[1]))
            target_session, target_raw_id = playing_sessions[0]
            is_playing = True
        elif paused_sessions:
            for s, raw_id in paused_sessions:
                if raw_id == _LAST_PLAYING_SOURCE:
                    target_session, target_raw_id = s, raw_id
                    break
            if target_session is None:
                paused_sessions.sort(key=lambda item: _get_priority_score(item[1]))
                target_session, target_raw_id = paused_sessions[0]

        if target_session is None:
            return None

        props    = await target_session.try_get_media_properties_async()
        timeline = target_session.get_timeline_properties()
        playback = target_session.get_playback_info()

        info = empty()
        info["position_ms"] = timeline.position.total_seconds() * 1000
        info["duration_ms"] = timeline.end_time.total_seconds() * 1000
        info["is_paused"]   = (
                playback.playback_status ==
                wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PAUSED
        )
        info["source"] = source_name(target_raw_id)

        if props:
            info["title"]        = clean_value(getattr(props, "title", ""))
            info["artist"]       = clean_value(getattr(props, "artist", ""))
            info["album"]        = clean_value(getattr(props, "album_title", ""))
            info["album_artist"] = clean_value(getattr(props, "album_artist", ""))
            info["track_number"] = _safe_int(getattr(props, "track_number", None))
            info["track_count"]  = _safe_int(getattr(props, "album_track_count", None))

        return target_raw_id, is_playing, info
    except Exception:
        import traceback
        traceback.print_exc()
        return None


def _linux_candidate() -> Optional[tuple[str, bool, dict]]:
    try:
        players = subprocess.check_output(
            ["playerctl", "-l"], encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2
        ).splitlines()
        if not players:
            return None

        playing_players = []
        paused_players = []

        for p in players:
            status = subprocess.check_output(
                ["playerctl", "-p", p, "status"],
                encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
            ).strip().lower()

            if status == "playing":
                playing_players.append(p)
            else:
                paused_players.append(p)

        player = None
        is_playing = False

        if playing_players:
            playing_players.sort(key=_get_priority_score)
            player = playing_players[0]
            is_playing = True
        elif paused_players:
            if _LAST_PLAYING_SOURCE and _LAST_PLAYING_SOURCE in paused_players:
                player = _LAST_PLAYING_SOURCE
            else:
                paused_players.sort(key=_get_priority_score)
                player = paused_players[0]

        if not player:
            return None

        out = subprocess.check_output(
            ["playerctl", "-p", player, "metadata", "--format",
             "{{title}}\n{{artist}}\n{{album}}\n{{xesam:trackNumber}}\n{{position}}\n{{mpris:length}}"],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
        ).strip().split("\n")

        info = empty()
        if len(out) >= 6:
            info["title"]        = clean_value(out[0])
            info["artist"]       = clean_value(out[1])
            info["album"]        = clean_value(out[2])
            info["track_number"] = _safe_int(out[3])
            info["position_ms"]  = int(out[4]) / 1000
            info["duration_ms"]  = int(out[5]) / 1000
            status = subprocess.check_output(
                ["playerctl", "-p", player, "status"],
                encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
            ).strip().lower()
            info["is_paused"] = (status == "paused")
            info["source"]    = source_name(player)

        return player, is_playing, info
    except Exception:
        return None


async def fetch() -> dict:
    """Merges up to two independent candidates — whatever the OS reports
    (SMTC on Windows / MPRIS on Linux) and, separately, Spotify's own Web
    API if connected in Settings -> Media -> Spotify — through the exact
    same playing > last-active-paused > priority-order selection used
    before this existed, so a connected Spotify account competes fairly
    against everything else on _PRIORITY_ORDER rather than always winning
    or being ignored."""
    global _LAST_PLAYING_SOURCE

    candidates: list[tuple[str, bool, dict]] = []

    if sys.platform == "win32":
        c = await _windows_candidate()
    else:
        c = _linux_candidate()
    if c is not None:
        candidates.append(c)

    spotify_info = _spotify_candidate()
    if spotify_info is not None:
        candidates.append(("spotify", not spotify_info.get("is_paused", False), spotify_info))

    if not candidates:
        return empty()

    playing = [c for c in candidates if c[1]]
    paused  = [c for c in candidates if not c[1]]

    target = None
    if playing:
        playing.sort(key=lambda item: _get_priority_score(item[0]))
        target = playing[0]
        _LAST_PLAYING_SOURCE = target[0]
    elif paused:
        for c in paused:
            if c[0] == _LAST_PLAYING_SOURCE:
                target = c
                break
        if target is None:
            paused.sort(key=lambda item: _get_priority_score(item[0]))
            target = paused[0]

    if target is None:
        return empty()

    return target[2]


def _safe_int(v) -> Optional[int]:
    try:
        n = int(v)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None