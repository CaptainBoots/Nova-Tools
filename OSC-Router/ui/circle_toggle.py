"""
ui/circle_toggle.py
───────────────────────
Qt replacement for ui/circle_toggle.py.

Same visual language as the Tk version — filled circle = ON, outline
circle = OFF — but uses QPainter's native antialiasing instead of the
PIL 4x-supersample-then-downscale trick (Qt handles this natively).

Usage:
    toggle = CircleToggle(parent, enabled=True, color="#a78bfa")
    toggle.toggled.connect(my_slot)   # emits bool on user click
    toggle.get() / toggle.set(bool)   # same API as the Tk version
"""

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget


class CircleToggle(QWidget):
    toggled = Signal(bool)  # mirrors the Tk version's `command` callback

    DEFAULT_SIZE = 20
    DEFAULT_PAD = 3
    DEFAULT_COLOR = "#a78bfa"

    def __init__(self, parent=None, *, enabled: bool = True,
                 color: str = DEFAULT_COLOR, size: int = DEFAULT_SIZE,
                 pad: int = DEFAULT_PAD, command=None):
        super().__init__(parent)
        self._enabled = enabled
        self._color = QColor(color)
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

    # ── Public API (mirrors the Tk version) ─────────────────────────────────

    def get(self) -> bool:
        return self._enabled

    def set(self, value: bool):
        """Set state programmatically without firing `toggled`."""
        self._enabled = bool(value)
        self.update()

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()