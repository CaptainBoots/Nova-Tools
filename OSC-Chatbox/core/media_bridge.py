"""Media worker bridge — shared singleton for root→user media IPC."""

import os
import sys
import subprocess
import threading
import queue
import json
import time
import traceback


# EVERYTHING LOGGED
def _log(msg):
    print(f"[MEDIA-BRIDGE] {msg}", flush=True)


def _log_err(msg):
    print(f"[MEDIA-BRIDGE-ERR] {msg}", flush=True)
    traceback.print_exc()


# Shared singleton state
_media_worker = None
_media_ready = None
_media_queue = None


def _spawn_media_worker():
    """Spawn media worker as real user when running as root/admin."""
    global _media_worker, _media_ready, _media_queue
    _log(f"_spawn_media_worker called, _media_worker={_media_worker}")

    # Already spawned
    if _media_worker is not None:
        _log("Already spawned, returning True")
        return True

    # Determine if we're elevated
    is_root = (os.geteuid() == 0) if hasattr(os, "geteuid") else False
    is_admin = False
    if sys.platform == "win32" and not is_root:
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            pass

    if not (is_root or is_admin):
        _log("Not elevated, returning False")
        return False

    # Get real user UID
    real_uid = os.environ.get("SUDO_UID")
    _log(f"SUDO_UID={real_uid}, is_root={is_root}")
    if not real_uid and is_root:
        try:
            import pwd
            for u in pwd.getpwall():
                if u.pw_uid >= 1000 and u.pw_shell not in ("/usr/sbin/nologin", "/bin/false"):
                    real_uid = str(u.pw_uid)
                    _log(f"Found user: {real_uid}")
                    break
        except Exception as e:
            _log_err(f"Failed to find user: {e}")

    if not real_uid:
        _log("No real_uid found")
        return False

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    worker_script = os.path.join(script_dir, "media_worker.py")
    _log(f"worker_script={worker_script}, exists={os.path.exists(worker_script)}")

    if sys.platform == "win32":
        _log("Windows admin detected — not implemented")
        return False

    # Spawn as real user via sudo -u
    try:
        env = os.environ.copy()
        for key in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "PULSE_SERVER", "WAYLAND_DISPLAY", "DISPLAY"):
            if key in os.environ:
                env[key] = os.environ[key]

        if "DBUS_SESSION_BUS_ADDRESS" not in env:
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{real_uid}/bus"
        if "XDG_RUNTIME_DIR" not in env:
            env["XDG_RUNTIME_DIR"] = f"/run/user/{real_uid}"
        if "PULSE_SERVER" not in env:
            env["PULSE_SERVER"] = f"unix:/run/user/{real_uid}/pulse/native"

        _log(f"Spawning worker as user #{real_uid} with DBUS_SESSION_BUS_ADDRESS={env.get('DBUS_SESSION_BUS_ADDRESS')}")

        _media_worker = subprocess.Popen(
            ["sudo", "-u", f"#{real_uid}",
             "--preserve-env=XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS,PULSE_SERVER,WAYLAND_DISPLAY,DISPLAY", "--",
             sys.executable, worker_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        _log(f"_media_worker assigned: {_media_worker}, pid={_media_worker.pid}")

        # Read the "ready" message
        _media_queue = queue.Queue()
        _media_ready = threading.Event()

        def _read_stdout():
            for line in iter(_media_worker.stdout.readline, b''):
                try:
                    msg = json.loads(line.decode().strip())
                    _media_queue.put(msg)
                except json.JSONDecodeError:
                    pass

        threading.Thread(target=_read_stdout, daemon=True).start()

        def _read_stderr():
            for line in iter(_media_worker.stderr.readline, b''):
                print(f"[media-worker-stderr] {line.decode().strip()}")

        threading.Thread(target=_read_stderr, daemon=True).start()

        import time
        for _ in range(50):
            try:
                msg = _media_queue.get_nowait()
                if msg.get("type") == "ready":
                    _media_ready.set()
                    break
            except queue.Empty:
                pass
            time.sleep(0.1)

        if not _media_ready.is_set():
            _log("Worker failed to start")
            _media_worker.terminate()
            _media_worker = None
            return False

        _log(f"_spawn_media_worker returning True, _media_worker={_media_worker}")
        return True

    except Exception as e:
        _log_err(f"Failed to spawn worker: {e}")
        return False


def fetch_media():
    """Fetch media info from worker if running as root/admin, else direct."""
    global _media_worker
    _log(f"fetch_media called, _media_worker={_media_worker}")

    # Check worker exists and is alive atomically
    worker = _media_worker
    if worker is None:
        _log("No worker — running as user, use direct fetch")
        return None

    poll_result = worker.poll()
    _log(f"Worker poll: {poll_result}")
    if poll_result is not None:
        _log(f"Worker died with code {worker.returncode}")
        if _media_worker is worker:
            _media_worker = None
        return None

    try:
        _log("Sending fetch request")
        worker.stdin.write(b'{"type": "fetch"}\n')
        worker.stdin.flush()

        # Pull the response from the queue that _read_stdout() already
        # fills — reading worker.stdout directly here would race that
        # background thread for the same pipe (both calling readline()
        # on it), and the background thread almost always wins, which
        # is why fetches used to time out even though the worker had
        # already printed a perfectly good response.
        _log("Waiting on queue for response...")
        try:
            msg = _media_queue.get(timeout=1.0)
        except queue.Empty:
            _log("Worker timeout (1s)")
            return None

        _log(f"Got queue message: {msg}")

        if msg.get("type") == "media":
            data = msg.get("data")
            _log(
                f"Got: source={data.get('source', '?')} playing={not data.get('is_paused', True)} title={data.get('title', '')[:30]}")
            return data
    except Exception as e:
        _log_err(f"Fetch error: {e}")
    return None


def shutdown_media_worker():
    global _media_worker
    _log("shutdown_media_worker called")
    if _media_worker:
        try:
            _media_worker.stdin.write(b'{"type": "shutdown"}\n')
            _media_worker.stdin.flush()
        except Exception as e:
            _log_err(f"Shutdown write error: {e}")
        _media_worker.terminate()
        _media_worker = None
        _log("Worker terminated")