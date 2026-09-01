"""monitors/vrchat.py — tails VRChat output log + listens for OSC feedback."""
import threading, time, os, re, glob, json, sys

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

_data = {
    "vrc_fps":          None,
    "vrc_world":        None,
    "vrc_player_count": 0,
    "vrc_avatar":       None,
    "vrc_ping":         None,
}
_lock    = threading.Lock()
_players = set()

# ── OSC feedback listener (VRChat → us on port 9001) ─────────────────────────

def _on_fps(address, *args):
    if args:
        with _lock:
            _data["vrc_fps"] = int(args[0])

def _start_osc_server():
    dispatcher = Dispatcher()
    dispatcher.map("/avatar/parameters/FPS", _on_fps)
    dispatcher.set_default_handler(lambda *a: None)
    try:
        server = BlockingOSCUDPServer(("127.0.0.1", 9001), dispatcher)
        server.serve_forever()
    except Exception as e:
        print(f"[vrchat monitor] OSC server error: {e}")

# ── Log regexes ───────────────────────────────────────────────────────────────
_RE_WORLD  = re.compile(r"\[Behaviour\] Joining or Creating Room:\s+(.+)")
_RE_JOIN   = re.compile(r"\[Behaviour\] OnPlayerJoined\s+(.+?)(?:\s+\(usr_[^)]+\))?$")
_RE_LEAVE  = re.compile(r"\[Behaviour\] OnPlayerLeft\s+(.+?)(?:\s+\(usr_[^)]+\))?$")
_RE_AVATAR = re.compile(r"\[Behaviour\] Switching \S+ to avatar (.+)")
_RE_STATS  = re.compile(r'^\{"runningTime":')

def _parse_stats(line: str):
    try:
        obj = json.loads(line)
        fps = ping = None
        for stat in obj.get("stats", []):
            name = stat.get("name")
            if name == "fps":
                fps = int(stat["tw-mean"])
            elif name == "ping":
                ping = int(stat["tw-mean"])
        return fps, ping
    except Exception:
        return None, None

def _log_search_bases() -> list[str]:
    """
    Candidate VRChat LocalLow directories to search, in priority order.

    Windows: the real AppData\\LocalLow path.
    Linux:   VRChat normally runs under Proton, so the log lives inside a
             Steam compatdata prefix instead. We don't know the exact
             library location or appid folder ahead of time, so glob
             across every discoverable Steam library for the standard
             compatdata layout. Falls back to a native-Linux path too,
             in case someone's running a non-Proton client under Wine
             directly or a future native build.
    """
    if sys.platform == "win32":
        return [os.path.expandvars(r"%APPDATA%\..\LocalLow\VRChat\VRChat")]

    bases = []

    # VRChat's Steam appid is 438100 — check the common compatdata locations
    # directly first (fast path, no globbing needed).
    home = os.path.expanduser("~")
    steam_roots = [
        os.path.join(home, ".steam", "steam"),
        os.path.join(home, ".local", "share", "Steam"),
        os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),  # Flatpak
    ]
    for root in steam_roots:
        bases.append(os.path.join(
            root, "steamapps", "compatdata", "438100", "pfx",
            "drive_c", "users", "steamuser", "AppData", "LocalLow", "VRChat", "VRChat",
        ))

    # Broader fallback: search all Steam library folders (handles custom
    # library locations on other drives/mounts) for the same relative path.
    for root in steam_roots:
        pattern = os.path.join(
            root, "steamapps", "libraryfolders.vdf",
        )
        if os.path.isfile(pattern):
            try:
                with open(pattern, "r", encoding="utf-8", errors="ignore") as f:
                    for m in re.finditer(r'"path"\s+"([^"]+)"', f.read()):
                        lib_path = m.group(1).replace("\\\\", "/")
                        bases.append(os.path.join(
                            lib_path, "steamapps", "compatdata", "438100", "pfx",
                            "drive_c", "users", "steamuser", "AppData", "LocalLow", "VRChat", "VRChat",
                        ))
            except OSError:
                pass

    # Non-Proton fallback (native Wine prefix, or a future native client).
    bases.append(os.path.join(home, ".wine", "drive_c", "users", os.environ.get("USER", "steamuser"),
                              "AppData", "LocalLow", "VRChat", "VRChat"))

    return bases


def _find_log() -> str | None:
    all_logs = []
    for base in _log_search_bases():
        all_logs.extend(glob.glob(os.path.join(base, "output_log_*.txt")))
    if not all_logs:
        return None
    all_logs.sort(key=os.path.getmtime)
    return all_logs[-1]

def _poll():
    global _players
    last_log = None
    last_pos = 0

    while True:
        log = _find_log()
        if not log:
            time.sleep(5)
            continue
        try:
            with open(log, "r", encoding="utf-8", errors="ignore") as f:
                if log != last_log:
                    last_log = log
                    last_pos = 0
                    with _lock:
                        _data["vrc_world"]        = None
                        _data["vrc_avatar"]       = None
                        _data["vrc_player_count"] = 0
                        _data["vrc_fps"]          = None
                        _data["vrc_ping"]         = None
                    _players = set()

                f.seek(last_pos)

                while True:
                    line = f.readline()
                    if not line:
                        last_pos = f.tell()
                        new_log = _find_log()
                        if new_log and new_log != last_log:
                            break
                        time.sleep(0.3)
                        continue

                    line = line.strip()

                    m = _RE_WORLD.search(line)
                    if m:
                        with _lock:
                            _data["vrc_world"] = m.group(1).strip()
                            _data["vrc_player_count"] = 0
                        _players = set()
                        continue

                    m = _RE_JOIN.search(line)
                    if m:
                        _players.add(m.group(1).strip())
                        with _lock:
                            _data["vrc_player_count"] = len(_players)
                        continue

                    m = _RE_LEAVE.search(line)
                    if m:
                        _players.discard(m.group(1).strip())
                        with _lock:
                            _data["vrc_player_count"] = len(_players)
                        continue

                    m = _RE_AVATAR.search(line)
                    if m:
                        with _lock:
                            _data["vrc_avatar"] = m.group(1).strip()
                        continue

                    if _RE_STATS.match(line):
                        fps, ping = _parse_stats(line)
                        with _lock:
                            if fps is not None:
                                _data["vrc_fps"] = fps
                            if ping is not None:
                                _data["vrc_ping"] = ping
                        continue

        except Exception as e:
            print(f"[vrchat monitor] error: {e}")
            time.sleep(2)

_started = False

def start():
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_poll, daemon=True).start()
    threading.Thread(target=_start_osc_server, daemon=True).start()

def snapshot() -> dict:
    with _lock:
        return dict(_data)