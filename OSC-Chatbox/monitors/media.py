"""monitors/media.py — Media session info fetch + helpers."""

import re
import shutil
import subprocess
import sys
from typing import Optional, Callable, Any

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


# ── sudo fix: run detection commands as real user ───────────────────────────────
# When launched via sudo (EUID=0), subprocess calls inherit root's env which
# points XDG_RUNTIME_DIR at /run/user/0/ (root's empty session). Even if we
# fix XDG_RUNTIME_DIR, D-Bus/PipeWire sockets have strict permissions that
# block root from connecting to the real user's session. The robust fix is to
# run the detection commands as the real user via `sudo -u #<uid>`.
import os
_real_user_uid = os.environ.get("SUDO_UID")

def _real_user_uid_or_none() -> str | None:
    """Return the real user's UID string if running via sudo, else None."""
    if os.geteuid() == 0 and _real_user_uid:
        return _real_user_uid
    return None

def _run_as_real_user(cmd: list[str], **kwargs) -> str:
    """
    Run a command as the real user (via sudo -u) when we're root,
    otherwise run normally. Returns stdout.
    """
    uid = _real_user_uid_or_none()
    if uid is None:
        return subprocess.check_output(cmd, **kwargs)
    # Run as the real user. Preserve XDG_RUNTIME_DIR for them.
    # Use --preserve-env to keep their env, but we also explicitly set it.
    sudo_cmd = [
        "sudo", "-u", f"#{uid}",
        "--preserve-env=XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS,PULSE_SERVER",
        "--",
    ] + cmd
    return subprocess.check_output(sudo_cmd, **kwargs)

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


# ── Spotify local (Free, no Premium / no OAuth) detection ───────────────────
# Since Feb 2026 Spotify requires a Premium subscription on the app
# owner's account just to call the Web API at all (403 otherwise), the
# Web API integration below is strictly an *optional Premium extra*
# (phone/Connect playback, etc.). The primary Spotify path — working
# for Free and Premium alike with zero setup — is purely local:
#
#   Linux:   MPRIS (org.mpris.MediaPlayer2.spotify / spotifyd / ncspot /
#            librespot) via playerctl, else raw D-Bus. Browser Spotify
#            Web Player is caught via its open.spotify.com URL / artUrl /
#            track-id even though MPRIS reports the browser name.
#   Windows: SMTC session whose AUMID contains "spotify"
#            (SpotifyAB.SpotifyMusic_...!Spotify) — matched by the
#            registry entry, no login needed.
#
# Helpers below keep that local identification in one place so both
# Linux candidate paths (and future Windows tweaks) agree on what
# counts as "Spotify".
_SPOTIFY_PLAYER_SUBSTRINGS = (
    "spotify", "spotifyd", "ncspot", "librespot", "spotify_player",
)

_SPOTIFY_URL_SUBSTRINGS = (
    "spotify", "open.spotify.com", "spotify:track", "spotify:ad",
    "spotify:episode",
)


def is_spotify_player(player_name: str = "", url: str = "",
                      art_url: str = "", trackid: str = "") -> bool:
    """True if any of the MPRIS/SMTC clues point at Spotify.

    player_name: MPRIS bus short name or SMTC AUMID.
    url/art_url/trackid: MPRIS metadata fields (may be empty).
    Browser web-player tabs report the *browser* as player_name, so the
    URL/track checks are what catch open.spotify.com there.
    """
    p = (player_name or "").lower()
    if p and any(k in p for k in _SPOTIFY_PLAYER_SUBSTRINGS):
        return True
    for field in (url or "", art_url or "", trackid or ""):
        f = field.lower()
        if f and any(k in f for k in _SPOTIFY_URL_SUBSTRINGS):
            return True
    return False


def spotify_process_running() -> bool:
    """Best-effort "is the Spotify desktop app even running?" check.

    Used only as a last-resort hint (e.g. MPRIS momentarily empty while
    the app is starting). Never raises, never blocks the loop.
    """
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                ["tasklist", "/FI", "IMAGENAME eq Spotify.exe", "/NH"],
                encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
            ).lower()
            return "spotify.exe" in out
        for cmd in (["pgrep", "-x", "spotify"], ["pidof", "spotify"]):
            try:
                out = subprocess.check_output(
                    cmd, encoding="utf-8",
                    stderr=subprocess.DEVNULL, timeout=2,
                ).strip()
                if out:
                    return True
            except (OSError, subprocess.SubprocessError):
                continue
    except Exception:
        pass
    return False


# ── Spotify Web API integration (Premium-only, optional) ────────────────────
# Optional — only used once a Premium person connects Spotify in
# Settings -> Media -> Spotify. Provides "now playing" straight from
# Spotify's own API (phone/Connect playback, etc.). Since Feb 2026 the
# Web API 403s without an active Premium subscription on the app
# owner's account, so Free users must NOT use this — local MPRIS/SMTC
# detection above already covers the desktop app + web player for free.
_spotify_session_provider: Optional[Callable[[], Any]] = None  # callable -> core.spotify_api.SpotifySession | None


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

    # Advanced Regex Clean-up Fallback
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


def _linux_candidate_playerctl() -> Optional[tuple[str, bool, dict]]:
    try:
        players = _run_as_real_user(
            ["playerctl", "-l"], encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
        ).splitlines()
        if not players:
            return None

        playing_players = []
        paused_players = []

        for p in players:
            status = _run_as_real_user(
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

        # Request trackid + url + artUrl to detect browser Spotify Web
        # Player (reports the browser name, but open.spotify.com URLs).
        out = _run_as_real_user(
            ["playerctl", "-p", player, "metadata", "--format",
             "{{title}}\n{{artist}}\n{{album}}\n{{xesam:trackNumber}}\n{{position}}\n{{mpris:length}}\n{{xesam:url}}\n{{mpris:artUrl}}\n{{mpris:trackid}}"],
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

            url = out[6].strip() if len(out) > 6 else ""
            art_url = out[7].strip() if len(out) > 7 else ""
            trackid = out[8].strip() if len(out) > 8 else ""

            status = _run_as_real_user(
                ["playerctl", "-p", player, "status"],
                encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
            ).strip().lower()
            info["is_paused"] = (status == "paused")

            # Free local Spotify detection — no Premium/OAuth needed.
            if is_spotify_player(player, url, art_url, trackid):
                info["source"] = "Spotify"
            else:
                info["source"] = source_name(player)

        return player, is_playing, info
    except Exception:
        return None


def _linux_candidate_spotify_direct() -> Optional[tuple[str, bool, dict]]:
    """Direct `playerctl -p spotify` probe for the Free desktop app.

    Covers the race where `playerctl -l` momentarily omits Spotify
    (startup, MPRIS re-register) but the well-known name still answers.
    Only tried when the normal list path found nothing AND playerctl
    is actually installed.
    """
    if shutil.which("playerctl") is None:
        return None
    for well_known in ("spotify", "spotifyd", "ncspot"):
        try:
            status = _run_as_real_user(
                ["playerctl", "-p", well_known, "status"],
                encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
            ).strip().lower()
            if status not in ("playing", "paused"):
                continue
            out = _run_as_real_user(
                ["playerctl", "-p", well_known, "metadata", "--format",
                 "{{title}}\n{{artist}}\n{{album}}\n{{xesam:trackNumber}}\n{{position}}\n{{mpris:length}}\n{{xesam:url}}\n{{mpris:artUrl}}\n{{mpris:trackid}}"],
                encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
            ).strip().split("\n")
            info = empty()
            if len(out) >= 6:
                info["title"]        = clean_value(out[0])
                info["artist"]       = clean_value(out[1])
                info["album"]        = clean_value(out[2])
                info["track_number"] = _safe_int(out[3])
                try:
                    info["position_ms"] = int(out[4]) / 1000
                    info["duration_ms"] = int(out[5]) / 1000
                except (ValueError, IndexError):
                    pass
                info["is_paused"] = (status == "paused")
                info["source"] = "Spotify"
                return well_known, status == "playing", info
        except Exception:
            continue
    return None


def _dbus_list_players() -> list[str]:
    try:
        out = _run_as_real_user(
            ["dbus-send", "--session", "--dest=org.freedesktop.DBus", "--type=method_call", "--print-reply", "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
        )
        players = []
        for line in out.splitlines():
            match = re.search(r'string "(org\.mpris\.MediaPlayer2\.[^"]+)"', line)
            if match:
                players.append(match.group(1))
        return players
    except Exception:
        return []


def _dbus_playback_status(player_dest: str) -> str:
    try:
        out = _run_as_real_user(
            ["dbus-send", "--session", f"--dest={player_dest}", "--type=method_call", "--print-reply", "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties.Get", "string:org.mpris.MediaPlayer2.Player", "string:PlaybackStatus"],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
        )
        match = re.search(r'variant\s+string\s+"([^"]+)"', out)
        if match:
            return match.group(1).lower()
    except Exception:
        pass
    return "stopped"


def _dbus_position_ms(player_dest: str) -> float:
    try:
        out = _run_as_real_user(
            ["dbus-send", "--session", f"--dest={player_dest}", "--type=method_call", "--print-reply", "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties.Get", "string:org.mpris.MediaPlayer2.Player", "string:Position"],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
        )
        match = re.search(r'variant\s+(?:int64|uint64)\s+(\d+)', out)
        if match:
            return float(match.group(1)) / 1000.0
    except Exception:
        pass
    return 0.0


def _dbus_metadata(player_dest: str) -> dict:
    meta = {}
    try:
        out = _run_as_real_user(
            ["dbus-send", "--session", f"--dest={player_dest}", "--type=method_call", "--print-reply", "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties.Get", "string:org.mpris.MediaPlayer2.Player", "string:Metadata"],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2,
        )
        lines = out.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            match_key = re.match(r'string "([^"]+)"', line)
            if match_key:
                key = match_key.group(1)
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line.startswith('string "'):
                        break

                    m_str = re.search(r'variant\s+string\s+"([^"]+)"', next_line)
                    if m_str:
                        meta[key] = m_str.group(1)
                        break

                    m_num = re.search(r'variant\s+(?:uint64|int64|int32|uint32|double)\s+([0-9.+-eE]+)', next_line)
                    if m_num:
                        meta[key] = m_num.group(1)
                        break

                    if 'variant' in next_line and 'array' in next_line:
                        arr_strings = []
                        k = j + 1
                        while k < len(lines):
                            arr_line = lines[k].strip()
                            if arr_line.startswith(']'):
                                break
                            m_arr_str = re.search(r'string "([^"]+)"', arr_line)
                            if m_arr_str:
                                arr_strings.append(m_arr_str.group(1))
                            k += 1
                        meta[key] = ", ".join(arr_strings)
                        break

                    j += 1
                i = j
            else:
                i += 1
    except Exception:
        pass
    return meta


def _linux_candidate_dbus() -> Optional[tuple[str, bool, dict]]:
    try:
        players = _dbus_list_players()
        if not players:
            return None

        playing_players = []
        paused_players = []

        for p in players:
            status = _dbus_playback_status(p)
            if status == "playing":
                playing_players.append(p)
            else:
                paused_players.append(p)

        player = None
        is_playing = False

        def dbus_priority(p):
            short = p.replace("org.mpris.MediaPlayer2.", "")
            return _get_priority_score(short)

        if playing_players:
            playing_players.sort(key=dbus_priority)
            player = playing_players[0]
            is_playing = True
        elif paused_players:
            matched_last = None
            if _LAST_PLAYING_SOURCE:
                for p in paused_players:
                    if _LAST_PLAYING_SOURCE in p:
                        matched_last = p
                        break
            if matched_last:
                player = matched_last
            else:
                paused_players.sort(key=dbus_priority)
                player = paused_players[0]

        if not player:
            return None

        meta = _dbus_metadata(player)
        info = empty()

        info["title"]        = clean_value(meta.get("xesam:title", ""))
        info["artist"]       = clean_value(meta.get("xesam:artist", ""))
        info["album"]        = clean_value(meta.get("xesam:album", ""))
        info["track_number"] = _safe_int(meta.get("xesam:trackNumber"))

        try:
            length_us = float(meta.get("mpris:length", 0))
            info["duration_ms"]  = length_us / 1000.0
        except Exception:
            info["duration_ms"]  = 0.0

        info["position_ms"]  = _dbus_position_ms(player)

        status = _dbus_playback_status(player)
        info["is_paused"]    = (status == "paused")

        player_name = player.replace("org.mpris.MediaPlayer2.", "")
        url = meta.get("xesam:url", "")
        art_url = meta.get("mpris:artUrl", "")
        trackid = meta.get("mpris:trackid", "")

        # Free local Spotify detection — no Premium/OAuth needed.
        if is_spotify_player(player_name, url, art_url, trackid):
            info["source"] = "Spotify"
        else:
            info["source"] = source_name(player_name)

        return player_name, is_playing, info
    except Exception:
        return None


def _linux_candidate() -> Optional[tuple[str, bool, dict]]:
    if shutil.which("playerctl"):
        res = _linux_candidate_playerctl()
        if res is not None:
            return res
        # playerctl exists but listed nothing usable — probe the
        # well-known Spotify names directly before falling to D-Bus.
        res = _linux_candidate_spotify_direct()
        if res is not None:
            return res
    res = _linux_candidate_dbus()
    if res is not None:
        return res
    # D-Bus MPRIS empty too — try PipeWire/PulseAudio audio stream
    # detection (catches Spotify desktop app + web player in browsers).
    return _linux_candidate_pipewire()


def _linux_candidate_pipewire() -> Optional[tuple[str, bool, dict]]:
    """PipeWire/PulseAudio fallback: detect any Spotify audio stream.

    When both playerctl and D-Bus MPRIS are empty (common with the
    Spotify desktop app on some distros, or the web player in a browser),
    pactl still shows Spotify as an active audio sink input.
    """
    playing = None  # True = playing, False = paused, None = not found
    try:
        out = _run_as_real_user(
            ["pactl", "list", "sink-inputs"],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=3,
        )
        # Parse blocks separated by blank lines.
        for block in out.split("\n\n"):
            if "Spotify" not in block:
                continue
            if "Corked: no" in block:
                playing = True
            elif "Corked: yes" in block:
                playing = False
            if playing is True:
                break
    except (OSError, subprocess.SubprocessError):
        pass

    if playing is None:
        return None

    info = empty()
    info["source"] = "Spotify"
    info["is_paused"] = not playing

    return ("spotify", playing, info)


async def fetch() -> dict:
    """Merges up to two independent candidates — whatever the OS reports
    locally (SMTC on Windows / MPRIS on Linux, incl. the Free Spotify
    desktop app + web player with zero setup) and, separately, Spotify's
    own Web API if a *Premium* person connected it in Settings -> Media
    -> Spotify — through the same playing > last-active-paused >
    priority-order selection. Local candidates are appended first so a
    local Spotify session beats the Web API one on ties (fresher
    position, no network lag, works for Free)."""
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

    def _rank(item: tuple[str, bool, dict]) -> tuple[int, int]:
        # (priority score, append order) — append order makes the local
        # OS candidate (index 0) beat the Web API one on equal scores.
        try:
            idx = candidates.index(item)
        except ValueError:
            idx = 0
        return (_get_priority_score(item[0]), idx)

    target = None
    if playing:
        playing.sort(key=_rank)
        target = playing[0]
        _LAST_PLAYING_SOURCE = target[0]
    elif paused:
        for c in paused:
            if c[0] == _LAST_PLAYING_SOURCE:
                target = c
                break
        if target is None:
            paused.sort(key=_rank)
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