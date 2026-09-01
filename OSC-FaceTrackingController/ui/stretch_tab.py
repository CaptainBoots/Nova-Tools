"""
ui/stretch_tab.py
────────────────────
A playful, directly-manipulable face: drag eyebrows/eyes/cheeks/mouth/jaw/
tongue to pose the avatar's face parameters in real time. The pose holds
wherever you leave it — nothing snaps back — until you hit Reset.

Sends through the same OSC connection as the sliders tab (see
FaceTab.send_param) rather than opening a second client, so Start/Stop
on the main tab controls whether this one is actually sending too.
"""

import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton

from core.face_params import FACE_PARAMS
from ui import theme
from ui.theme import StripeBackground

CANVAS_SIZE = 420
GRAB_RADIUS = 22
DRAG_RANGE  = 70

_PARAM_INFO = {
    name: (lo, hi, default)
    for params in FACE_PARAMS.values()
    for name, lo, hi, default in params
}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class _Handle:
    def __init__(self, base):
        self.base = base

    def get_pos(self, values):
        raise NotImplementedError

    def apply_drag(self, dx, dy, values, set_value):
        raise NotImplementedError


class _BrowHandle(_Handle):
    def __init__(self, base, up_param, down_param):
        super().__init__(base)
        self.up_param = up_param
        self.down_param = down_param

    def get_pos(self, values):
        y = self.base.y() - values.get(self.up_param, 0.0) * DRAG_RANGE \
            + values.get(self.down_param, 0.0) * DRAG_RANGE
        return QPointF(self.base.x(), y)

    def apply_drag(self, dx, dy, values, set_value):
        offset = -dy / DRAG_RANGE
        if offset >= 0:
            set_value(self.up_param, _clamp(offset, 0.0, 1.0))
            set_value(self.down_param, 0.0)
        else:
            set_value(self.up_param, 0.0)
            set_value(self.down_param, _clamp(-offset, 0.0, 1.0))


class _EyeHandle(_Handle):
    def __init__(self, base, wide_param, lid_param, x_param):
        super().__init__(base)
        self.wide_param = wide_param
        self.lid_param = lid_param
        self.x_param = x_param

    def get_pos(self, values):
        wide = values.get(self.wide_param, 0.0)
        lid = values.get(self.lid_param, 1.0)
        y = self.base.y() - wide * DRAG_RANGE + (1.0 - lid) * DRAG_RANGE
        x = self.base.x() + values.get(self.x_param, 0.0) * (DRAG_RANGE * 0.5)
        return QPointF(x, y)

    def apply_drag(self, dx, dy, values, set_value):
        offset = -dy / DRAG_RANGE
        if offset >= 0:
            set_value(self.wide_param, _clamp(offset, 0.0, 1.0))
            set_value(self.lid_param, 1.0)
        else:
            set_value(self.wide_param, 0.0)
            set_value(self.lid_param, _clamp(1.0 + offset, 0.0, 1.0))
        set_value(self.x_param, _clamp(dx / (DRAG_RANGE * 0.5), -1.0, 1.0))


class _CheekHandle(_Handle):
    def __init__(self, base, puff_param, suck_param, outward_sign):
        super().__init__(base)
        self.puff_param = puff_param
        self.suck_param = suck_param
        self.outward_sign = outward_sign

    def get_pos(self, values):
        puff = values.get(self.puff_param, 0.0)
        suck = values.get(self.suck_param, 0.0)
        x = self.base.x() + self.outward_sign * (puff * DRAG_RANGE - suck * DRAG_RANGE * 0.6)
        return QPointF(x, self.base.y())

    def apply_drag(self, dx, dy, values, set_value):
        outward = self.outward_sign * dx / DRAG_RANGE
        if outward >= 0:
            set_value(self.puff_param, _clamp(outward, 0.0, 1.0))
            set_value(self.suck_param, 0.0)
        else:
            set_value(self.puff_param, 0.0)
            set_value(self.suck_param, _clamp(-outward / 0.6, 0.0, 1.0))


class _MouthCornerHandle(_Handle):
    def __init__(self, base, smile_param, sad_param):
        super().__init__(base)
        self.smile_param = smile_param
        self.sad_param = sad_param

    def get_pos(self, values):
        y = self.base.y() - values.get(self.smile_param, 0.0) * (DRAG_RANGE * 0.7) \
            + values.get(self.sad_param, 0.0) * (DRAG_RANGE * 0.7)
        return QPointF(self.base.x(), y)

    def apply_drag(self, dx, dy, values, set_value):
        offset = -dy / (DRAG_RANGE * 0.7)
        if offset >= 0:
            set_value(self.smile_param, _clamp(offset, 0.0, 1.0))
            set_value(self.sad_param, 0.0)
        else:
            set_value(self.smile_param, 0.0)
            set_value(self.sad_param, _clamp(-offset, 0.0, 1.0))


class _TwoAxisHandle(_Handle):
    def __init__(self, base, open_param, x_param, v_range=DRAG_RANGE):
        super().__init__(base)
        self.open_param = open_param
        self.x_param = x_param
        self.v_range = v_range

    def get_pos(self, values):
        y = self.base.y() + values.get(self.open_param, 0.0) * self.v_range
        x = self.base.x() + values.get(self.x_param, 0.0) * (DRAG_RANGE * 0.5)
        return QPointF(x, y)

    def apply_drag(self, dx, dy, values, set_value):
        set_value(self.open_param, _clamp(dy / self.v_range, 0.0, 1.0))
        set_value(self.x_param, _clamp(dx / (DRAG_RANGE * 0.5), -1.0, 1.0))


class _StretchCanvas(QWidget):
    def __init__(self, on_change):
        super().__init__()
        self._on_change = on_change
        self.setFixedSize(CANVAS_SIZE, CANVAS_SIZE)
        self.setCursor(Qt.OpenHandCursor)

        self._values = {name: default for name, (_, _, default) in _PARAM_INFO.items()}
        self._drag_handle_id = None
        self._drag_start_mouse = None

        c = CANVAS_SIZE / 2
        self._handles = {
            "brow_l": _BrowHandle(QPointF(c - 62, c - 108), "BrowOuterUpLeft", "BrowDownLeft"),
            "brow_r": _BrowHandle(QPointF(c + 62, c - 108), "BrowOuterUpRight", "BrowDownRight"),
            "eye_l":  _EyeHandle(QPointF(c - 62, c - 68), "EyeWideLeft", "EyeLidLeft", "EyeLeftX"),
            "eye_r":  _EyeHandle(QPointF(c + 62, c - 68), "EyeWideRight", "EyeLidRight", "EyeRightX"),
            "cheek_l": _CheekHandle(QPointF(c - 100, c + 10), "CheekPuffLeft", "CheekSuckLeft", -1),
            "cheek_r": _CheekHandle(QPointF(c + 100, c + 10), "CheekPuffRight", "CheekSuckRight", 1),
            "mouth_l": _MouthCornerHandle(QPointF(c - 46, c + 62), "MouthSmileLeft", "MouthSadLeft"),
            "mouth_r": _MouthCornerHandle(QPointF(c + 46, c + 62), "MouthSmileRight", "MouthSadRight"),
            "jaw":     _TwoAxisHandle(QPointF(c, c + 108), "JawOpen", "JawX"),
            "tongue":  _TwoAxisHandle(QPointF(c, c + 150), "TongueOut", "TongueX", v_range=40),
        }

    def _set_value(self, param, value):
        lo, hi, _ = _PARAM_INFO.get(param, (0.0, 1.0, 0.0))
        value = round(_clamp(value, lo, hi), 3)
        if self._values.get(param) != value:
            self._values[param] = value
            self._on_change(param, value)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pos = event.position()
        nearest_id, nearest_dist = None, GRAB_RADIUS
        for handle_id, handle in self._handles.items():
            hp = handle.get_pos(self._values)
            dist = math.hypot(pos.x() - hp.x(), pos.y() - hp.y())
            if dist < nearest_dist:
                nearest_id, nearest_dist = handle_id, dist
        if nearest_id is not None:
            self._drag_handle_id = nearest_id
            self._drag_start_mouse = pos
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_handle_id is None:
            return
        pos = event.position()
        dx = pos.x() - self._drag_start_mouse.x()
        dy = pos.y() - self._drag_start_mouse.y()
        handle = self._handles[self._drag_handle_id]
        handle.apply_drag(dx, dy, self._values, self._set_value)
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag_handle_id = None
        self.setCursor(Qt.OpenHandCursor)

    def reset(self):
        for name, (_, _, default) in _PARAM_INFO.items():
            if self._values.get(name) != default:
                self._values[name] = default
                self._on_change(name, default)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        c = CANVAS_SIZE / 2
        v = self._values

        painter.setPen(QPen(QColor(theme.BORDER), 2))
        painter.setBrush(QColor(theme.PANEL))
        painter.drawEllipse(QRectF(c - 150, c - 160, 300, 320))

        for handle_id in ("cheek_l", "cheek_r"):
            handle = self._handles[handle_id]
            puff = v.get(handle.puff_param, 0.0)
            suck = v.get(handle.suck_param, 0.0)
            radius = 34 + puff * 22 - suck * 14
            hp = handle.get_pos(v)
            painter.setPen(Qt.NoPen)
            cheek_colour = QColor(theme.ACCENT2)
            cheek_colour.setAlpha(70)
            painter.setBrush(cheek_colour)
            painter.drawEllipse(hp, radius, radius)

        for handle_id in ("brow_l", "brow_r"):
            hp = self._handles[handle_id].get_pos(v)
            brow_pen = QPen(QColor(theme.TEXT), 6)
            brow_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(brow_pen)
            tilt = 4 if handle_id == "brow_l" else -4
            painter.drawLine(QPointF(hp.x() - 22, hp.y() + tilt), QPointF(hp.x() + 22, hp.y() - tilt))

        for handle_id in ("eye_l", "eye_r"):
            handle = self._handles[handle_id]
            base = handle.base
            wide = v.get(handle.wide_param, 0.0)
            lid = v.get(handle.lid_param, 1.0)
            eye_h = max(2.0, 26 * lid + 14 * wide)
            eye_w = 30
            gaze_x = v.get(handle.x_param, 0.0) * 8

            painter.setPen(QPen(QColor(theme.ACCENT2), 2))
            painter.setBrush(QColor(theme.BG))
            painter.drawEllipse(QRectF(base.x() - eye_w / 2, base.y() - eye_h / 2, eye_w, eye_h))

            if eye_h > 6:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(theme.ACCENT))
                pupil_r = min(6.0, eye_h / 2 - 1)
                painter.drawEllipse(QPointF(base.x() + gaze_x, base.y()), pupil_r, pupil_r)

        mouth_l = self._handles["mouth_l"].get_pos(v)
        mouth_r = self._handles["mouth_r"].get_pos(v)
        jaw_handle = self._handles["jaw"]
        jaw_open = v.get(jaw_handle.open_param, 0.0)
        jaw_x = v.get(jaw_handle.x_param, 0.0)

        mid_bottom = QPointF(
            (mouth_l.x() + mouth_r.x()) / 2 + jaw_x * 20,
            jaw_handle.base.y() - 46 + jaw_open * 40,
            )

        path = QPainterPath()
        path.moveTo(mouth_l)
        path.quadTo(QPointF((mouth_l.x() + mid_bottom.x()) / 2, mid_bottom.y()), mid_bottom)
        path.quadTo(QPointF((mid_bottom.x() + mouth_r.x()) / 2, mid_bottom.y()), mouth_r)
        mouth_pen = QPen(QColor(theme.TEXT), 4)
        mouth_pen.setCapStyle(Qt.RoundCap)
        mouth_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(mouth_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        if jaw_open > 0.08:
            tongue_handle = self._handles["tongue"]
            tongue_out = v.get(tongue_handle.open_param, 0.0)
            tongue_x = v.get(tongue_handle.x_param, 0.0)
            tongue_h = 10 + tongue_out * 34
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.RED))
            painter.drawRoundedRect(QRectF(
                mid_bottom.x() + tongue_x * 20 - 11, mid_bottom.y() - 4,
                22, tongue_h,
                ), 8, 8)

        for handle_id, handle in self._handles.items():
            hp = handle.get_pos(v)
            is_active = handle_id == self._drag_handle_id
            col = QColor(theme.ACCENT if is_active else theme.BORDER)
            col.setAlpha(230 if is_active else 150)
            painter.setPen(Qt.NoPen)
            painter.setBrush(col)
            r = 7 if is_active else 5
            painter.drawEllipse(hp, r, r)


class StretchTab(StripeBackground):
    def __init__(self, face_tab, parent=None):
        super().__init__(parent)
        self._face_tab = face_tab
        self._chips = []
        self._build()

    def set_bg_alpha(self, alpha: float):
        super().set_bg_alpha(alpha)
        for chip in self._chips:
            chip.set_bg_alpha(alpha)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        hint = theme.TextChip(
            "Drag any highlighted point on the face to pose it — the pose "
            "holds where you leave it, just like a slider.",
            fg=theme.SUBTEXT, padding="6px 12px",
        )
        hint.setFont(theme.qt_font(9))
        hint.setWordWrap(True)
        outer.addWidget(hint)
        self._chips.append(hint)

        canvas_row = QHBoxLayout()
        canvas_row.addStretch(1)
        self._canvas = _StretchCanvas(on_change=self._on_change)
        canvas_row.addWidget(self._canvas)
        canvas_row.addStretch(1)
        outer.addLayout(canvas_row, 1)

        btn_row = QHBoxLayout()

        self._status_chip = theme.TextChip("Not connected", fg=theme.RED, padding="3px 10px")
        self._status_chip.setFont(theme.qt_font(9, bold=True))
        btn_row.addWidget(self._status_chip)
        self._chips.append(self._status_chip)

        btn_row.addStretch(1)

        reset_btn = QPushButton("↺  Reset Pose")
        reset_btn.setStyleSheet(theme.accent_button_qss())
        reset_btn.setFont(theme.qt_font(10, bold=True))
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._canvas.reset)
        btn_row.addWidget(reset_btn)

        outer.addLayout(btn_row)

        self.refresh_status()

    def _on_change(self, param, value):
        self._face_tab.send_param(param, value)

    def refresh_status(self):
        if self._face_tab.is_connected():
            self._status_chip.setText("● Sending live")
            self._status_chip.setStyleSheet(
                f"color: {theme.GREEN}; background-color: {theme.PANEL}; "
                f"padding: 3px 10px; border-radius: 3px; border: none;"
            )
        else:
            self._status_chip.setText("○ Not connected — Start on the Face Tracking tab first")
            self._status_chip.setStyleSheet(
                f"color: {theme.RED}; background-color: {theme.PANEL}; "
                f"padding: 3px 10px; border-radius: 3px; border: none;"
            )