"""
ui/help_dialog.py
─────────────────
Paginated help window for VRChat Local Favorites.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from ui import theme

HELP_PAGES = [
    {
        "title": "Welcome",
        "content": (
            "VRChat Local Favorites stores as many favorites as you want, "
            "in as many groups as you want, entirely on your own computer — "
            "no 50-slot cap, no VRC+ needed.\n\n"
            "Each group is just a JSON file on disk, organized by "
            "category: Worlds, Avatars, Players, and Instances."
        ),
    },
    {
        "title": "Groups",
        "content": (
            "Make as many groups as you like per category — \"Chill "
            "Worlds\", \"Cursed Avatars\", whatever makes sense to you. "
            "The same favorite can live in more than one group at once.\n\n"
            "Right-click a group to rename or delete it. Deleting a group "
            "only removes that group's file — the same item in another "
            "group is untouched."
        ),
    },
    {
        "title": "Adding a favorite",
        "content": (
            "Worlds and Players can be searched by name. Avatars and "
            "Instances can't be searched (VRChat's own API doesn't allow "
            "it) — paste an ID or a vrchat.com link instead.\n\n"
            "For instances specifically, you need a link someone already "
            "gave you (or one from your own recent history) — this tool "
            "never scans or browses instances to find one for you."
        ),
    },
    {
        "title": "Launching & switching",
        "content": (
            "Worlds and Instances get a Launch/Join button that opens a "
            "vrchat.com link — your browser hands it to the installed "
            "VRChat client. If nothing happens, VRChat's own link handler "
            "may not be registered; the page that opens has a manual "
            "Launch button as a fallback.\n\n"
            "Avatars get a \"Change Into This Avatar\" button that calls "
            "VRChat's own API directly. This only works for avatars you "
            "own or that are already in your real (capped) VRChat avatar "
            "favorites — if it fails, this tool opens the avatar's page on "
            "the website instead, where you can view or favorite it "
            "properly."
        ),
    },
    {
        "title": "Players",
        "content": (
            "You can favorite any user by ID or search, friend or not. "
            "This is just a personal bookmark of their profile page — it "
            "does not show you their location, online status, or "
            "anything else VRChat doesn't already show you for a "
            "non-friend. For live friend activity or location, use "
            "VRChat Social Logger instead."
        ),
    },
    {
        "title": "Account & Privacy",
        "content": (
            "Logging in uses VRChat's own account authentication. Your "
            "password is never stored — only the resulting session "
            "cookie, which you can protect with your OS credential store "
            "or a master password in Settings. Log out any time."
        ),
    },
]


def open_help(parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle("VRChat Local Favorites - Help")
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
