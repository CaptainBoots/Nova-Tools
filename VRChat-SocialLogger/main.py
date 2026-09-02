import os
import subprocess
import sys

VERSION = "1.0.0"
NAME = "VRChat SocialLogger"

# ── Dependency bootstrap (Isolated Virtual Environment) ───────────────────────

def _ensure_venv():
    import shutil

    script_dir = os.path.dirname(os.path.abspath(__file__))
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
        # We are already in our local venv, so let imports proceed!
        return

    # We are NOT inside the local venv. Check if it's already created and working on the right version.
    venv_working = False
    if os.path.exists(venv_python):
        try:
            # Verify the venv python interpreter actually works and matches outer major/minor version
            version_bytes = subprocess.check_output(
                [venv_python, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
                stderr=subprocess.DEVNULL,
            ).strip()
            venv_version = version_bytes.decode("utf-8")
            outer_version = f"{sys.version_info[0]}.{sys.version_info[1]}"
            if venv_version == outer_version:
                venv_working = True
            else:
                print(f"[setup] Python version mismatch (venv: {venv_version}, outer: {outer_version}). Rebuilding venv...")
        except Exception:
            print(f"[setup] Existing virtual environment is invalid or broken. Re-creating...")
            try:
                shutil.rmtree(venv_dir, ignore_errors=True)
            except Exception as e:
                print(f"[setup] Error clearing broken venv directory: {e}")

    # Create the virtual environment if it does not exist or was broken
    if not venv_working or not os.path.exists(venv_dir):
        print(f"[setup] Creating virtual environment at {venv_dir}...")
        try:
            subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        except Exception as e:
            print(f"[setup] Failed to create virtual environment: {e}")
            sys.exit(1)

    # Install/update dependencies from dependency.txt
    dep_file = os.path.join(script_dir, "dependency.txt")
    sentinel_file = os.path.join(venv_dir, "installed.sentinel")
    
    needs_install = True
    if os.path.exists(sentinel_file) and os.path.exists(dep_file):
        if os.path.getmtime(dep_file) <= os.path.getmtime(sentinel_file):
            needs_install = False

    if needs_install and os.path.exists(dep_file):
        print(f"[setup] Installing/updating dependencies from dependency.txt...")
        try:
            # Upgrade pip inside the venv first
            subprocess.check_call(
                [venv_python, "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Install the requirements
            subprocess.check_call(
                [venv_python, "-m", "pip", "install", "--quiet", "-r", dep_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Write sentinel file to record successful installation
            with open(sentinel_file, "w") as f:
                f.write("OK")
        except Exception as e:
            print(f"[setup] Error installing dependencies: {e}")

    # Relaunch script using the local venv's Python interpreter
    cmd = [venv_python, os.path.abspath(__file__)] + sys.argv[1:]
    try:
        if sys.platform == "win32":
            code = subprocess.call(cmd)
            sys.exit(code)
        else:
            os.execv(venv_python, [venv_python, os.path.abspath(__file__)] + sys.argv[1:])
    except Exception as e:
        print(f"[setup] Failed to handoff execution to virtual environment: {e}")
        sys.exit(1)


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    _ensure_venv()

    from config import load_config
    from ui import theme
    theme.set_theme(load_config().get("theme_mode", "rich_purple"))

    from PySide6.QtWidgets import QApplication
    qt_app = QApplication(sys.argv)
    qt_app.setStyleSheet(theme.qss())

    from ui.app import App
    win = App()
    win.show()
    sys.exit(qt_app.exec())