"""
core/script_engine.py
──────────────────────
The brain of OSC-ScriptMaker. No Qt anywhere in this file — it's driven
entirely by callbacks and background threads, so it can be constructed
and unit-tested with no QApplication in existence.

There is no single shared "connection" here. Every OSC trigger (Input)
carries its own listen host/port, and every OSC-sending action carries
its own send host/port — the engine just keeps exactly one OSCListener
running per unique (host, port) pair that's actually in use by an
enabled OSC trigger right now, opening new ones and closing unused ones
automatically as scripts are added, edited, enabled, or removed. There's
nothing to manually reconnect when you change a trigger's address.

Trigger matching and action execution are both dispatched through the
pluggable registry in core/registry.py rather than being hardcoded here.

Owns:
- a pool of OSC input listeners, one per (host, port) an enabled OSC
  trigger currently uses, kept in sync roughly once a second
- a pool of cached outgoing OSC clients
- the shared variable store
- the timer-trigger loop (shares the same background thread as the
  listener sync tick)
- action-chain execution (each firing script runs its chain on its own
  daemon thread so a `wait` action never blocks any listener)
"""

from __future__ import annotations

import threading
import time

from Actions.context import ActionContext
from core.registry import run_action, input_matches, timer_interval
from core.conditions import evaluate_condition
from core.osc_io import OSCListener, OSCSenderPool

MAX_ACTIONS_PER_EVENT = 200   # runaway-loop guard shared across a fire chain
LISTENER_SYNC_INTERVAL = 1.0  # seconds between checking triggers for new/removed listen addresses


class _BudgetExceeded(Exception):
    pass


class ScriptEngine:
    def __init__(self, get_scripts_cb, log_cb=None):
        self._get_scripts = get_scripts_cb
        self._log = log_cb or (lambda msg: None)

        self._running = False
        self._listeners: dict[tuple[str, int], OSCListener] = {}
        self._listeners_lock = threading.Lock()
        self._senders = OSCSenderPool()

        # keyed by (host, port, address) so the same address on two
        # different listen endpoints tracks its own rising/falling state
        self._last_osc_values: dict[tuple[str, int, str], object] = {}
        self._variables: dict[str, object] = {}
        self._last_var_values: dict[str, object] = {}

        self._timer_next_fire: dict[int, float] = {}
        self._bg_thread: threading.Thread | None = None
        self._bg_stop = threading.Event()

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._sync_listeners()
        self._bg_stop.clear()
        self._timer_next_fire.clear()
        self._bg_thread = threading.Thread(target=self._background_loop, daemon=True)
        self._bg_thread.start()

    def stop(self):
        self._running = False
        self._bg_stop.set()
        if self._bg_thread:
            self._bg_thread.join(timeout=1)
        self._bg_thread = None
        with self._listeners_lock:
            for listener in self._listeners.values():
                listener.stop()
            self._listeners.clear()

    @property
    def is_running(self) -> bool:
        return self._running

    def shutdown(self):
        self.stop()
        self._senders.close_all()

    def listening_addresses(self) -> list[tuple[str, int]]:
        """What's actually bound right now — handy for a status display."""
        with self._listeners_lock:
            return list(self._listeners.keys())

    # ── Listener sync (one OSCListener per host:port an enabled OSC
    #    trigger currently needs — no manual connect step) ───────────────

    def _needed_addresses(self) -> set[tuple[str, int]]:
        needed: set[tuple[str, int]] = set()
        for script in self._safe_scripts():
            trig = script.trigger
            if not script.enabled or trig.kind != "osc":
                continue
            host = (trig.host or "127.0.0.1").strip()
            try:
                port = int(trig.port or 9001)
            except (TypeError, ValueError):
                continue
            needed.add((host, port))
        return needed

    def _sync_listeners(self):
        if not self._running:
            return
        needed = self._needed_addresses()
        with self._listeners_lock:
            for addr in list(self._listeners.keys()):
                if addr not in needed:
                    self._listeners.pop(addr).stop()
                    self._log(f"Stopped listening on {addr[0]}:{addr[1]} (no trigger uses it anymore)")
            for host, port in needed:
                addr = (host, port)
                if addr in self._listeners:
                    continue
                try:
                    listener = OSCListener(
                        host, port,
                        lambda a, v, h=host, p=port: self._on_osc_message(h, p, a, v),
                    )
                    listener.start()
                    self._listeners[addr] = listener
                    self._log(f"Listening on {host}:{port}")
                except OSError as exc:
                    self._log(f"\u26a0 Could not listen on {host}:{port} \u2014 {exc}")

    # ── Variables ────────────────────────────────────────────────────────

    def get_variable(self, name: str, default=None):
        return self._variables.get(name, default)

    def set_variable(self, name: str, value, _budget=None):
        if not name:
            return
        prev = self._variables.get(name)
        self._variables[name] = value
        self._last_var_values[name] = prev
        self._check_variable_triggers(name, value, prev, _budget)

    # ── Trigger dispatch (via core/registry) ─────────────────────────────

    def _on_osc_message(self, host: str, port: int, address: str, value):
        key = (host, port, address)
        prev = self._last_osc_values.get(key)
        self._last_osc_values[key] = value
        for script in self._safe_scripts():
            trig = script.trigger
            if not script.enabled or trig.kind != "osc":
                continue
            if (trig.host or "127.0.0.1").strip() != host:
                continue
            try:
                if int(trig.port or 9001) != port:
                    continue
            except (TypeError, ValueError):
                continue
            if not input_matches(trig, address, value):
                continue
            if evaluate_condition(trig.condition, value, trig.value, trig.value2, prev):
                self._fire(script, value)

    def _check_variable_triggers(self, name: str, value, prev, _budget):
        for script in self._safe_scripts():
            trig = script.trigger
            if not script.enabled or trig.kind != "variable":
                continue
            if not input_matches(trig, name, value):
                continue
            if evaluate_condition(trig.condition, value, trig.value, trig.value2, prev):
                self._fire(script, value, _budget)

    def _background_loop(self):
        """Single background thread doing two jobs on the same tick:
        keeping the listener pool in sync with whatever OSC triggers now
        exist, and driving timer triggers. Combined so adding/removing a
        script never needs a separate restart step for either."""
        last_sync = 0.0
        while not self._bg_stop.is_set():
            now = time.time()

            if now - last_sync >= LISTENER_SYNC_INTERVAL:
                self._sync_listeners()
                last_sync = now

            for script in self._safe_scripts():
                trig = script.trigger
                if not script.enabled or trig.kind != "timer":
                    continue
                interval = timer_interval(trig)
                next_fire = self._timer_next_fire.get(script.uid)
                if next_fire is None:
                    self._timer_next_fire[script.uid] = now + interval
                    continue
                if now >= next_fire:
                    self._timer_next_fire[script.uid] = now + interval
                    self._fire(script, None)

            self._bg_stop.wait(0.2)

    def _safe_scripts(self):
        try:
            return list(self._get_scripts())
        except Exception:
            return []

    # ── Firing / execution (via core/registry) ───────────────────────────

    def _fire(self, script, trigger_value, _budget=None):
        self._log(f"\u25b6 {script.name} fired")
        t = threading.Thread(
            target=self._run_chain, args=(script, trigger_value, _budget), daemon=True
        )
        t.start()

    def _run_chain(self, script, trigger_value, _budget=None):
        budget = _budget if _budget is not None else {"n": 0}
        for action in script.actions:
            try:
                self._run_action(action, trigger_value, budget)
            except _BudgetExceeded:
                self._log(f"\u26a0 {script.name}: action limit reached, stopping (possible loop)")
                return
            except Exception as exc:
                self._log(f"\u26a0 {script.name}: action error \u2014 {exc}")

    def _run_action(self, action, trigger_value, budget):
        budget["n"] = budget.get("n", 0) + 1
        if budget["n"] > MAX_ACTIONS_PER_EVENT:
            raise _BudgetExceeded()

        ctx = ActionContext(
            trigger_value=trigger_value,
            senders=self._senders,
            set_variable=lambda name, val: self.set_variable(name, val, budget),
            run_sub_action=lambda sub: self._run_action(sub, trigger_value, budget),
        )
        run_action(action, ctx)