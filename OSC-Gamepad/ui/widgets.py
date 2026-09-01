"""
ui/widgets.py
─────────────
Reusable button factories (axis/action/toggle/square) and the
NES / Joystick pad layout widgets.
"""

import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QGridLayout, QHBoxLayout, QVBoxLayout,
)

from ui import theme


# ── Button factories ──────────────────────────────────────────────────────────
#
# NOTE: every button style below is applied INLINE via setStyleSheet() on the
# widget itself, and every stylesheet explicitly includes "border: none"
# (or an explicit border colour) rather than leaving it unset. Both of these
# sidestep confirmed Qt Style Sheet cascading quirks: (1) objectName-scoped
# global rules get silently shadowed by any styled ancestor, and (2) the
# "border" property leaks down from a styled ancestor through multiple
# levels of nesting even when a base "border: none" rule exists elsewhere.
# Applying styles inline, with an explicit border on every widget, avoids
# both failure modes regardless of how deeply a button ends up nested.


class _AxisButton(QPushButton):
    """Held-direction button (D-pad, look controls). Sends press/release
    to PadState — including releasing on mouse-leave, so dragging off the
    button while held doesn't leave the input stuck on."""

    def __init__(self, label: str, action: str, state, font_size: int = 13):
        super().__init__(label)
        self._action = action
        self._state = state
        self.setFixedSize(34, 34)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(theme.qt_font(font_size, bold=True))
        self._apply_style(theme.BORDER)

    def _apply_style(self, border_colour):
        self.setStyleSheet(
            f"QPushButton {{ background-color: {theme.PANEL}; color: {theme.TEXT}; "
            f"border: 1px solid {border_colour}; }}"
        )

    def enterEvent(self, event):
        self.setStyleSheet(
            f"QPushButton {{ background-color: {theme.BORDER}; color: {theme.TEXT}; "
            f"border: 1px solid {theme.BORDER}; }}"
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._state.release_axis(self._action)
        self._apply_style(theme.BORDER)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._state.press_axis(self._action)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._state.release_axis(self._action)
        super().mouseReleaseEvent(event)


def make_axis_btn(parent, label: str, action: str, state, font_size: int = 13) -> QPushButton:
    return _AxisButton(label, action, state, font_size)


class _ActionButton(QPushButton):
    """Momentary action button (JUMP/GRAB/USE/MENU/MUTE) — coloured
    outline per action, filled theme.ACCENT while held."""

    def __init__(self, label: str, action: str, colour: str, state,
                 width: int = 5, height: int = 2):
        super().__init__(label)
        self._action = action
        self._state = state
        self._colour = colour
        self.setFixedSize(width * 14, height * 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(theme.qt_font(8, bold=True))
        self._set_bg(theme.PANEL)

    def _set_bg(self, bg):
        self.setStyleSheet(
            f"QPushButton {{ background-color: {bg}; color: {self._colour}; "
            f"border: 1px solid {self._colour}; }}"
        )

    def enterEvent(self, event):
        self._set_bg(theme.BORDER)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._state.release_btn(self._action)
        self._set_bg(theme.PANEL)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._state.press_btn(self._action)
            self._set_bg(theme.ACCENT)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._state.release_btn(self._action)
            self._set_bg(theme.PANEL)
        super().mouseReleaseEvent(event)


def make_action_btn(parent, label: str, action: str, colour: str, state,
                    width: int = 5, height: int = 2) -> QPushButton:
    return _ActionButton(label, action, colour, state, width, height)


class _ToggleButton(QPushButton):
    """Sticky toggle button (SIT/CROUCH) — stays filled theme.ACCENT while active."""

    def __init__(self, label: str, param: str, colour: str, state,
                 width: int = 5, height: int = 2):
        super().__init__(label)
        self._param = param
        self._state = state
        self._colour = colour
        self._active = False
        self.setFixedSize(width * 14, height * 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(theme.qt_font(8, bold=True))
        self._refresh()
        self.clicked.connect(self._on_click)

    def _refresh(self):
        bg = theme.ACCENT if self._active else theme.PANEL
        self.setStyleSheet(
            f"QPushButton {{ background-color: {bg}; color: {self._colour}; "
            f"border: 1px solid {self._colour}; }}"
        )

    def _on_click(self):
        self._active = self._state.toggle_avatar_param(self._param)
        self._refresh()

    def enterEvent(self, event):
        if not self._active:
            self.setStyleSheet(
                f"QPushButton {{ background-color: {theme.BORDER}; color: {self._colour}; "
                f"border: 1px solid {self._colour}; }}"
            )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._refresh()
        super().leaveEvent(event)


def make_toggle_btn(parent, label: str, param: str, colour: str, state,
                    width: int = 5, height: int = 2) -> QPushButton:
    return _ToggleButton(label, param, colour, state, width, height)


def square_button(parent, text: str, command, base_size: int = 28) -> QWidget:
    container = QWidget()
    container.setFixedSize(base_size, base_size)
    container.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
    lay = QVBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)

    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFont(theme.qt_font(12))
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {theme.PANEL}; color: {theme.SUBTEXT}; border: none; }}"
        f"QPushButton:hover {{ background-color: {theme.BORDER}; color: {theme.TEXT}; }}"
    )
    btn.clicked.connect(command)
    lay.addWidget(btn)
    return container


# ── Action button definitions shared by both pad styles ──────────────────────

def _action_buttons():
    """Built lazily (not at import time) so it always reflects the
    currently active theme's colours."""
    return [
        ("JUMP",   "jump",     theme.GREEN,   False),
        ("GRAB",   "grab",     theme.ORANGE,  False),
        ("USE",    "use",      theme.ACCENT2, False),
        ("MENU",   "menu",     theme.ACCENT,  False),
        ("MUTE",   "voice",    theme.YELLOW,  False),
        ("SIT",    "seated",   theme.RED,     True),
        ("CROUCH", "crouched", theme.CYAN,    True),
    ]


def build_action_grid(parent, state) -> QWidget:
    act = QWidget()
    act.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
    grid = QGridLayout(act)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(4)
    for i, (label, action, colour, is_toggle) in enumerate(_action_buttons()):
        b = (make_toggle_btn(act, label, action, colour, state) if is_toggle
             else make_action_btn(act, label, action, colour, state))
        grid.addWidget(b, i // 2, i % 2)
    return act


# ── NES-style D-pad layout ────────────────────────────────────────────────────

class NESPad(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        left = QVBoxLayout()

        dpad = QWidget()
        dpad.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        dpad_grid = QGridLayout(dpad)
        dpad_grid.setSpacing(2)
        dpad_grid.addWidget(make_axis_btn(dpad, "▲", "up", self.state), 0, 1)
        dpad_grid.addWidget(make_axis_btn(dpad, "◀", "left", self.state), 1, 0)
        dpad_grid.addWidget(make_axis_btn(dpad, "▶", "right", self.state), 1, 2)
        dpad_grid.addWidget(make_axis_btn(dpad, "▼", "down", self.state), 2, 1)
        spacer = QWidget()
        spacer.setFixedSize(34, 34)
        spacer.setStyleSheet(f"background-color: {theme.BG}; border: none;")
        dpad_grid.addWidget(spacer, 1, 1)
        left.addWidget(dpad)

        look = QWidget()
        look.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        look_layout = QVBoxLayout(look)
        look_layout.setContentsMargins(0, 0, 0, 0)
        look_layout.setSpacing(2)

        look_lbl = QLabel("LOOK")
        look_lbl.setAlignment(Qt.AlignCenter)
        look_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        look_lbl.setFont(theme.qt_font(7))
        look_layout.addWidget(look_lbl)

        lh_row = QHBoxLayout()
        lh_row.addStretch(1)
        lh_row.addWidget(make_axis_btn(look, "◀", "look_l", self.state, font_size=10))
        lh_row.addWidget(make_axis_btn(look, "▶", "look_r", self.state, font_size=10))
        lh_row.addStretch(1)
        look_layout.addLayout(lh_row)

        lv_row = QHBoxLayout()
        lv_row.addStretch(1)
        lv_row.addWidget(make_axis_btn(look, "▲", "look_u", self.state, font_size=10))
        lv_row.addWidget(make_axis_btn(look, "▼", "look_d", self.state, font_size=10))
        lv_row.addStretch(1)
        look_layout.addLayout(lv_row)

        left.addSpacing(8)
        left.addWidget(look)
        left.addStretch(1)

        root.addLayout(left)
        root.addSpacing(8)
        root.addWidget(build_action_grid(self, self.state))


# ── Joystick-style analogue layout ────────────────────────────────────────────

class _AnalogStick(QWidget):
    """Draggable analogue stick — mirrors the Tk canvas: outer ring, centre
    dot, and a knob that can be dragged anywhere inside the ring radius and
    snaps back to centre on release."""

    def __init__(self, state, size: int = 170, knob: int = 16):
        super().__init__()
        self._state = state
        self._size = size
        self._knob = knob
        self._pos = QPointF(0, 0)  # offset from centre, in pixels
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        cen = self._size / 2

        painter.setPen(QPen(QColor(theme.BORDER), 1))
        painter.setBrush(QColor(theme.BG))
        painter.drawEllipse(QRectF(4, 4, self._size - 8, self._size - 8))

        painter.setBrush(QColor(theme.PANEL))
        painter.drawEllipse(QPointF(cen, cen), 5, 5)

        knob_centre = QPointF(cen + self._pos.x(), cen + self._pos.y())
        painter.setPen(QPen(QColor(theme.ACCENT2), 2))
        painter.setBrush(QColor(theme.ACCENT))
        painter.drawEllipse(knob_centre, self._knob, self._knob)

    def _max_radius(self):
        return self._size / 2 - self._knob - 4

    def mouseMoveEvent(self, event):
        cen = self._size / 2
        dx = event.position().x() - cen
        dy = event.position().y() - cen
        dist = math.hypot(dx, dy)
        max_r = self._max_radius()
        if dist > max_r and dist > 0:
            dx, dy = dx / dist * max_r, dy / dist * max_r
        self._pos = QPointF(dx, dy)
        self.update()
        self._state._safe_send("/input/Horizontal", round(max(-1.0, min(1.0, dx / max_r)), 3))
        self._state._safe_send("/input/Vertical", round(max(-1.0, min(1.0, -dy / max_r)), 3))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._pos = QPointF(0, 0)
        self.update()
        self._state._safe_send("/input/Horizontal", 0.0)
        self._state._safe_send("/input/Vertical", 0.0)


class _AxisSlider(QWidget):
    """Draggable horizontal slider (LOOK H / LOOK V) — knob snaps back to
    centre on release, sending 0.0."""

    def __init__(self, state, osc_addr: str, width: int = 170, height: int = 36, knob: int = 26):
        super().__init__()
        self._state = state
        self._addr = osc_addr
        self._w = width
        self._h = height
        self._knob = knob
        self._x = width / 2  # knob centre x
        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        ty = self._h / 2

        painter.setPen(QPen(QColor(theme.BORDER), 2))
        painter.drawLine(QPointF(self._knob / 2, ty), QPointF(self._w - self._knob / 2, ty))

        painter.setPen(QPen(QColor(theme.ACCENT2), 2))
        painter.setBrush(QColor(theme.ACCENT))
        painter.drawEllipse(QPointF(self._x, ty), self._knob / 2, self._knob / 2)

    def mouseMoveEvent(self, event):
        usable = self._w - self._knob
        x = max(self._knob / 2, min(self._w - self._knob / 2, event.position().x()))
        self._x = x
        self.update()
        self._state._safe_send(self._addr, round((x - self._w / 2) / (usable / 2), 3))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._x = self._w / 2
        self.update()
        self._state._safe_send(self._addr, 0.0)


class JoystickPad(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        left = QVBoxLayout()
        left.addWidget(_AnalogStick(self.state))

        left.addSpacing(2)
        h_slider = _AxisSlider(self.state, "/input/LookHorizontal")
        left.addWidget(h_slider)
        h_lbl = QLabel("LOOK H")
        h_lbl.setAlignment(Qt.AlignCenter)
        h_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        h_lbl.setFont(theme.qt_font(7))
        left.addWidget(h_lbl)

        left.addSpacing(2)
        v_slider = _AxisSlider(self.state, "/input/LookVertical")
        left.addWidget(v_slider)
        v_lbl = QLabel("LOOK V")
        v_lbl.setAlignment(Qt.AlignCenter)
        v_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        v_lbl.setFont(theme.qt_font(7))
        left.addWidget(v_lbl)

        left.addStretch(1)

        root.addLayout(left)
        root.addSpacing(8)
        root.addWidget(build_action_grid(self, self.state))