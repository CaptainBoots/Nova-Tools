"""
core/models.py
──────────────
Pure data model for OSC-ScriptMaker. No Qt, no OSC, no threads — just
plain dataclasses plus to_dict/from_dict for JSON persistence.

A Script = one Trigger + an ordered chain of Actions. When the trigger
fires (and its condition passes), the actions run in order, top to
bottom, on a background thread (see core/script_engine.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

# ── Trigger ──────────────────────────────────────────────────────────────

TRIGGER_KINDS = ("osc", "timer", "variable")

CONDITIONS = (
    "any", "equals", "not_equals", "greater", "less", "in_range",
    "rising_edge", "falling_edge", "changed",
)

# Conditions that need one comparison value box shown in the UI.
CONDITIONS_NEEDING_VALUE = ("equals", "not_equals", "greater", "less", "in_range")
# Conditions that need a second (max) value box.
CONDITIONS_NEEDING_VALUE2 = ("in_range",)


@dataclass
class Trigger:
    kind: str = "osc"            # "osc" | "timer" | "variable"
    host: str = "127.0.0.1"      # listen host, for kind == "osc" — set per-input, no shared default
    port: str = "9001"           # listen port, for kind == "osc"
    address: str = ""            # OSC address, for kind == "osc"
    var_name: str = ""           # variable name, for kind == "variable"
    interval_s: float = 5.0      # seconds, for kind == "timer"
    condition: str = "any"
    value: str = ""              # comparison value (stringly typed, cast at eval time)
    value2: str = ""             # range max, only used when condition == "in_range"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Trigger":
        t = Trigger()
        for k in ("kind", "host", "port", "address", "var_name", "condition", "value", "value2"):
            if k in d:
                setattr(t, k, d[k])
        if "interval_s" in d:
            try:
                t.interval_s = float(d["interval_s"])
            except (TypeError, ValueError):
                pass
        return t


# ── Action ───────────────────────────────────────────────────────────────

ACTION_KINDS = (
    "keybind", "send_osc", "chatbox", "run_program", "wait",
    "set_variable", "play_sound", "random",
)

VALUE_MODES = ("static", "forward", "transform")


@dataclass
class Action:
    kind: str = "keybind"

    # keybind
    keys: list = field(default_factory=list)     # e.g. ["ctrl", "alt", "u"]
    hold_ms: int = 0                              # 0 = quick tap

    # send_osc
    host: str = "127.0.0.1"                        # every action sets its own target, no shared default
    port: str = "9000"
    address: str = ""
    value_mode: str = "static"                     # static | forward | transform
    static_value: str = ""
    in_min: float = 0.0
    in_max: float = 1.0
    out_min: float = 0.0
    out_max: float = 1.0
    invert: bool = False
    as_bool: bool = False

    # chatbox
    text: str = ""                                  # "{value}" is replaced with trigger value
    send_immediately: bool = True
    play_sfx: bool = False
    chatbox_target: str = "vrchat"                   # "vrchat" | "channel"
    chatbox_channel: int = 1                         # 1-10, used when chatbox_target == "channel"

    # run_program
    program_path: str = ""
    program_args: str = ""

    # wait
    wait_ms: int = 500

    # set_variable
    var_name: str = ""
    var_value_mode: str = "static"                  # static | forward
    var_static_value: str = ""

    # play_sound
    sound_path: str = ""

    # random — one sub-action is picked and run each time; sub-actions
    # are themselves single Actions (not chains), one nesting level only.
    sub_actions: list = field(default_factory=list)  # list[Action]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sub_actions"] = [a.to_dict() for a in self.sub_actions]
        return d

    @staticmethod
    def from_dict(d: dict) -> "Action":
        a = Action()
        for k, v in d.items():
            if k == "sub_actions":
                continue
            if hasattr(a, k):
                setattr(a, k, v)
        a.sub_actions = [Action.from_dict(sd) for sd in d.get("sub_actions", [])]
        return a


# ── Script ───────────────────────────────────────────────────────────────

@dataclass
class Script:
    uid: int = 0
    name: str = "New Script"
    enabled: bool = True
    trigger: Trigger = field(default_factory=Trigger)
    actions: list = field(default_factory=list)   # list[Action]

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "name": self.name,
            "enabled": self.enabled,
            "trigger": self.trigger.to_dict(),
            "actions": [a.to_dict() for a in self.actions],
        }

    @staticmethod
    def from_dict(d: dict) -> "Script":
        s = Script()
        s.uid = d.get("uid", 0)
        s.name = d.get("name", "New Script")
        s.enabled = d.get("enabled", True)
        s.trigger = Trigger.from_dict(d.get("trigger", {}))
        s.actions = [Action.from_dict(ad) for ad in d.get("actions", [])]
        return s


def default_action(kind: str = "keybind") -> Action:
    return Action(kind=kind)


def default_script(uid: int) -> Script:
    return Script(uid=uid, name=f"Script {uid}", actions=[default_action()])