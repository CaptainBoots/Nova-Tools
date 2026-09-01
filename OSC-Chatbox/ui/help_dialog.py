"""
ui/help_dialog.py
──────────────────────
Qt replacement for ui/help_dialog.py. Same paged help content, same
back/next navigation, "Close" on the final page.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

try:
    from main import VERSION
except ImportError:
    VERSION = "version error"

from ui import theme

HELP_PAGES = [
    {
        "title": "Getting Started",
        "content": (
            f"Welcome to OSC-Chatbox Version: {VERSION}!\n\n"
            "OSC-Chatbox sends live system stats, weather, and media\n"
            "info to your VRChat chatbox via OSC.\n\n"
            "Quick start:\n"
            "  1. Set your OSC IP and Port in the Chatbox tab\n"
            "     (defaults: 127.0.0.1 / 9000)\n"
            "  2. Make sure OSC is enabled in VRChat\n"
            "     (Action Menu → Options → OSC → Enable)\n"
            "  3. Press ▶ Start\n\n"
            "The Builder tab lets you fully customise what each\n"
            "page shows and how long it stays on screen."
        ),
    },
    {
        "title": "The Builder Tab",
        "content": (
            "The Builder tab is where you design your pages.\n\n"
            "  All available data modules grouped by category.\n\n"
            "Right panel — Pages:\n"
            "  Each page is a card. Slots inside it are the lines\n"
            "  sent to VRChat in order.\n\n"
            "  ▲ ▼  — reorder slots\n"
            "  x    — remove a slot\n"
            "  +    — adds onto line\n"
            "  ⠿    — drag to reorder (grab and move up/down)\n\n"
            "  Custom Text slots have an inline text box so you\n"
            "  can type a fixed line directly in the slot.\n\n"
            "+ Add Page creates a new blank page."
        ),
    },
    {
        "title": "Pages & Duration",
        "content": (
            "Each page has its own Duration (in seconds).\n\n"
            "The chatbox rotates through your enabled pages,\n"
            "spending exactly that many seconds on each one\n"
            "before moving to the next.\n\n"
            "You can set different durations per page — for\n"
            "example, show your hardware stats for 30 seconds\n"
            "but your weather page for only 10 seconds.\n\n"
            "The checkbox on each page header enables or\n"
            "disables that page without deleting it.\n\n"
            "If ALL pages are disabled the chatbox will show\n"
            "'No pages enabled' until you re-enable one."
        ),
    },
    {
        "title": "OSC & Network Config",
        "content": (
            "OSC IP — IP address to send messages to.\n"
            "  • Same PC: 127.0.0.1 (default)\n"
            "  • Different PC on LAN: use that PC's local IP\n\n"
            "OSC Port — VRChat listens on 9000 by default.\n"
            "  Don't change this unless you know you need to.\n\n"
            "Network Interface — The adapter to monitor for\n"
            "upload/download speed modules.\n"
            "  Open Task Manager → Performance tab to find\n"
            "  your adapter name (e.g. Ethernet, Wi-Fi).\n\n"
            "Interval (s) — Default duration for new pages.\n"
            "  Existing pages use their own per-page duration."
        ),
    },
    {
        "title": "LibreHardwareMonitor",
        "content": (
            "CPU/GPU temperature, wattage, and load modules\n"
            "require LibreHardwareMonitor (LHM) to be running.\n\n"
            "If you want to run the included one you can run it from the toolbox.\n\n"
            "If you want to get it from github — Setup:\n"
            "  1. Download LHM from GitHub:\n"
            "     github.com/LibreHardwareMonitor/LibreHardwareMonitor\n"
            "  2. Run LibreHardwareMonitor.exe as Administrator\n"
            "  3. Options → Web Server → Run\n"
            "     (default port 8085)\n\n"
            "LHM URL in the config should be:\n"
            "  http://localhost:8085/data.json\n\n"
            "LHM is Windows-only. On Linux, CPU/GPU stat modules\n"
            "read sensors directly from /sys instead and don't\n"
            "need LHM running at all."
        ),
    },
    {
        "title": "Weather",
        "content": (
            "Weather modules use the free Open-Meteo API.\n"
            "No API key needed.\n\n"
            "Location — Enter your coordinates as:\n"
            "   latitude,longitude\n\n"
            "Examples:\n"
            "   53.4,-2.2   (Manchester, UK)\n"
            "   51.5,-0.1   (London, UK)\n"
            "   40.7,-74.0  (New York, USA)\n"
            "   35.6,139.7  (Tokyo, Japan)\n\n"
            "To find your coordinates:\n"
            "  Google Maps → right-click your location\n"
            "  The first two numbers are lat,lon.\n\n"
            "Weather refreshes every 5 minutes."
        ),
    },
    {
        "title": "Media Modules",
        "content": (
            "Media modules show your currently playing music.\n\n"
            "On Windows these use the Windows Media Transport\n"
            "Controls (the same system as the taskbar overlay).\n"
            "Any app that reports to Windows media controls\n"
            "will work: Spotify, Chrome, Firefox, VLC, etc.\n\n"
            "Available media modules:\n"
            "  Media Title     — song name (with ▶/⏸ icon)\n"
            "  Media Artist    — artist name\n"
            "  Media Album     — album name\n"
            "  Media Source    — app name (e.g. Spotify)\n"
            "  Media Progress  — visual progress bar\n"
            "  Media Time      — 2:14 / 3:45\n"
            "  Media Detail    — track, time & source combined\n\n"
            "Trim Media Titles (in Settings) removes clutter\n"
            "like '(Official Video)' and '[Lyrics]'."
        ),
    },
    {
        "title": "Forced Text",
        "content": (
            "The Forced Text field on the Chatbox tab lets you\n"
            "override all pages instantly.\n\n"
            "While anything is typed in that field, the chatbox\n"
            "will send only that text — ignoring all pages.\n\n"
            "Leave it blank (or clear it) to return to the\n"
            "normal rotating page display.\n\n"
            "Useful for:\n"
            "  • Sending a quick custom message to the world\n"
            "  • Temporarily hiding your stats\n"
            "  • Testing what a line looks like in VRChat\n\n"
            "VRChat's chatbox limit is 144 characters.\n"
            "Any text longer than that is automatically trimmed."
        ),
    },
    {
        "title": "Settings",
        "content": (
            "Open Settings with the ⚙ Settings button.\n\n"
            "Themes — changes the colours of everything.\n\n"
            "Config reset — Resets everything to Defaults including the config.\n\n"
            "Progress Bar Characters:\n"
            "  Filled / Border / Empty — the three characters\n"
            "  used to draw the Media Progress bar module.\n"
            "  Defaults: ▓ ▒ ░\n"
            "  Type any character; preview updates live.\n\n"
            "Trim Media Titles — strips words like 'official',\n"
            "  'lyrics', 'video' from song titles.\n\n"
            "Slow Mode — updates pages every 5 seconds.\n"
            "Speed Mode — updates pages every 0.1 seconds.\n"
            "  (Both off = 1 second page update interval)\n\n"
            "Reset to Defaults restores all settings but\n"
            "keeps your pages and connection config."
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

    # ── Header ────────────────────────────────────────────────────────────
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

    # ── Content ───────────────────────────────────────────────────────────
    content_panel = QFrame()
    content_panel.setStyleSheet(
        f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};"
    )
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

    # ── Nav ───────────────────────────────────────────────────────────────
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