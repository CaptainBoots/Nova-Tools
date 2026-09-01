"""
ui/help_dialog.py
─────────────────
Paginated help window for OSC Face Tracking Controller.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from ui import theme

HELP_PAGES = [
    {
        "title": "Welcome",
        "content": (
            "Welcome to OSC Face Tracking Controller!\n\n"
            "This tool connects to VRChat and other applications to\n"
            "send face tracking data via OSC (Open Sound Control).\n\n"
            "Use the tabs below to explore different facial\n"
            "parameters like eyes, mouth, brows, and more."
        ),
    },
    {
        "title": "Connection",
        "content": (
            "Connection Setup:\n\n"
            "1. IP Address: The target application's IP\n"
            "   (usually 127.0.0.1 for local)\n"
            "2. Port: OSC port number (default: 9000)\n"
            "3. Prefix: OSC address prefix (VRCFT v2 or\n"
            "   Direct/v1)\n\n"
            "Click Start to establish connection.\n"
            "Green status = running, Red status = stopped or error."
        ),
    },
    {
        "title": "Parameters",
        "content": (
            "Facial Parameters:\n\n"
            "• Eyes: Eye movement, eyelid, blinking\n"
            "• Brows: Eyebrow position and expression\n"
            "• Mouth: Jaw, lips, smile, and other mouth shapes\n"
            "• Cheek/Nose: Puffing and scrunching\n"
            "• Tongue: Tongue position and movement\n\n"
            "Use sliders to adjust values from 0 to 1 (or -1 to 1)."
        ),
    },
    {
        "title": "Tips",
        "content": (
            "Tips & Tricks:\n\n"
            "• Reset All resets every parameter to its default\n"
            "• Changes are sent in real-time as you drag\n"
            "• Use the prefix presets to quickly switch between\n"
            "  VRCFT v2 and Direct/v1 addressing\n"
            "• The ↺ button next to each slider resets just\n"
            "  that one parameter\n\n"
            "For issues, check your connection status and verify\n"
            "the target application is running."
        ),
    },
]


def open_help(parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle("OSC Face Tracking - Help")
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
