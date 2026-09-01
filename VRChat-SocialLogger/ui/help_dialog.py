"""
ui/help_dialog.py
─────────────────
Paginated help window for VRChat Social Logger.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from ui import theme

HELP_PAGES = [
    {
        "title": "Welcome",
        "content": (
            "VRChat Social Logger keeps a local history of your own VRChat "
            "social activity: what your friends are up to, and what happens "
            "in the instance you're currently in.\n\n"
            "It only ever reads data VRChat already shares with you as the "
            "logged-in account it's signed in as — your own friends list and "
            "your own local game log. It never looks up an arbitrary user, "
            "and never scans public instances to find someone."
        ),
    },
    {
        "title": "Tab 1: Current Instance",
        "content": (
            "Shows the world, instance type, region, and population of "
            "whatever instance you're currently in, read from your local "
            "VRChat log — the same log your own client already writes.\n\n"
            "Below that, it lists which of your friends are also in this "
            "instance right now, from your friends list data. It never "
            "accepts a pasted-in instance ID for somewhere you aren't "
            "actually in — it always reflects your current session only."
        ),
    },
    {
        "title": "Tab 2: Friends Feed",
        "content": (
            "A running feed of your friends' status, location, and avatar "
            "changes, built from polling VRChat's own friends-list API — "
            "the same data the official app already shows you.\n\n"
            "Every event is also written to a rotating log file on disk "
            "(one file per day). Once the total size of these files passes "
            "the cap set in Settings, the oldest file is deleted "
            "automatically to make room, so this never grows unbounded."
        ),
    },
    {
        "title": "Tab 3: Current Instance Log",
        "content": (
            "The same feed-style view as the Friends Feed, but scoped to "
            "the instance you're currently in: players joining/leaving, "
            "avatar changes, and world transitions, parsed live from your "
            "own local VRChat log file.\n\n"
            "This also rotates to disk with its own size cap, independent "
            "of the Friends Feed's cap."
        ),
    },
    {
        "title": "What this tool won't do",
        "content": (
            "It won't search public instances for a specific user, won't "
            "look up someone by user ID/URL to find their location, and "
            "won't accept a list of instance IDs to check in bulk. That's "
            "a deliberate boundary, not a missing feature — see the "
            "Settings/README for why.\n\n"
            "'Ask Me' (orange) and 'Do Not Disturb' (red) friends won't "
            "show a real instance in the Friends Feed, matching VRChat's "
            "own privacy behavior for those statuses."
        ),
    },
    {
        "title": "Account & Privacy",
        "content": (
            "Logging in uses VRChat's own account authentication, the same "
            "as the official app or website. Your password is never stored "
            "— only the resulting session cookie is kept locally so you "
            "don't have to log in every launch. Log out any time from "
            "Settings."
        ),
    },
]


def open_help(parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle("VRChat Social Logger - Help")
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
