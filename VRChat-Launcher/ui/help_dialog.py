"""
ui/help_dialog.py
─────────────────
Paginated help window for VRChat Launcher.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from ui import theme

HELP_PAGES = [
    {
        "title": "Welcome",
        "content": (
            "Welcome to VRChat Launcher!\n\n"
            "This tool launches multiple VRChat instances side by side,\n"
            "each with its own OSC ports so they don't clash with one\n"
            "another.\n\n"
            "Use the profile list to manage each instance, and the\n"
            "panel on the right to edit a profile's settings."
        ),
    },
    {
        "title": "Profiles",
        "content": (
            "Profiles:\n\n"
            "• Click a profile's name to open its editor on the right\n"
            "• Name: a label to tell instances apart\n"
            "• Theme Color: used to colour that profile's name\n"
            "• OSC Destination Port: what VRChat sends OSC data to\n"
            "• OSC Source Bind Port: what VRChat listens for OSC on\n"
            "• Custom Launch Args: any extra flags appended to launch.exe\n\n"
            "+ Add Profile creates a new one with the next free port\n"
            "pair. Each profile needs at least 1 to remain."
        ),
    },
    {
        "title": "Launching",
        "content": (
            "Launching:\n\n"
            "1. Set LAUNCH EXE PATH to your VRChat launch.exe (Browse\n"
            "   finds it for you)\n"
            "2. Click Launch on a profile to start that instance\n"
            "3. The status dot turns green while it's running, and\n"
            "   turns red again once it closes\n"
            "4. Kill force-stops a running instance\n\n"
            "You must use launch.exe — launching VRChat.exe directly\n"
            "forces offline test mode."
        ),
    },
    {
        "title": "Instance Limit",
        "content": (
            "3-Instance Limit:\n\n"
            "VRChat allows a maximum of 3 simultaneous instances per\n"
            "public IP address. This is enforced server-side and can't\n"
            "be bypassed with launch arguments.\n\n"
            "Workarounds:\n"
            "• Use a VPN for each extra instance beyond 3\n"
            "• Run extra instances from a different network/hotspot\n\n"
            "The limit is per public IP, not per machine — so a second\n"
            "PC on the same home network still shares the same limit."
        ),
    },
    {
        "title": "Tips",
        "content": (
            "Tips & Tricks:\n\n"
            "• Profiles, the exe path, and your theme are all saved\n"
            "  automatically between launches\n"
            "• Closing this tool does not close any VRChat instances\n"
            "  you've already launched — they keep running\n"
            "• Give each profile a distinct OSC port pair if you're\n"
            "  running face tracking or other OSC tools alongside it\n\n"
            "For issues, check the exe path and confirm launch.exe\n"
            "actually exists at that location."
        ),
    },
]


def open_help(parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle("VRChat Launcher - Help")
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
    content_layout.setContentsMargins(16, 16, 16, 16)

    content_lbl = QLabel("")
    content_lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
    content_lbl.setFont(theme.qt_font(9))
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
        page_lbl.setText(f"Page {idx + 1} / {len(HELP_PAGES)}")
        prev_btn.setEnabled(idx > 0)
        next_btn.setText("Finish" if idx == len(HELP_PAGES) - 1 else "Next →")

    def go_back():
        if current[0] > 0:
            current[0] -= 1
            show(current[0])

    def next_or_finish():
        if current[0] < len(HELP_PAGES) - 1:
            current[0] += 1
            show(current[0])
        else:
            dlg.close()

    prev_btn.clicked.connect(go_back)
    next_btn.clicked.connect(next_or_finish)

    show(0)
    dlg.exec()
