"""Media worker subprocess — runs as real user, continuously polls media, serves latest cached data instantly."""

import sys
import json
import asyncio
import os
import traceback
import time
from pathlib import Path

def _log(msg):
    print(f"[MEDIA-WORKER] {msg}", file=sys.stderr, flush=True)

def _log_err(msg):
    print(f"[MEDIA-WORKER-ERR] {msg}", file=sys.stderr, flush=True)
    traceback.print_exc()

sys.path.insert(0, str(Path(__file__).parent.parent))

_log(f"Starting worker PID={os.getpid()} UID={os.getuid()} EUID={os.geteuid()}")
for k in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "PULSE_SERVER", "WAYLAND_DISPLAY", "DISPLAY"):
    _log(f"{k}={os.environ.get(k)}")

# Shared state
_latest_media = {"title": "", "artist": "", "album": "", "album_artist": "", "track_number": None, "track_count": None, "source": "", "position_ms": 0, "duration_ms": 0, "is_paused": True}

async def _poll_loop():
    """Background poller - continuously updates _latest_media"""
    global _latest_media
    _log("Starting background poll loop")
    try:
        from monitors.media import fetch, empty
    except Exception as e:
        _log_err(f"Import fetch failed: {e}")
        return
    
    while True:
        try:
            _log("Polling fetch()...")
            start = time.time()
            info = await fetch()
            elapsed = time.time() - start
            _log(f"fetch() took {elapsed:.2f}s: {info.get('source', 'none')} {info.get('title', '')[:30]}")
            _latest_media = info if isinstance(info, dict) else empty()
        except Exception as e:
            _log_err(f"Poll fetch failed: {e}")
        await asyncio.sleep(2)

async def _run_worker():
    _log("Importing fetch")
    try:
        from monitors.media import fetch, empty
        _log("Imported fetch OK")
    except Exception as e:
        _log_err(f"Import fetch failed: {e}")
        return

    # Synchronous stdout for instant flush
    _log("Ready sent")
    print(json.dumps({"type": "ready"}), flush=True)

    # Start background poller
    poll_task = asyncio.create_task(_poll_loop())
    
    _log("Worker ready, entering command loop")
    
    # Command loop - read from stdin
    while True:
        try:
            _log("About to read stdin...")
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            _log(f"stdin.readline returned: {repr(line[:50])}")
            if not line:
                _log("EOF on stdin")
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                _log(f"JSON decode error: {e}, line={line[:50]}")
                continue

            if msg.get("type") == "fetch":
                _log(f"Serving cached: {_latest_media.get('source', 'none')} {_latest_media.get('title', '')[:30]}")
                print(json.dumps({"type": "media", "data": _latest_media}), flush=True)
            elif msg.get("type") == "shutdown":
                _log("Shutdown received")
                break
        except Exception as e:
            _log_err(f"Command loop error: {e}")
            break

    # Cleanup
    poll_task.cancel()
    _log("Worker exiting")

if __name__ == "__main__":
    try:
        asyncio.run(_run_worker())
    except Exception as e:
        _log_err(f"Fatal: {e}")