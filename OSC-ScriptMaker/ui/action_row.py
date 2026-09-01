"""
ui/action_row.py
─────────────────
ActionRow: one action within a script's action chain. The kind
dropdown is populated straight from core.registry, and
switching it rebuilds the field panel below for that kind — same
"swap the body, keep the frame" pattern PadCard uses for NES/Joystick.

A "random" action embeds its own list of nested ActionRows (one
level deep only — nestable=False on those, so their kind dropdown
excludes "random" itself, via registry.NON_NESTABLE_KINDS).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog,
)

from core.registry import ACTIONS, ACTION_BY_ID, NON_NESTABLE_KINDS
from core.models import Action
from Actions.chatbox_action import CHATBOX_CHANNELS
from ui import theme
from ui.circle_toggle import CircleToggle


def _row_label(text, width=None):
    l = QLabel(text)
    l.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
    l.setFont(theme.qt_font(8))
    if width:
        l.setFixedWidth(width)
    return l


def _entry(text, width=70):
    e = QLineEdit(text)
    e.setFixedWidth(width)
    e.setFont(theme.qt_font(9))
    e.setStyleSheet(theme.line_edit_qss())
    return e


def _combo(options, current):
    """options: list of (value, label) tuples."""
    c = QComboBox()
    c.setFont(theme.qt_font(9))
    c.setStyleSheet(
        f"QComboBox {{ background-color: {theme.PANEL}; color: {theme.TEXT}; "
        f"border: 1px solid {theme.BORDER}; border-radius: 2px; padding: 3px 6px; }}"
    )
    for value, label in options:
        c.addItem(label, value)
    idx = c.findData(current)
    c.setCurrentIndex(idx if idx >= 0 else 0)
    return c


def _toggle_with_label(text, checked):
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    toggle = CircleToggle(enabled=checked, color=theme.ACCENT)
    lay.addWidget(toggle)
    lbl = _row_label(text)
    lay.addWidget(lbl)
    return row, toggle


def _clear_layout(layout):
    """Recursively empties `layout`: deletes every widget it contains and
    descends into any nested layouts (addLayout(...) rows), deleting those
    too. QLayout.takeAt()/item.widget() only strips one level — most of
    this file's field builders nest a QHBoxLayout per row via addLayout,
    so a shallow clear leaves the previous kind's fields alive underneath
    (invisible, but still wired to the action object) every time the kind
    dropdown changes."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
            continue
        sub_layout = item.layout()
        if sub_layout is not None:
            _clear_layout(sub_layout)


class ActionRow(QFrame):
    def __init__(self, action: Action, on_remove, on_move_up=None, on_move_down=None,
                 nestable=True, parent=None):
        super().__init__(parent)
        self.action = action
        self.on_remove = on_remove
        self.on_move_up = on_move_up
        self.on_move_down = on_move_down
        self.nestable = nestable

        self._fields: dict = {}
        self._sub_rows: list[ActionRow] = []

        bg = theme.PANEL if nestable else theme.BG
        self.setStyleSheet(f"background-color: {bg}; border: 1px solid {theme.BORDER};")
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        hdr = QHBoxLayout()

        if self.on_move_up is not None:
            up_btn = QLabel("▲")
            up_btn.setCursor(Qt.PointingHandCursor)
            up_btn.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
            up_btn.setFont(theme.qt_font(8))
            up_btn.mousePressEvent = lambda _e: self.on_move_up(self)
            hdr.addWidget(up_btn)

        if self.on_move_down is not None:
            down_btn = QLabel("▼")
            down_btn.setCursor(Qt.PointingHandCursor)
            down_btn.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
            down_btn.setFont(theme.qt_font(8))
            down_btn.mousePressEvent = lambda _e: self.on_move_down(self)
            hdr.addWidget(down_btn)

        kind_options = [(a["id"], a["label"]) for a in ACTIONS
                        if self.nestable or a["id"] in NON_NESTABLE_KINDS]
        self._kind_combo = _combo(kind_options, self.action.kind)
        self._kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        hdr.addWidget(self._kind_combo)
        hdr.addStretch(1)

        rm_btn = QLabel("✕")
        rm_btn.setCursor(Qt.PointingHandCursor)
        rm_btn.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        rm_btn.setFont(theme.qt_font(9))
        rm_btn.mousePressEvent = lambda _e: self.on_remove(self)
        hdr.addWidget(rm_btn)

        outer.addLayout(hdr)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(4, 2, 4, 2)
        self._body_layout.setSpacing(4)
        outer.addWidget(self._body)

        self._rebuild_fields()

    def _on_kind_changed(self, _idx):
        self.action.kind = self._kind_combo.currentData()
        self._rebuild_fields()

    def _clear_body(self):
        _clear_layout(self._body_layout)
        self._fields = {}
        self._sub_rows = []

    def _rebuild_fields(self):
        self._clear_body()
        builder = _FIELD_BUILDERS.get(self.action.kind)
        if builder:
            builder(self, self._body_layout, self.action)

    # ── Config I/O ────────────────────────────────────────────────────────

    def get_config(self) -> Action:
        # Field widgets write straight into self.action as they're read,
        # so by this point self.action already reflects the UI — except
        # random's nested sub-rows, which need an explicit pull.
        if self.action.kind == "random":
            self.action.sub_actions = [row.get_config() for row in self._sub_rows]
        return self.action


# ── Per-kind field builders ─────────────────────────────────────────────────
# Each takes (row: ActionRow, layout: QVBoxLayout, action: Action) and adds
# whatever widgets that action kind needs, wiring them to write straight
# back into `action` on change (no separate "commit" step needed).

def _line(row, layout, label_text, initial, width, setter, placeholder=""):
    wrap = QHBoxLayout()
    wrap.addWidget(_row_label(label_text, 70))
    e = _entry(initial, width)
    if placeholder:
        e.setPlaceholderText(placeholder)
    e.textChanged.connect(setter)
    wrap.addWidget(e)
    wrap.addStretch(1)
    layout.addLayout(wrap)
    return e


def _build_keybind(row, layout, action: Action):
    def set_keys(text):
        action.keys = [k.strip().lower() for k in text.split("+") if k.strip()]

    keys_text = "+".join(action.keys)
    _line(row, layout, "Keys:", keys_text, 140, set_keys, placeholder="ctrl+alt+u")

    def set_hold(text):
        try:
            action.hold_ms = int(text)
        except ValueError:
            action.hold_ms = 0

    _line(row, layout, "Hold (ms):", str(action.hold_ms), 60, set_hold,
          placeholder="0 = tap")


def _build_send_osc(row, layout, action: Action):
    def set_host(t): action.host = t
    def set_port(t): action.port = t
    def set_addr(t): action.address = t

    hp = QHBoxLayout()
    hp.addWidget(_row_label("Send to:", 50))
    h = _entry(action.host, 90)
    h.textChanged.connect(set_host)
    hp.addWidget(h)
    hp.addWidget(_row_label(":", 6))
    p = _entry(action.port, 50)
    p.textChanged.connect(set_port)
    hp.addWidget(p)
    hp.addStretch(1)
    layout.addLayout(hp)

    _line(row, layout, "Address:", action.address, 180, set_addr,
          placeholder="/avatar/parameters/...")

    mode_row = QHBoxLayout()
    mode_row.addWidget(_row_label("Value:", 70))
    mode_combo = _combo(
        [("static", "Static"), ("forward", "Forward trigger value"), ("transform", "Remap trigger value")],
        action.value_mode,
    )
    mode_row.addWidget(mode_combo)
    mode_row.addStretch(1)
    layout.addLayout(mode_row)

    static_wrap = QWidget()
    static_layout = QVBoxLayout(static_wrap)
    static_layout.setContentsMargins(0, 0, 0, 0)

    def set_static(t): action.static_value = t
    _line(row, static_layout, "Value:", action.static_value, 90, set_static,
          placeholder="e.g. 1, true, hello")

    transform_wrap = QWidget()
    tlay = QVBoxLayout(transform_wrap)
    tlay.setContentsMargins(0, 0, 0, 0)
    tlay.setSpacing(2)

    def _num_setter(attr):
        def _set(t):
            try:
                setattr(action, attr, float(t))
            except ValueError:
                pass
        return _set

    range_row = QHBoxLayout()
    range_row.addWidget(_row_label("In:", 24))
    in_min = _entry(str(action.in_min), 45); in_min.textChanged.connect(_num_setter("in_min"))
    range_row.addWidget(in_min)
    range_row.addWidget(_row_label("to", 16))
    in_max = _entry(str(action.in_max), 45); in_max.textChanged.connect(_num_setter("in_max"))
    range_row.addWidget(in_max)
    range_row.addWidget(_row_label("Out:", 28))
    out_min = _entry(str(action.out_min), 45); out_min.textChanged.connect(_num_setter("out_min"))
    range_row.addWidget(out_min)
    range_row.addWidget(_row_label("to", 16))
    out_max = _entry(str(action.out_max), 45); out_max.textChanged.connect(_num_setter("out_max"))
    range_row.addWidget(out_max)
    range_row.addStretch(1)
    tlay.addLayout(range_row)

    toggle_row = QHBoxLayout()
    invert_wrap, invert_toggle = _toggle_with_label("Invert", action.invert)
    invert_toggle.toggled.connect(lambda v: setattr(action, "invert", v))
    toggle_row.addWidget(invert_wrap)
    bool_wrap, bool_toggle = _toggle_with_label("As bool", action.as_bool)
    bool_toggle.toggled.connect(lambda v: setattr(action, "as_bool", v))
    toggle_row.addWidget(bool_wrap)
    toggle_row.addStretch(1)
    tlay.addLayout(toggle_row)

    layout.addWidget(static_wrap)
    layout.addWidget(transform_wrap)

    def _refresh_visibility():
        mode = action.value_mode
        static_wrap.setVisible(mode == "static")
        transform_wrap.setVisible(mode == "transform")

    def _on_mode_changed(_idx):
        action.value_mode = mode_combo.currentData()
        _refresh_visibility()

    mode_combo.currentIndexChanged.connect(_on_mode_changed)
    _refresh_visibility()


def _build_chatbox(row, layout, action: Action):
    target_row = QHBoxLayout()
    target_row.addWidget(_row_label("Target:", 70))
    target_combo = _combo(
        [("vrchat", "Send to VRChat"), ("channel", "Send to Chatbox (channel)")],
        action.chatbox_target,
    )
    target_row.addWidget(target_combo)
    target_row.addStretch(1)
    layout.addLayout(target_row)

    def set_host(t): action.host = t
    def set_port(t): action.port = t

    # VRChat mode: real host:port, normally 127.0.0.1:9000 (VRChat's OSC in)
    vrchat_wrap = QWidget()
    vrchat_layout = QVBoxLayout(vrchat_wrap)
    vrchat_layout.setContentsMargins(0, 0, 0, 0)
    vhp = QHBoxLayout()
    vhp.addWidget(_row_label("Send to:", 70))
    vh = _entry(action.host, 90)
    vh.textChanged.connect(set_host)
    vhp.addWidget(vh)
    vhp.addWidget(_row_label(":", 6))
    vp = _entry(action.port, 50)
    vp.textChanged.connect(set_port)
    vhp.addWidget(vp)
    vhp.addStretch(1)
    vrchat_layout.addLayout(vhp)

    # Channel mode: host stays editable (in case a channel listener runs on
    # another machine), port is picked from the 10 fixed channel ports —
    # nothing to type, nothing that can collide with real VRChat traffic.
    channel_wrap = QWidget()
    channel_layout = QVBoxLayout(channel_wrap)
    channel_layout.setContentsMargins(0, 0, 0, 0)
    chp = QHBoxLayout()
    chp.addWidget(_row_label("Host:", 70))
    ch_host = _entry(action.host, 90)
    ch_host.textChanged.connect(set_host)
    chp.addWidget(ch_host)
    chp.addWidget(_row_label("Channel:", 55))
    channel_options = [(n, f"Channel {n}  ({CHATBOX_CHANNELS[n]})") for n in sorted(CHATBOX_CHANNELS)]
    channel_combo = _combo(channel_options, action.chatbox_channel)
    channel_combo.currentIndexChanged.connect(
        lambda _i: setattr(action, "chatbox_channel", channel_combo.currentData())
    )
    chp.addWidget(channel_combo)
    chp.addStretch(1)
    channel_layout.addLayout(chp)

    layout.addWidget(vrchat_wrap)
    layout.addWidget(channel_wrap)

    def _refresh_target_visibility():
        is_channel = action.chatbox_target == "channel"
        vrchat_wrap.setVisible(not is_channel)
        channel_wrap.setVisible(is_channel)

    def _on_target_changed(_i):
        action.chatbox_target = target_combo.currentData()
        _refresh_target_visibility()

    target_combo.currentIndexChanged.connect(_on_target_changed)
    _refresh_target_visibility()

    def set_text(t): action.text = t
    _line(row, layout, "Text:", action.text, 180, set_text,
          placeholder="Use {value} for the trigger value")

    toggle_row = QHBoxLayout()
    imm_wrap, imm_toggle = _toggle_with_label("Send immediately", action.send_immediately)
    imm_toggle.toggled.connect(lambda v: setattr(action, "send_immediately", v))
    toggle_row.addWidget(imm_wrap)
    sfx_wrap, sfx_toggle = _toggle_with_label("Play sound", action.play_sfx)
    sfx_toggle.toggled.connect(lambda v: setattr(action, "play_sfx", v))
    toggle_row.addWidget(sfx_wrap)
    toggle_row.addStretch(1)
    layout.addLayout(toggle_row)


def _build_run_program(row, layout, action: Action):
    def set_path(t): action.program_path = t

    path_row = QHBoxLayout()
    path_row.addWidget(_row_label("Program:", 70))
    path_edit = _entry(action.program_path, 160)
    path_edit.textChanged.connect(set_path)
    path_row.addWidget(path_edit)

    def _browse():
        f, _ = QFileDialog.getOpenFileName(row, "Choose Program")
        if f:
            path_edit.setText(f)

    browse_btn = QPushButton("…")
    browse_btn.setFixedWidth(28)
    browse_btn.setStyleSheet(theme.subtle_button_qss())
    browse_btn.clicked.connect(_browse)
    path_row.addWidget(browse_btn)
    path_row.addStretch(1)
    layout.addLayout(path_row)

    def set_args(t): action.program_args = t
    _line(row, layout, "Args:", action.program_args, 160, set_args,
          placeholder="optional command-line args")


def _build_wait(row, layout, action: Action):
    def set_ms(t):
        try:
            action.wait_ms = int(t)
        except ValueError:
            action.wait_ms = 0

    _line(row, layout, "Wait (ms):", str(action.wait_ms), 70, set_ms)


def _build_set_variable(row, layout, action: Action):
    def set_name(t): action.var_name = t
    _line(row, layout, "Variable:", action.var_name, 120, set_name,
          placeholder="myVariable")

    mode_row = QHBoxLayout()
    mode_row.addWidget(_row_label("Value:", 70))
    mode_combo = _combo([("static", "Static"), ("forward", "Forward trigger value")],
                        action.var_value_mode)
    mode_row.addWidget(mode_combo)
    mode_row.addStretch(1)
    layout.addLayout(mode_row)

    static_wrap = QWidget()
    static_layout = QVBoxLayout(static_wrap)
    static_layout.setContentsMargins(0, 0, 0, 0)

    def set_static(t): action.var_static_value = t
    _line(row, static_layout, "Value:", action.var_static_value, 90, set_static)
    layout.addWidget(static_wrap)

    def _refresh_visibility():
        static_wrap.setVisible(action.var_value_mode == "static")

    def _on_mode_changed(_idx):
        action.var_value_mode = mode_combo.currentData()
        _refresh_visibility()

    mode_combo.currentIndexChanged.connect(_on_mode_changed)
    _refresh_visibility()


def _build_play_sound(row, layout, action: Action):
    def set_path(t): action.sound_path = t

    path_row = QHBoxLayout()
    path_row.addWidget(_row_label("Sound:", 70))
    path_edit = _entry(action.sound_path, 160)
    path_edit.textChanged.connect(set_path)
    path_row.addWidget(path_edit)

    def _browse():
        f, _ = QFileDialog.getOpenFileName(row, "Choose Sound File",
                                           filter="Audio Files (*.wav *.mp3 *.ogg *.flac);;All Files (*)")
        if f:
            path_edit.setText(f)

    browse_btn = QPushButton("…")
    browse_btn.setFixedWidth(28)
    browse_btn.setStyleSheet(theme.subtle_button_qss())
    browse_btn.clicked.connect(_browse)
    path_row.addWidget(browse_btn)
    path_row.addStretch(1)
    layout.addLayout(path_row)


def _build_random(row, layout, action: Action):
    list_wrap = QVBoxLayout()
    list_wrap.setSpacing(4)
    layout.addLayout(list_wrap)

    def _remove_sub(sub_row):
        list_wrap.removeWidget(sub_row)
        sub_row.setParent(None)
        sub_row.deleteLater()
        row._sub_rows.remove(sub_row)

    def _add_sub(sub_action=None):
        sub_action = sub_action or Action(kind="wait")
        sub_row = ActionRow(sub_action, on_remove=_remove_sub, nestable=False)
        list_wrap.addWidget(sub_row)
        row._sub_rows.append(sub_row)

    for sub in action.sub_actions:
        _add_sub(sub)

    add_btn = QPushButton("+ Add Random Option")
    add_btn.setStyleSheet(theme.subtle_button_qss())
    add_btn.setFont(theme.qt_font(8, bold=True))
    add_btn.clicked.connect(lambda: _add_sub())
    layout.addWidget(add_btn)


_FIELD_BUILDERS = {
    "keybind": _build_keybind,
    "send_osc": _build_send_osc,
    "chatbox": _build_chatbox,
    "run_program": _build_run_program,
    "wait": _build_wait,
    "set_variable": _build_set_variable,
    "play_sound": _build_play_sound,
    "random": _build_random,
}