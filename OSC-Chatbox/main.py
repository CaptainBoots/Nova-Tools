import os
import subprocess
import sys
import json

VERSION = "1.0.4"
NAME = "ChatBox"
TOOL_ID = "000101"


# ── Dependency bootstrap (Isolated Virtual Environment) ───────────────────────

def _ensure_venv():
    import shutil
    import os
    import sys
    import subprocess
    cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0

    script_dir = os.path.dirname(os.path.abspath(__file__))
    is_toolbox = os.environ.get("TOOLBOX_MANAGED") == "1"

    # If managed by toolbox, use the parent repo's shared venv
    if is_toolbox:
        venv_dir = os.path.join(os.path.dirname(script_dir), ".venv")
    else:
        venv_dir = os.path.join(script_dir, ".venv")

    # Path to virtual environment python
    if sys.platform == "win32":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")

    # Detect if we are already running inside our local .venv
    is_in_venv = False
    if hasattr(sys, "real_prefix") or (sys.base_prefix != sys.prefix):
        is_in_venv = os.path.abspath(sys.executable).lower() == os.path.abspath(venv_python).lower()

    if is_in_venv:
        return

    # If run via Toolbox, assume the shared venv is fully built. Handoff immediately.
    if is_toolbox and os.path.exists(venv_python):
        cmd = [venv_python, os.path.abspath(__file__)] + sys.argv[1:]
        try:
            if sys.platform == "win32":
                code = subprocess.call(cmd, creationflags=cflags)
                sys.exit(code)
            else:
                os.execv(venv_python, cmd)
        except Exception as e:
            print(f"[setup] Failed to handoff execution to virtual environment: {e}")
            sys.exit(1)

    # Standalone mode: Check if it's already created and working on the right version.
    venv_working = False
    if os.path.exists(venv_python):
        try:
            version_bytes = subprocess.check_output(
                [venv_python, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
                stderr=subprocess.DEVNULL,
                creationflags=cflags
            ).strip()
            venv_version = version_bytes.decode("utf-8")
            outer_version = f"{sys.version_info[0]}.{sys.version_info[1]}"
            if venv_version == outer_version:
                venv_working = True
            else:
                print(
                    f"[setup] Python version mismatch (venv: {venv_version}, outer: {outer_version}). Rebuilding venv...")
        except Exception:
            print(f"[setup] Existing virtual environment is invalid or broken. Re-creating...")
            try:
                shutil.rmtree(venv_dir, ignore_errors=True)
            except Exception as e:
                print(f"[setup] Error clearing broken venv directory: {e}")

    # Create the virtual environment if it does not exist or was broken
    if not venv_working or not os.path.exists(venv_dir):
        print(f"[setup] Creating standalone virtual environment at {venv_dir}...")
        try:
            subprocess.check_call([sys.executable, "-m", "venv", venv_dir], creationflags=cflags)
        except Exception as e:
            print(f"[setup] Failed to create virtual environment: {e}")
            sys.exit(1)

    # Install/update dependencies from dependency.txt
    dep_file = os.path.join(script_dir, "dependency.txt")
    sentinel_file = os.path.join(venv_dir, f"installed_{TOOL_ID}.sentinel")

    needs_install = True
    if os.path.exists(sentinel_file) and os.path.exists(dep_file):
        if os.path.getmtime(dep_file) <= os.path.getmtime(sentinel_file):
            needs_install = False

    if needs_install and os.path.exists(dep_file):
        print(f"[setup] Installing standalone dependencies from dependency.txt...")
        try:
            subprocess.check_call([venv_python, "-m", "pip", "install", "--quiet", "-r", dep_file],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,
                                  creationflags=cflags
                                  )
            with open(sentinel_file, "w") as f:
                f.write("OK")
        except Exception as e:
            print(f"[setup] Error installing dependencies: {e}")

    # Relaunch script using the local venv's Python interpreter
    cmd = [venv_python, os.path.abspath(__file__)] + sys.argv[1:]
    try:
        if sys.platform == "win32":
            code = subprocess.call(cmd, creationflags=cflags)
            sys.exit(code)
        else:
            os.execv(venv_python, cmd)
    except Exception as e:
        print(f"[setup] Failed to handoff execution to virtual environment: {e}")
        sys.exit(1)


# ── Media worker bridge (root → user) ─────────────────────────────────────────

from core.media_bridge import fetch_media, shutdown_media_worker

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _ensure_venv()

    from config import load_config
    from ui import theme
    from core.media_bridge import _spawn_media_worker, shutdown_media_worker

    cfg = load_config()
    theme.set_theme(cfg.get("theme_mode", "rich_purple"))

    # Qt needs exactly one QApplication instance, created before any window
    # or dialogue is constructed.
    from PySide6.QtWidgets import QApplication

    qt_app = QApplication(sys.argv)
    qt_app.setStyleSheet(theme.qss())

    # Spawn media worker if running as root/admin
    _spawn_media_worker()

    from monitors import steamvr, vrchat, channels

    steamvr.start()
    vrchat.start()
    channels.start()

    from ui.app import App

    app = App()

    try:
        app.run()
    finally:
        shutdown_media_worker()