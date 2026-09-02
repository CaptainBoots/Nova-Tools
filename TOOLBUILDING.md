# VRChat Tools Development Guide

Welcome to the development guide for creating official VRChat OSC and utility tools. This document outlines the standards, naming conventions, directory structure, dependency management, and UI styling guidelines required to build high-quality, modern, and visually consistent tools for the VRChat-Tools ecosystem.

---

## 1. Project Directory Layout & Naming Conventions

All tools must follow a strict, standardized directory structure. This ensures that the codebase remains clean, maintainable, and easy to navigate.

### Directory Placement & Naming
- **Repository Location:** Every tool must be a top-level directory in the workspace root.
- **Naming Rule:** Directories must use kebab-case or pascal-case prefixed with `OSC-` or `VRChat-` depending on their domain:
  - `OSC-<ToolName>` for tools sending/receiving OSC data (e.g., `OSC-Chatbox`, `OSC-Gamepad`, `OSC-ParameterBrowser`).
  - `VRChat-<ToolName>` for pure utility/system tools (e.g., `VRChat-Launcher`, `VRChat-LocalFavorites`).

### Standard Directory Structure
Each tool must be organized as follows:

```text
OSC-MyNewTool/
├── .venv/                      # Local virtual environment (ignored in git)
├── core/                       # Core business logic and background threads
│   ├── __init__.py
│   ├── osc_io.py               # OSC input/output handlers
│   └── state.py                # Tool-specific state management
├── ui/                         # PySide6 GUI components
│   ├── __init__.py
│   ├── app.py                  # Main App (QMainWindow)
│   ├── circle_toggle.py        # Custom circular toggle widget
│   ├── my_tool_tab.py          # Primary tab/view of the tool
│   ├── settings_dialog.py      # Theme, port, and options config dialog
│   └── theme.py                # Visual theme registry, QSS builder, and fonts
├── __init__.py
├── config.py                   # Configuration I/O (JSON save/load)
├── dependency.txt              # Standard pip requirements
└── main.py                     # Entry point (bootstrap & venv auto-launcher)
```

---

## 2. Python 3.13 & Isolated Virtual Environments (`.venv`)

To prevent dependency conflicts between tools, every tool **must** operate inside its own local, isolated virtual environment (`.venv`) and run on **Python 3.13**. 

### Dependency Specification (`dependency.txt`)
All dependencies must be declared in a `dependency.txt` file in the tool's root directory (standardized over `requirements.txt`).
- Specify OS-specific packages where needed (e.g., Windows-specific APIs).
- Maintain PySide6 as the standard GUI toolkit.

Example `dependency.txt`:
```text
python-osc
psutil
requests
Pillow
PySide6
winrt-runtime; sys_platform == "win32"
winrt-Windows.Media.Control; sys_platform == "win32"
```

### Self-Bootstrapping Entry Point (`main.py`)
To make tools completely "plug-and-play", the entry point `main.py` must contain a self-bootstrapping mechanism that:
1. Detects if it is already running inside the tool's local `.venv`.
2. Creates `.venv` if it is missing or invalid.
3. Verifies that the `.venv` Python version matches the outer Python interpreter's major/minor version (rebuilding it if a mismatch is found).
4. Silently upgrades `pip` and installs/updates requirements from `dependency.txt` only when `dependency.txt` is updated (tracked via `installed.sentinel`).
5. Transparently relaunches itself inside the `.venv`.

#### Copy-Pasteable Bootstrap Template
Place this exact bootstrap logic at the very top of your `main.py`:

```python
"""
main.py
───────
Entry point and bootstrap script for the tool.
"""

import os
import subprocess
import sys

VERSION = "1.0.0"
NAME = "My New Tool"

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

    # Verify existing virtual environment
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


# ── Main Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    _ensure_venv()

    # Ensure we can find local imports
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from config import load_config, save_config
    from ui import theme
    from ui.app import App
    from PySide6.QtWidgets import QApplication

    cfg = load_config()
    theme.set_theme(cfg.get("theme_mode", "rich_purple"))

    # Instantiate Application
    qt_app = QApplication(sys.argv)
    qt_app.setStyleSheet(theme.qss())

    app = App()
    app.run()
```

---

## 3. Standard Global Variables

To allow launchers and tooling indexes to correctly read metadata from each tool, the top-level of `main.py` **must** declare two global variables:

1. `VERSION`: A string variable specifying the current semver release (e.g., `"1.2.0"`).
2. `NAME`: A short, user-friendly display name for the tool (e.g., `"Gamepad"`, `"Face Tracking Controller"`).

```python
VERSION = "1.2.0"
NAME = "Gamepad"
```

---

## 4. Styling & Theming with `theme.py`

Consistency is key to a cohesive user experience. All tools must integrate with the shared theme system defined in their local `ui/theme.py`. 

### Color Palette Registry
The theme registry uses module-level globals that are set dynamically by `theme.set_theme(theme_mode)`. Always use these variables rather than hardcoding hexadecimal values:

| Constant Name | Purpose / Application |
|:---|:---|
| `BG` | The main window background color (extremely dark/flat). |
| `PANEL` | Cards, module capsules, and container surfaces. |
| `BORDER` | Grid lines, separation dividers, and non-focused boundaries. |
| `ACCENT` | Principal interactive accent (buttons, checked state). |
| `ACCENT2` | Hover colors, title headings, and secondary indicators. |
| `TAB` | Selected text and focus indicators in navigation. |
| `TEXT` | Primary content text color. |
| `TEXT2` | Subheadings and emphasized details. |
| `SUBTEXT` | Unfocused text, descriptions, and placeholder hints. |
| `GREEN` | Success metrics, connected indicators, active states. |
| `RED` | Errors, disconnected states, and delete commands. |
| `YELLOW` | Warning logs and pending states. |
| `CYAN` / `ORANGE` | Auxiliary status or data visualization flags. |

### Font Standardization
Tools must use the monospace font family defined by the theme system to retain a retro, developer-centric terminal vibe:
- **Default Font:** `Consolas` (with fallback to system monospace).
- **Title Prefix Constant (`TITLE_PREFIX`):** `"◈"` (placed before header titles).
- **Font Resolver:** Use `theme.qt_font(size, bold=False)` to obtain a standard `QFont` instance.

```python
title_label.setFont(theme.qt_font(12, bold=True))
```

> [!WARNING]
> ### Crucial Qt Style Sheet Cascading Bug & Warning
> In PySide6 / Qt, **objectName-scoped global QSS rules get silently shadowed and ignored** if a widget is nested inside any ancestor widget that specifies its own `setStyleSheet()` call. In our layouts, almost every panel, row, or card calls `setStyleSheet()` to establish its own background color.
>
> To bypass this cascading quirk:
> 1. **Do not use objectName-scoped rules** (like `QPushButton#accentButton`) in `theme.qss()` for interactive nested elements.
> 2. **Apply styles inline** on the widgets themselves (e.g., using `widget.setStyleSheet(...)`) or use the inline stylesheet helper functions provided in `theme.py`.
> 3. Always include an explicit `border` property (like `border: none` or an explicit color) in your inline styles; otherwise, border styling can leak down from ancestor panels.

### Standard Inline Theme Stylesheets
Use these pre-built stylesheet helpers in `theme.py` when instantiating widgets:

```python
# Apply standard styles directly to controls
my_accent_btn.setStyleSheet(theme.accent_button_qss())
my_subtle_btn.setStyleSheet(theme.subtle_button_qss())
section_label.setStyleSheet(theme.section_caption_qss())
text_input.setStyleSheet(theme.line_edit_qss())
```

---

## 5. Core UI Component Templates

Use the following reference templates to build consistent, responsive, and robust PySide6 widgets.

### CircleToggle Widget (`circle_toggle.py`)
The circle toggle replaces ugly checkboxes with a high-fidelity retro toggle: filled = ON, outlined = OFF.

```python
"""
ui/circle_toggle.py
───────────────────
High-fidelity circular toggle widget for PySide6.
"""

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget
from ui import theme


class CircleToggle(QWidget):
    toggled = Signal(bool)

    DEFAULT_SIZE = 20
    DEFAULT_PAD = 3

    def __init__(self, parent=None, *, enabled: bool = True,
                 color: str = None, size: int = DEFAULT_SIZE,
                 pad: int = DEFAULT_PAD, command=None):
        super().__init__(parent)
        self._enabled = enabled
        self._color = QColor(color or theme.ACCENT2)
        self._size = size
        self._pad = pad
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        if command is not None:
            self.toggled.connect(command)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self._pad, self._pad,
                      self._size - 2 * self._pad, self._size - 2 * self._pad)
        if self._enabled:
            painter.setBrush(self._color)
            painter.setPen(Qt.NoPen)
        else:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(self._color, 2))
        painter.drawEllipse(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._enabled = not self._enabled
            self.update()
            self.toggled.emit(self._enabled)

    def get(self) -> bool:
        return self._enabled

    def set(self, value: bool):
        self._enabled = bool(value)
        self.update()

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()
```

### Main Window Structure (`app.py`)
This structure leverages a standard top title bar, clean vertical layouts, dividers, and a tabbed interface.

```python
"""
ui/app.py
─────────
Root Main Window configuration.
"""

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget
from ui import theme
from ui.circle_toggle import CircleToggle


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VRChat OSC Tool")
        self.setMinimumSize(480, 520)
        
        self._build_ui()

    def _build_root(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)
        
        # Header Row
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_lbl = QLabel(f"{theme.TITLE_PREFIX}  MY NEW TOOL")
        title_lbl.setFont(theme.qt_font(13, bold=True))
        title_lbl.setStyleSheet(f"color: {theme.ACCENT};")
        header_layout.addWidget(title_lbl)
        
        root_layout.addWidget(header)
        
        # Divider Line
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {theme.BORDER};")
        root_layout.addWidget(divider)
        
        # Main Tab Widget
        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)
        
    def _build_ui(self):
        self._build_root()
        
        # Example Tab Addition
        main_tab = QWidget()
        main_tab_layout = QVBoxLayout(main_tab)
        
        desc = QLabel("Welcome to the template tool.")
        desc.setFont(theme.qt_font(9))
        main_tab_layout.addWidget(desc)
        
        # Custom Circle Toggle integration
        toggle_row = QHBoxLayout()
        toggle_label = QLabel("Enable Feature X:")
        toggle_label.setFont(theme.qt_font(9))
        self.feature_toggle = CircleToggle(command=self._on_toggle)
        toggle_row.addWidget(toggle_label)
        toggle_row.addWidget(self.feature_toggle)
        toggle_row.addStretch()
        
        main_tab_layout.addLayout(toggle_row)
        main_tab_layout.addStretch()
        
        self.tabs.addTab(main_tab, "Control Panel")

    def _on_toggle(self, enabled: bool):
        print(f"Feature X state: {enabled}")

    def run(self):
        self.show()
        instance = QApplication.instance()
        if instance is not None:
            instance.exec()
```

---

## 6. Configuration Management (Save/Load Pattern)

All configuration must be written to/read from a shared sibling directory named `configs/` to keep user configurations decoupled from repository source trees. 

### Location Rules:
- **Config Directory:** Sibling directory to the tool folder (`configs/`).
- **Filename Pattern:** `<tool_slug_name>_config.json`.

### `config.py` Implementation Example
Keep your config handling clean and robust using JSON parsing with default fallbacks:

```python
"""
config.py
─────────
Unified config parsing with safe fallback policies.
"""

import json
import os

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR  = os.path.dirname(SCRIPT_DIR)
CONFIG_DIR  = os.path.join(PARENT_DIR, "configs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "mynewtool_config.json")


def get_defaults() -> dict:
    return {
        "theme_mode": "rich_purple",
        "feature_x_enabled": True,
        "osc_port": 9000
    }


def load_config() -> dict:
    defaults = get_defaults()
    try:
        if not os.path.exists(CONFIG_FILE):
            return defaults
            
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        if isinstance(loaded, dict):
            return {**defaults, **loaded}

        return defaults
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return defaults


def save_config(config_data: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        print(f"[Config] Configuration successfully saved.")
    except OSError as e:
        print(f"[Config] Failed to save configuration: {e}")
```

Using this unified format ensures that you remain aligned with the existing tools in this repository while avoiding common layout, virtual environment, dependency, and Qt style bugs!
