"""
Actions/context.py
──────────────────────────
ActionContext is the small bundle of engine hooks every action module
needs. Keeping it as one plain dataclass (rather than passing the whole
ScriptEngine in) keeps each action module trivially testable on its
own, with no import back onto script_engine.py.

Every OSC-sending action (send_osc, chatbox) carries its own host/port
directly on the Action itself — there's no shared "default connection"
to fall back to, so this context stays deliberately small.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

from core.osc_io import OSCSenderPool


@dataclass
class ActionContext:
    trigger_value: Any                            # the value that caused this chain to fire (None for timer)
    senders: OSCSenderPool
    set_variable: Callable[[str, Any], None]       # (name, value) -> None
    run_sub_action: Callable[[Any], None]          # (Action) -> None, used by the "random" action kind