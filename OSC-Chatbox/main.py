import os
import subprocess
import sys

VERSION = "8.5.8"
NAME = "ChatBox"

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


# ── Ensure we can find our own modules ───────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ── LHM startup helpers ───────────────────────────────────────────────────────

def _lhm_exe_path() -> str:
    """Resolve the LHM exe path relative to the VRChat-Tools root."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tools_root = os.path.dirname(script_dir)          # VRChat-Tools/
    toolbox_root = os.path.dirname(tools_root)         # same level as VRChat-Tools/
    # Try both: tools root sibling and tools root child
    candidates = [
        os.path.join(tools_root, "LibreHardwareMonitor", "LibreHardwareMonitor.exe"),
        os.path.join(toolbox_root, "VRChat-Tools", "LibreHardwareMonitor", "LibreHardwareMonitor.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return candidates[0]  # return primary path even if missing (will error on launch)


def _patch_lhm_config() -> None:
    """
    Ensure the LHM .config file has the required keys set before launch.
    Sets:
      runWebServerMenuItem = true   (enables the web API on port 8085)
      startMinMenuItem     = true   (starts minimised to tray)
    Creates the config from scratch if it doesn't exist yet.
    """
    import xml.etree.ElementTree as ET

    lhm_dir  = os.path.dirname(_lhm_exe_path())
    cfg_path = os.path.join(lhm_dir, "LibreHardwareMonitor.config")

    REQUIRED_KEYS = {
        "runWebServerMenuItem": "true",
        "startMinMenuItem":     "true",
    }

    if os.path.isfile(cfg_path):
        try:
            tree = ET.parse(cfg_path)
            root = tree.getroot()
        except ET.ParseError as e:
            print(f"[LHM] Config parse error ({e}), will recreate.")
            root = ET.Element("configuration")
            tree = ET.ElementTree(root)
    else:
        print("[LHM] No config found, creating one.")
        root = ET.Element("configuration")
        tree = ET.ElementTree(root)

    app_settings = root.find("appSettings")
    if app_settings is None:
        app_settings = ET.SubElement(root, "appSettings")

    for key, value in REQUIRED_KEYS.items():
        node = app_settings.find(f"./add[@key='{key}']")
        if node is not None:
            if node.get("value") != value:
                print(f"[LHM] Config: setting {key} = {value} (was {node.get('value')})")
                node.set("value", value)
        else:
            print(f"[LHM] Config: inserting {key} = {value}")
            ET.SubElement(app_settings, "add", key=key, value=value)

    try:
        tree.write(cfg_path, encoding="utf-8", xml_declaration=True)
        print(f"[LHM] Config written to {cfg_path}")
    except Exception as e:
        print(f"[LHM] Could not write config: {e}")


def _lhm_theme_colours():
    """Small shared helper: pull theme colours/font for the two popups
    below, with a hardcoded fallback if ui.theme isn't importable yet."""
    try:
        from ui.theme import BG, PANEL, BORDER, ACCENT, ACCENT2, TEXT, SUBTEXT, qt_font
        return BG, PANEL, BORDER, ACCENT, ACCENT2, TEXT, SUBTEXT, qt_font
    except Exception:
        from PySide6.QtGui import QFont

        def qt_font(size, bold=False):
            f = QFont("Consolas", size)
            if bold:
                f.setBold(True)
            return f

        return (
            "#0f0f13", "#1f102a", "#2a2a38", "#9D00FF", "#b44bff",
            "#e2e0f0", "#7e7b9a", qt_font,
        )


def _show_lhm_started_popup() -> None:
    """Small confirmation popup shown after LHM launches successfully."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

    BG, PANEL, BORDER, ACCENT, ACCENT2, TEXT, SUBTEXT, qt_font = _lhm_theme_colours()

    popup = QDialog()
    popup.setWindowTitle("Libre Hardware Monitor")
    popup.setStyleSheet(f"background-color: {BG};")

    root_layout = QVBoxLayout(popup)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    hdr = QWidget()
    hdr.setStyleSheet(f"background-color: {PANEL};")
    hdr_layout = QHBoxLayout(hdr)
    hdr_layout.setContentsMargins(14, 8, 14, 8)
    title_lbl = QLabel("Libre Hardware Monitor")
    title_lbl.setStyleSheet(f"color: {ACCENT2}; background: transparent;")
    title_lbl.setFont(qt_font(11, bold=True))
    hdr_layout.addWidget(title_lbl)
    root_layout.addWidget(hdr)

    divider = QWidget()
    divider.setFixedHeight(1)
    divider.setStyleSheet(f"background-color: {BORDER};")
    root_layout.addWidget(divider)

    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(20, 14, 20, 14)
    msg = QLabel(
        "✓  LHM started successfully.\n\n"
        "It will appear in your system tray shortly.\n"
        "The UAC prompt may have appeared behind this window."
    )
    msg.setStyleSheet(f"color: {TEXT}; background: transparent;")
    msg.setFont(qt_font(9))
    body_layout.addWidget(msg)

    ok_btn = QPushButton("OK")
    ok_btn.setStyleSheet(
        f"QPushButton {{ background-color: {ACCENT}; color: {BG}; padding: 4px 16px; font-weight: bold; }}"
    )
    ok_btn.setFont(qt_font(9, bold=True))
    ok_btn.clicked.connect(popup.accept)
    body_layout.addWidget(ok_btn, alignment=Qt.AlignCenter)

    root_layout.addWidget(body)

    popup.exec()


def _launch_lhm():
    exe = _lhm_exe_path()
    if not os.path.isfile(exe):
        print(f"[LHM] exe not found at {exe} — skipping launch")
        return

    # Patch config before every launch so settings are always correct
    _patch_lhm_config()

    try:
        if sys.platform == "win32":
            import ctypes
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", exe, None, os.path.dirname(exe), 1
            )
            if ret <= 32:
                print(f"[LHM] ShellExecuteW returned {ret} (elevation denied or failed)")
                return
            else:
                print(f"[LHM] Launched with admin elevation")
        else:
            subprocess.Popen([exe], cwd=os.path.dirname(exe))
            print(f"[LHM] Launched")

        _show_lhm_started_popup()
    except Exception as e:
        print(f"[LHM] Launch failed: {e}")


def _show_lhm_prompt(cfg: dict, save_cfg_cb) -> bool:
    """
    Show a popup asking whether to start LHM.
    Returns True if LHM should be launched.
    Saves preference back to config if user picks always/never.
    """
    from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton

    BG, PANEL, BORDER, ACCENT, ACCENT2, TEXT, SUBTEXT, qt_font = _lhm_theme_colours()

    result = {"launch": False}

    popup = QDialog()
    popup.setWindowTitle("Libre Hardware Monitor")
    popup.setStyleSheet(f"background-color: {BG};")

    root_layout = QVBoxLayout(popup)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    # Header
    hdr = QWidget()
    hdr.setStyleSheet(f"background-color: {PANEL};")
    hdr_layout = QHBoxLayout(hdr)
    hdr_layout.setContentsMargins(16, 10, 16, 10)
    title_lbl = QLabel("Libre Hardware Monitor")
    title_lbl.setStyleSheet(f"color: {ACCENT2}; background: transparent;")
    title_lbl.setFont(qt_font(12, bold=True))
    hdr_layout.addWidget(title_lbl)
    root_layout.addWidget(hdr)

    divider = QWidget()
    divider.setFixedHeight(1)
    divider.setStyleSheet(f"background-color: {BORDER};")
    root_layout.addWidget(divider)

    # Body
    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(24, 16, 24, 16)
    msg = QLabel(
        "Would you like to start Libre Hardware Monitor?\n"
        "LHM provides GPU & CPU temperature data for the ChatBox."
    )
    msg.setStyleSheet(f"color: {TEXT}; background: transparent;")
    msg.setFont(qt_font(9))
    msg.setWordWrap(True)
    body_layout.addWidget(msg)

    # Buttons
    btn_grid = QGridLayout()

    def _do(choice: str):
        """choice: 'start' | 'always' | 'dismiss' | 'never'"""
        if choice in ("start", "always"):
            result["launch"] = True
        if choice == "always":
            cfg["lhm_prompt"] = "always"
            save_cfg_cb(cfg)
        elif choice == "never":
            cfg["lhm_prompt"] = "never"
            save_cfg_cb(cfg)
        popup.accept()

    def _mk_btn(text, bg, fg):
        b = QPushButton(text)
        b.setFont(qt_font(9, bold=True))
        b.setStyleSheet(
            f"QPushButton {{ background-color: {bg}; color: {fg}; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background-color: {BORDER}; }}"
        )
        return b

    start_btn = _mk_btn("▶  Start LHM", ACCENT, TEXT)
    start_btn.clicked.connect(lambda: _do("start"))
    btn_grid.addWidget(start_btn, 0, 0)

    always_btn = _mk_btn("▶  Always Start", PANEL, TEXT)
    always_btn.clicked.connect(lambda: _do("always"))
    btn_grid.addWidget(always_btn, 0, 1)

    dismiss_btn = _mk_btn("✕  Dismiss", PANEL, SUBTEXT)
    dismiss_btn.clicked.connect(lambda: _do("dismiss"))
    btn_grid.addWidget(dismiss_btn, 1, 0)

    never_btn = _mk_btn("✕  Never Ask Again", PANEL, SUBTEXT)
    never_btn.clicked.connect(lambda: _do("never"))
    btn_grid.addWidget(never_btn, 1, 1)

    body_layout.addLayout(btn_grid)
    root_layout.addWidget(body)

    popup.exec()
    return result["launch"]


def _handle_lhm_startup(cfg: dict, save_cfg_cb):
    """Check lhm_prompt preference and act accordingly."""
    pref = cfg.get("lhm_prompt", "ask")
    if pref == "always":
        print("[LHM] Auto-starting (always)")
        _launch_lhm()
    elif pref == "never":
        print("[LHM] Skipping (never)")
    else:  # "ask"
        if _show_lhm_prompt(cfg, save_cfg_cb):
            _launch_lhm()


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _ensure_venv()

    from config import load_config, save_config
    from ui import theme

    cfg = load_config()
    theme.set_theme(cfg.get("theme_mode", "rich_purple"))

    # Qt needs exactly one QApplication instance, created before any window
    # or dialog (including the LHM startup popups below) is constructed.
    from PySide6.QtWidgets import QApplication
    qt_app = QApplication(sys.argv)
    qt_app.setStyleSheet(theme.qss())

    if sys.platform == "win32":
        _handle_lhm_startup(cfg, save_config)

    from monitors import steamvr, vrchat, channels
    steamvr.start()
    vrchat.start()
    channels.start()

    from ui.app import App
    app = App()
    app.run()