"""
ui/script_card.py
───────────────────
ScriptCard: one script's full editor — enabled toggle, name, a
collapsible trigger editor (kind dropdown from core.registry,
condition + comparison value boxes), and its ordered chain of
ActionRows with reorder/add/remove.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton,
)

from core.registry import INPUTS
from core.models import (
    Script, Action, CONDITIONS, CONDITIONS_NEEDING_VALUE, CONDITIONS_NEEDING_VALUE2,
)
from ui import theme
from ui.circle_toggle import CircleToggle
from ui.action_row import ActionRow, _entry, _row_label, _combo  # reuse the same small helpers

CONDITION_LABELS = {
    "any": "Any message", "equals": "Equals", "not_equals": "Not equals",
    "greater": "Greater than", "less": "Less than", "in_range": "In range",
    "rising_edge": "Rising edge (false→true)", "falling_edge": "Falling edge (true→false)",
    "changed": "Changed",
}


class ScriptCard(QFrame):
    def __init__(self, script: Script, on_remove, parent=None):
        super().__init__(parent)
        self.script = script
        self.on_remove = on_remove
        self._expanded = True
        self._action_rows: list[ActionRow] = []

        self.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()

        self._enabled_toggle = CircleToggle(enabled=self.script.enabled, color=theme.GREEN)
        self._enabled_toggle.toggled.connect(self._on_enabled_toggled)
        hdr.addWidget(self._enabled_toggle)

        arrow = QLabel("▼")
        arrow.setCursor(Qt.PointingHandCursor)
        arrow.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
        arrow.setFont(theme.qt_font(10, bold=True))
        arrow.mousePressEvent = lambda _e: self._toggle_expanded()
        self._arrow_lbl = arrow
        hdr.addWidget(arrow)

        self._name_entry = QLineEdit(self.script.name)
        self._name_entry.setFixedWidth(180)
        self._name_entry.setFont(theme.qt_font(10, bold=True))
        self._name_entry.setStyleSheet(
            f"QLineEdit {{ background-color: {theme.PANEL}; color: {theme.ACCENT2}; "
            f"border: none; padding: 1px 4px; }}"
        )
        self._name_entry.textChanged.connect(lambda t: setattr(self.script, "name", t))
        hdr.addWidget(self._name_entry)
        hdr.addStretch(1)

        rm_btn = QLabel("✕")
        rm_btn.setCursor(Qt.PointingHandCursor)
        rm_btn.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        rm_btn.setFont(theme.qt_font(11))
        rm_btn.mousePressEvent = lambda _e: self.on_remove(self)
        hdr.addWidget(rm_btn)

        outer.addLayout(hdr)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
        outer.addWidget(divider)

        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(4, 2, 4, 2)
        body_layout.setSpacing(8)
        outer.addWidget(self._body)

        self._build_trigger_section(body_layout)
        self._build_actions_section(body_layout)

    def _toggle_expanded(self):
        self._expanded = not self._expanded
        self._arrow_lbl.setText("▼" if self._expanded else "▶")
        self._body.setVisible(self._expanded)

    def _on_enabled_toggled(self, checked: bool):
        self.script.enabled = checked

    # ── Trigger section ───────────────────────────────────────────────────

    def _build_trigger_section(self, parent_layout):
        cap = QLabel("TRIGGER")
        cap.setStyleSheet(theme.section_caption_qss(bg=theme.BORDER))
        cap.setFont(theme.qt_font(8, bold=True))
        parent_layout.addWidget(cap)

        trig = self.script.trigger

        kind_row = QHBoxLayout()
        kind_row.addWidget(_row_label("Type:", 50))
        kind_combo = _combo([(i["id"], i["label"]) for i in INPUTS], trig.kind)
        kind_row.addWidget(kind_combo)
        kind_row.addStretch(1)
        parent_layout.addLayout(kind_row)

        # Kind-specific single field: OSC address / timer interval / variable name
        key_row = QHBoxLayout()
        self._key_label = _row_label("Address:", 60)
        key_row.addWidget(self._key_label)
        self._key_edit = _entry(self._current_key_value(trig), 200)
        self._key_edit.textChanged.connect(self._on_key_changed)
        key_row.addWidget(self._key_edit)
        key_row.addStretch(1)
        parent_layout.addLayout(key_row)

        # Listen host/port — only relevant for kind == "osc". Each OSC
        # trigger owns its own listen address; there's no shared default,
        # so this is where it's set.
        self._host_port_wrap = QWidget()
        hp_layout = QHBoxLayout(self._host_port_wrap)
        hp_layout.setContentsMargins(0, 0, 0, 0)
        hp_layout.addWidget(_row_label("Listen on:", 60))
        self._host_edit = _entry(trig.host, 90)
        self._host_edit.textChanged.connect(lambda t: setattr(trig, "host", t))
        hp_layout.addWidget(self._host_edit)
        hp_layout.addWidget(_row_label(":", 6))
        self._port_edit = _entry(trig.port, 55)
        self._port_edit.textChanged.connect(lambda t: setattr(trig, "port", t))
        hp_layout.addWidget(self._port_edit)
        hp_layout.addStretch(1)
        parent_layout.addWidget(self._host_port_wrap)

        # Condition + comparison value(s) — not applicable to timer triggers
        self._cond_row_wrap = QWidget()
        cond_outer = QVBoxLayout(self._cond_row_wrap)
        cond_outer.setContentsMargins(0, 0, 0, 0)
        cond_outer.setSpacing(4)

        cond_row = QHBoxLayout()
        cond_row.addWidget(_row_label("Condition:", 60))
        self._cond_combo = _combo([(c, CONDITION_LABELS[c]) for c in CONDITIONS], trig.condition)
        self._cond_combo.currentIndexChanged.connect(self._on_condition_changed)
        cond_row.addWidget(self._cond_combo)
        cond_row.addStretch(1)
        cond_outer.addLayout(cond_row)

        val_row = QHBoxLayout()
        val_row.addWidget(_row_label("Value:", 60))
        self._value_edit = _entry(trig.value, 70)
        self._value_edit.textChanged.connect(lambda t: setattr(trig, "value", t))
        val_row.addWidget(self._value_edit)
        self._value2_label = _row_label("to", 20)
        val_row.addWidget(self._value2_label)
        self._value2_edit = _entry(trig.value2, 70)
        self._value2_edit.textChanged.connect(lambda t: setattr(trig, "value2", t))
        val_row.addWidget(self._value2_edit)
        val_row.addStretch(1)
        cond_outer.addLayout(val_row)

        parent_layout.addWidget(self._cond_row_wrap)

        kind_combo.currentIndexChanged.connect(lambda _i: self._on_kind_changed(kind_combo.currentData()))
        self._kind_combo = kind_combo

        self._refresh_trigger_visibility()

    def _current_key_value(self, trig) -> str:
        if trig.kind == "osc":
            return trig.address
        if trig.kind == "variable":
            return trig.var_name
        return str(trig.interval_s)

    def _on_key_changed(self, text: str):
        trig = self.script.trigger
        if trig.kind == "osc":
            trig.address = text
        elif trig.kind == "variable":
            trig.var_name = text
        elif trig.kind == "timer":
            try:
                trig.interval_s = float(text)
            except ValueError:
                pass

    def _on_kind_changed(self, new_kind: str):
        trig = self.script.trigger
        trig.kind = new_kind
        if new_kind == "timer":
            trig.condition = "any"
            self._cond_combo.setCurrentIndex(self._cond_combo.findData("any"))
        self._key_edit.blockSignals(True)
        self._key_edit.setText(self._current_key_value(trig))
        self._key_edit.blockSignals(False)
        self._refresh_trigger_visibility()

    def _on_condition_changed(self, _idx):
        self.script.trigger.condition = self._cond_combo.currentData()
        self._refresh_trigger_visibility()

    def _refresh_trigger_visibility(self):
        trig = self.script.trigger
        if trig.kind == "osc":
            self._key_label.setText("Address:")
            self._key_edit.setPlaceholderText("/avatar/parameters/... (or prefix* wildcard)")
        elif trig.kind == "variable":
            self._key_label.setText("Variable:")
            self._key_edit.setPlaceholderText("myVariable")
        else:
            self._key_label.setText("Interval (s):")
            self._key_edit.setPlaceholderText("5")

        self._cond_row_wrap.setVisible(trig.kind != "timer")
        self._host_port_wrap.setVisible(trig.kind == "osc")
        cond = trig.condition
        self._value_edit.setVisible(cond in CONDITIONS_NEEDING_VALUE)
        self._value2_label.setVisible(cond in CONDITIONS_NEEDING_VALUE2)
        self._value2_edit.setVisible(cond in CONDITIONS_NEEDING_VALUE2)

    # ── Actions section ──────────────────────────────────────────────────

    def _build_actions_section(self, parent_layout):
        cap = QLabel("ACTIONS")
        cap.setStyleSheet(theme.section_caption_qss(bg=theme.BORDER))
        cap.setFont(theme.qt_font(8, bold=True))
        parent_layout.addWidget(cap)

        self._actions_wrap = QVBoxLayout()
        self._actions_wrap.setSpacing(4)
        parent_layout.addLayout(self._actions_wrap)

        for action in self.script.actions:
            self._add_action_row(action)
        if not self.script.actions:
            self._add_action_row(Action())

        add_btn = QPushButton("+ Add Action")
        add_btn.setStyleSheet(theme.accent_button_qss())
        add_btn.setFont(theme.qt_font(9, bold=True))
        add_btn.clicked.connect(lambda: self._add_action_row(Action()))
        parent_layout.addWidget(add_btn)

    def _add_action_row(self, action: Action):
        row = ActionRow(
            action,
            on_remove=self._remove_action_row,
            on_move_up=self._move_action_up,
            on_move_down=self._move_action_down,
            nestable=True,
        )
        self._actions_wrap.addWidget(row)
        self._action_rows.append(row)

    def _remove_action_row(self, row: ActionRow):
        if len(self._action_rows) <= 1:
            return  # a script always needs at least one action row
        self._actions_wrap.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        self._action_rows.remove(row)

    def _move_action_up(self, row: ActionRow):
        idx = self._action_rows.index(row)
        if idx == 0:
            return
        self._swap_rows(idx, idx - 1)

    def _move_action_down(self, row: ActionRow):
        idx = self._action_rows.index(row)
        if idx >= len(self._action_rows) - 1:
            return
        self._swap_rows(idx, idx + 1)

    def _swap_rows(self, i: int, j: int):
        self._action_rows[i], self._action_rows[j] = self._action_rows[j], self._action_rows[i]
        for k in (i, j):
            self._actions_wrap.removeWidget(self._action_rows[k])
        # re-insert in new order at the lower index position
        lo = min(i, j)
        self._actions_wrap.insertWidget(lo, self._action_rows[lo])
        self._actions_wrap.insertWidget(lo + 1, self._action_rows[lo + 1])

    # ── Config I/O ────────────────────────────────────────────────────────

    def get_config(self) -> Script:
        self.script.actions = [row.get_config() for row in self._action_rows]
        return self.script