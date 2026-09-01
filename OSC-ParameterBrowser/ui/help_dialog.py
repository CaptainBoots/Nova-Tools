"""
ui/help_dialog.py
─────────────────
Paginated help window for OSC Parameter Browser.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from ui import theme

HELP_PAGES = [
    {
        "title": "Getting Started",
        "content": (
            "OSC Parameter Browser listens for incoming OSC packets\n"
            "and shows every address, value, and type it sees —\n"
            "useful for inspecting what VRChat (or any OSC app) is\n"
            "actually sending.\n\n"
            "Quick start:\n"
            "  1. Set Listen Port to the port you want to capture\n"
            "     traffic on (default: 9001).\n"
            "  2. Click Listen. The status dot turns green when\n"
            "     the socket is bound successfully.\n"
            "  3. Incoming parameters populate the table live,\n"
            "     sorted alphabetically by address.\n\n"
            "Click Clear Data to wipe the table without stopping\n"
            "the listener."
        ),
    },
    {
        "title": "Filtering",
        "content": (
            "Filter Address narrows the table to only addresses\n"
            "containing the text you type — useful once a busy\n"
            "avatar starts sending hundreds of parameters.\n\n"
            "The filter is live: the table updates on every\n"
            "keystroke, and matching is case-insensitive and\n"
            "matches anywhere in the address, not just the start.\n\n"
            "Example: typing 'Wing' would match both\n"
            "  /avatar/parameters/WingFlap\n"
            "  /avatar/parameters/LeftWing\n\n"
            "Clear the field to show everything again."
        ),
    },
    {
        "title": "Injecting Packets",
        "content": (
            "The Inject row lets you send a manual OSC packet —\n"
            "handy for testing an avatar parameter without\n"
            "triggering it in VRChat directly.\n\n"
            "  Inject Address — the OSC address to send to.\n"
            "  Val            — the value, entered as text.\n"
            "  Type           — float / int / bool / string.\n"
            "    bool accepts: true, 1, yes (anything else = false)\n\n"
            "Target IP / Send Port at the top control where the\n"
            "packet actually goes — usually 127.0.0.1 : 9000 for\n"
            "a local VRChat instance.\n\n"
            "Double-click any row in the table to copy that\n"
            "address, value, and type straight into the inject\n"
            "fields — a quick way to replay or tweak a captured\n"
            "value."
        ),
    },
    {
        "title": "Parameter Table",
        "content": (
            "Each row shows the latest value seen for one OSC\n"
            "address:\n\n"
            "  Path  — the full OSC address\n"
            "  Value — the most recent value received\n"
            "  Type  — float / int / bool / string\n"
            "  Ts    — timestamp of the last update (HH:MM:SS)\n\n"
            "The table only keeps the latest value per address,\n"
            "not a history — if you need to watch a value change\n"
            "over time, keep an eye on the Ts column to confirm\n"
            "it's still updating.\n\n"
            "Listen Port must be free — if it's already in use\n"
            "(e.g. another instance of this app, or VRChat itself\n"
            "listening there), the status bar will show a bind\n"
            "failure and the dot stays red."
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