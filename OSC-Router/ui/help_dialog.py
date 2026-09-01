"""
ui/help_dialog.py
─────────────────
Paginated help window for OSC-Router.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from ui import theme

HELP_PAGES = [
    {
        "title": "Getting Started",
        "content": (
            "Welcome to OSC-Router!\n\n"
            "OSC-Router takes OSC messages from multiple\n"
            "sources and merges them into a single output\n"
            "stream — usually VRChat on port 9000.\n\n"
            "Quick start:\n"
            "  1. Add your source apps and their ports\n"
            "  2. Set the Output IP and Port\n"
            "     (defaults: 127.0.0.1 / 9000)\n"
            "  3. Press ▶ Start\n\n"
            "Any OSC app (Chatbox, Face Tracking, etc.)\n"
            "can send to the router instead of VRChat\n"
            "directly, and the router handles the merge."
        ),
    },
    {
        "title": "Sources",
        "content": (
            "Each source is an app or device that sends\n"
            "OSC messages to the router.\n\n"
            "Each source needs:\n"
            "  Name — a friendly label (e.g. 'Chatbox')\n"
            "  Port — the UDP port it listens on\n\n"
            "Defaults:\n"
            "  Chatbox:       port 9011\n"
            "  Face Tracking: port 9012\n\n"
            "Point your OSC apps at those ports instead\n"
            "of VRChat's 9000 port. The router will\n"
            "merge them and forward to the output.\n\n"
            "Click + Add Source to add more.\n"
            "Click ✕ to remove a source."
        ),
    },
    {
        "title": "Output",
        "content": (
            "Output IP — destination IP address.\n"
            "  Same PC:       127.0.0.1 (default)\n"
            "  Different PC:  use that machine's LAN IP\n\n"
            "Output Port — destination port.\n"
            "  VRChat default: 9000\n\n"
            "All merged OSC messages are forwarded\n"
            "to this single IP:Port destination.\n\n"
            "Tip: If VRChat is on this machine,\n"
            "leave both fields at their defaults."
        ),
    },
    {
        "title": "Priority & Conflicts",
        "content": (
            "Sources are listed with a priority number\n"
            "(#1 is highest priority).\n\n"
            "Merge rules:\n"
            "  • Different OSC addresses → all forwarded\n"
            "  • Same address, same value → sent once\n"
            "  • Same address, different value →\n"
            "    highest priority source wins\n\n"
            "Live Conflicts in the stats bar shows how\n"
            "many addresses are currently being contested\n"
            "between sources right now.\n\n"
            "The router runs at 20 Hz (every 50ms) and\n"
            "only forwards values that have changed,\n"
            "so it won't chatter the output."
        ),
    },
    {
        "title": "Live Stats",
        "content": (
            "The stats bar at the top shows:\n\n"
            "Forwarded — total OSC messages routed\n"
            "since the router was last started.\n\n"
            "Conflicts — number of OSC addresses\n"
            "currently being sent by more than one\n"
            "source with different values.\n\n"
            "Sources — how many are active vs total.\n\n"
            "Each source row shows:\n"
            "  ● 1,234 rx  — running, message count\n"
            "  ✗ failed    — could not bind the port\n"
            "                (port already in use)\n\n"
            "Stats update every second."
        ),
    },
]


def open_help(parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Info Page")
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