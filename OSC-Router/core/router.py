"""
core/router.py
──────────────
OscRouter: merges OSC values from named sources and fans out to
multiple outputs, each with its own source subscription list.

Data flow:
  Source A (port 9011) ─┐
  Source B (port 9012) ─┤─► per-output merge ─► Output 1 (gets A+B)
  Source C (port 9013) ─┘                    ├─► Output 2 (gets A only)
                                              └─► Output 3 (gets B+C)

Merge rules per output (index 0 = highest priority):
  • Different addresses            → all forwarded
  • Same address, same value       → forwarded once
  • Same address, different value  → highest-priority source wins

Only changed values per output are forwarded (no chattering).
"""

import threading
import time
from dataclasses import dataclass, field

from core.source import OscSource
from pythonosc.udp_client import SimpleUDPClient


@dataclass
class OutputTarget:
    name:        str
    ip:          str
    port:        int
    source_names: list[str]          # ordered: index 0 = highest priority
    _client:     SimpleUDPClient | None = field(default=None, repr=False)
    _last:       dict[str, tuple]   = field(default_factory=dict, repr=False)
    fwd_total:   int                 = 0
    failed:      bool                = False

    def open(self):
        try:
            self._client = SimpleUDPClient(self.ip, self.port)
            self.failed  = False
        except Exception as e:
            print(f"[Router] Output '{self.name}' client error: {e}")
            self.failed = True

    def close(self):
        self._client = None
        self._last.clear()
        self.fwd_total = 0
        self.failed    = False

    def send_merged(self, sources: list[OscSource]):
        """
        Build a merged snapshot from subscribed sources (priority order)
        and forward any changed values to this output.
        """
        if self._client is None or self.failed:
            return

        # Filter to subscribed sources, preserving priority order
        subscribed = [s for s in sources if s.name in self.source_names]
        # Sort by priority (position in source_names list, lower = higher priority)
        subscribed.sort(key=lambda s: self.source_names.index(s.name)
        if s.name in self.source_names else 999)

        # Merge: reverse so highest-priority wins by writing last
        merged: dict[str, tuple] = {}
        for src in reversed(subscribed):
            merged.update(src.snapshot())

        # Only send what changed
        to_send = {addr: args for addr, args in merged.items()
                   if self._last.get(addr) != args}

        if to_send:
            for addr, args in to_send.items():
                try:
                    self._client.send_message(addr, list(args))
                except Exception as e:
                    print(f"[Router] Send error on '{self.name}': {e}")
            self._last.update(to_send)
            self.fwd_total += len(to_send)


class OscRouter:
    INTERVAL = 0.05   # 20 Hz

    def __init__(self):
        self.sources: list[OscSource]   = []
        self.outputs: list[OutputTarget] = []
        self._running  = False
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def live_conflicts(self) -> int:
        """Addresses currently contested across ALL sources."""
        seen: dict[str, set] = {}
        for src in self.sources:
            for addr, args in src.snapshot().items():
                try:
                    seen.setdefault(addr, set()).add(args)
                except TypeError:
                    pass
        return sum(1 for v in seen.values() if len(v) > 1)

    @property
    def total_forwarded(self) -> int:
        return sum(o.fwd_total for o in self.outputs)

    def start(self) -> dict[str, list[str]]:
        """
        Start all sources and outputs.
        Returns {"sources": [failed names], "outputs": [failed names]}.
        """
        if self._running:
            return {"sources": [], "outputs": []}

        failed_sources = [s.name for s in self.sources if not s.start()]

        for out in self.outputs:
            out.open()
        failed_outputs = [o.name for o in self.outputs if o.failed]

        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return {"sources": failed_sources, "outputs": failed_outputs}

    def stop(self):
        self._running = False
        for s in self.sources:
            s.stop()
        for o in self.outputs:
            o.close()

    def _loop(self):
        while self._running:
            for out in self.outputs:
                out.send_merged(self.sources)
            time.sleep(self.INTERVAL)