"""
ui/help_dialog.py
─────────────────
Paginated help window for OSC-Gamepad.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from ui import theme

HELP_PAGES = [
    {
        "title": "Getting Started",
        "content": (
            "OSC Gamepad lets you control your VRChat avatar using\n"
            "on-screen buttons and joysticks, sent over OSC.\n\n"
            "1. Make sure VRChat is running with OSC enabled.\n"
            "   (Action Menu → Options → OSC → Enabled)\n\n"
            "2. Click + Add Pad to create a new pad.\n\n"
            "3. Set the Host and Port to match your VRChat OSC\n"
            "   settings. Default is 127.0.0.1 : 9000 for a\n"
            "   local game instance.\n\n"
            "4. Click Connect. The status dot turns green\n"
            "   when active.\n\n"
            "5. Use the pad controls to move and interact.\n\n"
            "Your pad layout and connection settings are saved\n"
            "automatically when you close the app."
        ),
    },
    {
        "title": "NES Pad Mode",
        "content": (
            "NES mode gives you a classic D-pad layout.\n\n"
            "D-PAD (top-left)\n"
            "  ▲ ▼ ◀ ▶ — Move forward, back, left, right.\n\n"
            "LOOK (bottom-left)\n"
            "  ◀ ▶ — Rotate camera left / right.\n"
            "  ▲ ▼ — Look up / down.\n"
            "  Hold a button to keep looking that direction.\n\n"
            "ACTION BUTTONS (right side)\n"
            "  JUMP — Jump. Fires once per press.\n"
            "  GRAB — Hold to grab objects or players.\n"
            "  USE  — Interact with world objects.\n"
            "  MENU — Toggle the Quick Menu.\n"
            "  MUTE — Toggle microphone mute.\n\n"
            "TOGGLE BUTTONS\n"
            "  SIT    — Toggles Seated avatar parameter.\n"
            "  CROUCH — Toggles Crouching avatar parameter.\n"
            "  Active toggles stay highlighted in purple."
        ),
    },
    {
        "title": "Joystick Mode",
        "content": (
            "Joystick mode replaces the D-pad with an analogue\n"
            "stick and sliders.\n\n"
            "ANALOGUE STICK (circle canvas)\n"
            "  Click and drag inside the circle to move.\n"
            "  Snaps back to centre on release.\n"
            "  Movement is proportional — drag further for\n"
            "  faster movement.\n\n"
            "LOOK H / LOOK V SLIDERS\n"
            "  Drag to rotate camera / look up-down.\n"
            "  Returns to centre on release.\n\n"
            "ACTION BUTTONS (right side)\n"
            "  Same as NES mode — JUMP, GRAB, USE, MENU,\n"
            "  MUTE, SIT, CROUCH.\n\n"
            "Useful for smoother, variable-speed movement\n"
            "instead of binary on/off inputs."
        ),
    },
    {
        "title": "Multiple Pads",
        "content": (
            "You can run as many pads as you like at once.\n\n"
            "Each pad is independent and can have its own:\n"
            "  • Custom name (click the name field to edit)\n"
            "  • Host and Port\n"
            "  • NES or Joystick style\n\n"
            "USE CASES\n"
            "  • One pad for movement, another for actions.\n"
            "  • Control two VRChat instances on the same PC\n"
            "    (e.g. one on port 9000, one on port 9001).\n"
            "  • Send OSC to another app on a different port\n"
            "    alongside VRChat.\n\n"
            "REMOVING A PAD\n"
            "  Click the ✕ in the pad's header.\n"
            "  This also disconnects the OSC client cleanly.\n\n"
            "All pad configs are saved to gamepad_config.json\n"
            "and restored on next launch."
        ),
    },
    {
        "title": "OSC Reference",
        "content": (
            "OSC addresses used by this app:\n\n"
            "  /input/Vertical          Float -1.0 to 1.0\n"
            "  /input/Horizontal        Float -1.0 to 1.0\n"
            "  /input/LookHorizontal    Float -1.0 to 1.0\n"
            "  /input/LookVertical      Float -1.0 to 1.0\n"
            "  /input/Jump              Int   0 or 1\n"
            "  /input/Grab              Int   0 or 1\n"
            "  /input/Use               Int   0 or 1\n"
            "  /input/QuickMenuToggleLeft  Int  0 or 1\n"
            "  /input/Voice             Int   0 or 1\n\n"
            "  /avatar/parameters/Seated     Bool\n"
            "  /avatar/parameters/Crouching  Bool\n\n"
            "Axis and button messages are sent on a 50ms loop\n"
            "(20Hz) while the pad is connected. Toggle\n"
            "parameters are sent once on click.\n\n"
            "Default VRChat OSC port: 9000 (incoming to VRChat)"
        ),
    },
]


def open_help(parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle("OSC-Gamepad Help")
    dlg.resize(parent.size())

    root = QVBoxLayout(dlg)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    current = [0]

    hdr = QWidget()
    hdr.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
    hdr_layout = QHBoxLayout(hdr)
    hdr_layout.setContentsMargins(16, 10, 16, 10)

    title_lbl = QLabel("")
    title_lbl.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
    title_lbl.setFont(theme.qt_font(12, bold=True))
    hdr_layout.addWidget(title_lbl)
    hdr_layout.addStretch(1)

    page_lbl = QLabel("")
    page_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    page_lbl.setFont(theme.qt_font(8))
    hdr_layout.addWidget(page_lbl)

    root.addWidget(hdr)

    divider = QFrame()
    divider.setFixedHeight(1)
    divider.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
    root.addWidget(divider)

    content_panel = QFrame()
    content_panel.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
    content_layout = QVBoxLayout(content_panel)
    content_layout.setContentsMargins(16, 14, 16, 14)

    content_lbl = QLabel("")
    content_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
    content_lbl.setFont(theme.qt_font(10))
    content_lbl.setWordWrap(True)
    content_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    content_layout.addWidget(content_lbl)

    body_wrap = QWidget()
    body_wrap_layout = QVBoxLayout(body_wrap)
    body_wrap_layout.setContentsMargins(20, 14, 20, 0)
    body_wrap_layout.addWidget(content_panel)
    root.addWidget(body_wrap, 1)

    nav = QHBoxLayout()
    nav.setContentsMargins(20, 8, 20, 14)

    prev_btn = QPushButton("← Back")
    prev_btn.setStyleSheet(theme.subtle_button_qss())
    prev_btn.setFont(theme.qt_font(9, bold=True))
    prev_btn.setFixedWidth(100)
    nav.addWidget(prev_btn)
    nav.addStretch(1)

    next_btn = QPushButton("Next →")
    next_btn.setStyleSheet(theme.accent_button_qss())
    next_btn.setFont(theme.qt_font(9, bold=True))
    next_btn.setFixedWidth(100)
    nav.addWidget(next_btn)

    root.addLayout(nav)

    def show(idx):
        p = HELP_PAGES[idx]
        title_lbl.setText(p["title"])
        content_lbl.setText(p["content"])
        page_lbl.setText(f"{idx + 1} / {len(HELP_PAGES)}")
        prev_btn.setEnabled(idx > 0)
        next_btn.setText("Close" if idx == len(HELP_PAGES) - 1 else "Next →")

    def go_back():
        if current[0] > 0:
            current[0] -= 1
            show(current[0])

    def next_or_close():
        if current[0] < len(HELP_PAGES) - 1:
            current[0] += 1
            show(current[0])
        else:
            dlg.close()

    prev_btn.clicked.connect(go_back)
    next_btn.clicked.connect(next_or_close)

    show(0)
    dlg.exec()