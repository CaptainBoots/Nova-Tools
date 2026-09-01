"""
ui/router_tab.py
────────────────
Router tab with two inner subtabs:
  • Sources  — input listeners (name + port)
  • Outputs  — output targets (name + ip + port + source checkboxes)

Plus status bar, Start/Stop/Restart, and live stats at the top.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QTabWidget, QScrollArea,
)

from ui import theme
from ui.theme import StripeBackground


class RouterTab(StripeBackground):
    def __init__(self, cfg, router, save_cb, start_cb, stop_cb, restart_cb,
                 settings_cb, help_cb, parent=None):
        super().__init__(parent)
        self._cfg         = cfg
        self._router      = router
        self._save_cb     = save_cb
        self._start_cb    = start_cb
        self._stop_cb     = stop_cb
        self._restart_cb  = restart_cb
        self._settings_cb = settings_cb
        self._help_cb     = help_cb

        self._src_rows: list[dict] = []
        self._out_rows: list[dict] = []

        self._build()

    # ── Top section (always visible) ────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        # ── Status bar ────────────────────────────────────────────────────────
        sf = QWidget()
        sf.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        sf_layout = QHBoxLayout(sf)
        sf_layout.setContentsMargins(10, 6, 10, 6)

        status_caption = QLabel("Status:")
        status_caption.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        status_caption.setFont(theme.qt_font(9))
        sf_layout.addWidget(status_caption)

        self._status_lbl = QLabel("Stopped")
        self._status_lbl.setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
        self._status_lbl.setFont(theme.qt_font(9, bold=True))
        sf_layout.addWidget(self._status_lbl)
        sf_layout.addStretch(1)

        outer.addWidget(sf)

        # ── Control buttons ───────────────────────────────────────────────────
        bf = QHBoxLayout()
        bf.setContentsMargins(0, 4, 0, 4)

        for text, cmd, fg in (
                ("▶  Start",   self._start_cb,   theme.ACCENT),
                ("■  Stop",    self._stop_cb,    theme.ACCENT),
                ("↺  Restart", self._restart_cb, theme.ACCENT),
        ):
            b = QPushButton(text)
            b.setFont(theme.qt_font(10, bold=True))
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumWidth(110)
            b.setStyleSheet(
                f"QPushButton {{ background-color: {theme.PANEL}; color: {fg}; border: none; padding: 6px 14px; }}"
                f"QPushButton:hover {{ background-color: {theme.BORDER}; color: {theme.TEXT}; }}"
            )
            b.clicked.connect(cmd)
            bf.addWidget(b)

        bf.addStretch(1)

        help_btn = QPushButton("? Help")
        help_btn.setStyleSheet(theme.subtle_button_qss())
        help_btn.setFont(theme.qt_font(9))
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.clicked.connect(self._help_cb)
        bf.addWidget(help_btn)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setStyleSheet(theme.subtle_button_qss())
        settings_btn.setFont(theme.qt_font(9))
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.clicked.connect(self._settings_cb)
        bf.addWidget(settings_btn)

        outer.addLayout(bf)

        # ── Live stats ────────────────────────────────────────────────────────
        lf = QFrame()
        lf.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
        lf_layout = QVBoxLayout(lf)
        lf_layout.setContentsMargins(10, 6, 10, 6)
        lf_layout.setSpacing(2)

        stats_caption = QLabel("Live Stats")
        stats_caption.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
        stats_caption.setFont(theme.qt_font(9, bold=True))
        lf_layout.addWidget(stats_caption)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        self._lbl_fwd      = QLabel("Forwarded: —")
        self._lbl_conflict = QLabel("Conflicts: —")
        self._lbl_sources  = QLabel("Sources: 0 / 0")
        self._lbl_outputs  = QLabel("Outputs: 0 / 0")
        for lbl in (self._lbl_fwd, self._lbl_conflict, self._lbl_sources, self._lbl_outputs):
            lbl.setStyleSheet(f"color: {theme.TEXT}; background: transparent; border: none;")
            lbl.setFont(theme.qt_font(9))
            stats_row.addWidget(lbl)
        stats_row.addStretch(1)
        lf_layout.addLayout(stats_row)

        outer.addWidget(lf)

        # ── Inner tabs (Sources / Outputs) ───────────────────────────────────
        nb = QTabWidget()
        nb.setDocumentMode(True)
        nb.setStyleSheet(
            f"QTabBar::tab {{ background: {theme.PANEL}; color: {theme.SUBTEXT}; padding: 4px 12px; "
            f"border: none; font-weight: normal; }}"
            f"QTabBar::tab:selected {{ background: {theme.PANEL}; color: {theme.ACCENT2}; font-weight: bold; }}"
            f"QTabWidget::pane {{ border: none; background: {theme.BG}; }}"
        )

        self._src_tab = self._make_sources_tab()
        self._out_tab = self._make_outputs_tab()
        nb.addTab(self._src_tab, "  Sources  ")
        nb.addTab(self._out_tab, "  Outputs  ")

        outer.addWidget(nb, 1)

    # ── Sources subtab ────────────────────────────────────────────────────────

    def _make_sources_tab(self) -> QWidget:
        frame = QWidget()
        frame.setStyleSheet(f"background-color: {theme.BG};")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        toolbar = QWidget()
        toolbar.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 4, 4, 4)

        cap = QLabel("Input Sources")
        cap.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
        cap.setFont(theme.qt_font(9, bold=True))
        toolbar_layout.addWidget(cap)

        add_btn = QPushButton("+ Add Source")
        add_btn.setStyleSheet(
            f"QPushButton {{ background-color: {theme.PANEL}; color: {theme.ACCENT2}; border: none; padding: 2px 8px; }}"
            f"QPushButton:hover {{ background-color: {theme.BORDER}; color: {theme.TEXT}; }}"
        )
        add_btn.setFont(theme.qt_font(9))
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_source)
        toolbar_layout.addWidget(add_btn)
        toolbar_layout.addStretch(1)

        layout.addWidget(toolbar)

        self._src_scroll, self._src_inner_layout = self._scrollable()
        layout.addWidget(self._src_scroll, 1)

        return frame

    # ── Outputs subtab ────────────────────────────────────────────────────────

    def _make_outputs_tab(self) -> QWidget:
        frame = QWidget()
        frame.setStyleSheet(f"background-color: {theme.BG};")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        toolbar = QWidget()
        toolbar.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 4, 4, 4)

        cap = QLabel("Output Targets")
        cap.setStyleSheet(f"color: {theme.ACCENT2}; background: transparent; border: none;")
        cap.setFont(theme.qt_font(9, bold=True))
        toolbar_layout.addWidget(cap)

        add_btn = QPushButton("+ Add Output")
        add_btn.setStyleSheet(
            f"QPushButton {{ background-color: {theme.PANEL}; color: {theme.ACCENT2}; border: none; padding: 2px 8px; }}"
            f"QPushButton:hover {{ background-color: {theme.BORDER}; color: {theme.TEXT}; }}"
        )
        add_btn.setFont(theme.qt_font(9))
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_output)
        toolbar_layout.addWidget(add_btn)
        toolbar_layout.addStretch(1)

        layout.addWidget(toolbar)

        self._out_scroll, self._out_inner_layout = self._scrollable()
        layout.addWidget(self._out_scroll, 1)

        return frame

    # ── Source rows ───────────────────────────────────────────────────────────

    def add_source_row(self, name: str = "Source", port: int = 9001):
        idx = len(self._src_rows)
        card = QFrame()
        card.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
        grid = QGridLayout(card)
        grid.setContentsMargins(8, 6, 8, 6)

        idx_lbl = QLabel(f"#{idx + 1}")
        idx_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        idx_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        idx_lbl.setFont(theme.qt_font(8))
        grid.addWidget(idx_lbl, 0, 0)

        name_e = self._entry(name)
        grid.addWidget(name_e, 0, 1)
        grid.setColumnStretch(1, 1)

        port_cap = QLabel("Port:")
        port_cap.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        port_cap.setFont(theme.qt_font(9))
        grid.addWidget(port_cap, 0, 2)

        port_e = self._entry(str(port), width=60)
        grid.addWidget(port_e, 0, 3)

        stats = QLabel("●")
        stats.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        stats.setFont(theme.qt_font(9))
        grid.addWidget(stats, 0, 4)

        rm_btn = QPushButton("✕")
        rm_btn.setStyleSheet(
            f"QPushButton {{ background-color: {theme.PANEL}; color: {theme.RED}; border: none; padding: 2px 6px; }}"
            f"QPushButton:hover {{ background-color: {theme.BORDER}; }}"
        )
        rm_btn.setFont(theme.qt_font(9))
        rm_btn.setCursor(Qt.PointingHandCursor)
        rm_btn.clicked.connect(lambda _checked=False, i=idx: self._remove_source(i))
        grid.addWidget(rm_btn, 0, 5)

        self._src_inner_layout.insertWidget(self._src_inner_layout.count() - 1, card)

        row = {"frame": card, "name_entry": name_e, "port_entry": port_e, "stats_label": stats}
        self._src_rows.append(row)

        for e in (name_e, port_e):
            e.editingFinished.connect(self._on_source_change)

    def _add_source(self):
        self.add_source_row("Source", 9010 + len(self._src_rows) + 1)
        self._on_source_change()
        self._rebuild_output_source_checks()

    def _remove_source(self, idx: int):
        if idx >= len(self._src_rows):
            return
        row = self._src_rows.pop(idx)
        self._src_inner_layout.removeWidget(row["frame"])
        row["frame"].setParent(None)
        row["frame"].deleteLater()
        self._on_source_change()
        self._rebuild_output_source_checks()

    def _on_source_change(self, _=None):
        self._cfg["sources"] = self._collect_sources()
        self._save_cb()

    def _collect_sources(self) -> list[dict]:
        out = []
        for r in self._src_rows:
            name = r["name_entry"].text().strip() or "Source"
            try:
                port = int(r["port_entry"].text())
            except ValueError:
                port = 9001
            out.append({"name": name, "port": port})
        return out

    def source_names(self) -> list[str]:
        return [r["name_entry"].text().strip() or "Source" for r in self._src_rows]

    # ── Output rows ───────────────────────────────────────────────────────────

    def add_output_row(self, name: str = "Output", ip: str = "127.0.0.1",
                       port: int = 9000, subscribed: list[str] | None = None):
        if subscribed is None:
            subscribed = self.source_names()

        idx = len(self._out_rows)
        card = QFrame()
        card.setStyleSheet(f"background-color: {theme.PANEL}; border: 1px solid {theme.BORDER};")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ── Header row ────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        hdr_grid = QGridLayout(hdr)
        hdr_grid.setContentsMargins(8, 8, 8, 4)

        idx_lbl = QLabel(f"#{idx + 1}")
        idx_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        idx_lbl.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        idx_lbl.setFont(theme.qt_font(8))
        hdr_grid.addWidget(idx_lbl, 0, 0)

        name_e = self._entry(name)
        hdr_grid.addWidget(name_e, 0, 1)
        hdr_grid.setColumnStretch(1, 1)

        ip_cap = QLabel("IP:")
        ip_cap.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        ip_cap.setFont(theme.qt_font(9))
        hdr_grid.addWidget(ip_cap, 0, 2)

        ip_e = self._entry(ip)
        hdr_grid.addWidget(ip_e, 0, 3)
        hdr_grid.setColumnStretch(3, 1)

        port_cap = QLabel("Port:")
        port_cap.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        port_cap.setFont(theme.qt_font(9))
        hdr_grid.addWidget(port_cap, 0, 4)

        port_e = self._entry(str(port), width=60)
        hdr_grid.addWidget(port_e, 0, 5)

        stats = QLabel("●")
        stats.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        stats.setFont(theme.qt_font(9))
        hdr_grid.addWidget(stats, 0, 6)

        rm_btn = QPushButton("✕")
        rm_btn.setStyleSheet(
            f"QPushButton {{ background-color: {theme.PANEL}; color: {theme.RED}; border: none; padding: 2px 6px; }}"
            f"QPushButton:hover {{ background-color: {theme.BORDER}; }}"
        )
        rm_btn.setFont(theme.qt_font(9))
        rm_btn.setCursor(Qt.PointingHandCursor)
        rm_btn.clicked.connect(lambda _checked=False, i=idx: self._remove_output(i))
        hdr_grid.addWidget(rm_btn, 0, 7)

        card_layout.addWidget(hdr)

        # ── Source checkboxes ─────────────────────────────────────────────────
        check_frame = QWidget()
        check_frame.setStyleSheet(f"background-color: {theme.PANEL}; border: none;")
        check_layout = QHBoxLayout(check_frame)
        check_layout.setContentsMargins(12, 0, 12, 8)

        recv_cap = QLabel("Receives from:")
        recv_cap.setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        recv_cap.setFont(theme.qt_font(8))
        check_layout.addWidget(recv_cap)

        src_vars: dict[str, QCheckBox] = {}
        for src_name in self.source_names():
            cb = QCheckBox(src_name)
            cb.setStyleSheet(
                f"QCheckBox {{ color: {theme.TEXT}; background: transparent; border: none; }}"
                f"QCheckBox::indicator {{ width: 13px; height: 13px; border: 1px solid {theme.BORDER}; "
                f"background: {theme.PANEL}; }}"
                f"QCheckBox::indicator:checked {{ background: {theme.ACCENT2}; border: 1px solid {theme.ACCENT2}; }}"
            )
            cb.setFont(theme.qt_font(9))
            cb.setCursor(Qt.PointingHandCursor)
            cb.setChecked(src_name in subscribed)
            cb.toggled.connect(self._on_output_change)
            check_layout.addWidget(cb)
            src_vars[src_name] = cb

        check_layout.addStretch(1)
        card_layout.addWidget(check_frame)

        self._out_inner_layout.insertWidget(self._out_inner_layout.count() - 1, card)

        row_data = {
            "frame":       card,
            "name_entry":  name_e,
            "ip_entry":    ip_e,
            "port_entry":  port_e,
            "stats_label": stats,
            "src_vars":    src_vars,
        }
        self._out_rows.append(row_data)

        for e in (name_e, ip_e, port_e):
            e.editingFinished.connect(self._on_output_change)

    def _add_output(self):
        self.add_output_row(
            name="Output",
            ip="127.0.0.1",
            port=9000 + len(self._out_rows),
            subscribed=self.source_names(),
        )
        self._on_output_change()

    def _remove_output(self, idx: int):
        if idx >= len(self._out_rows):
            return
        row = self._out_rows.pop(idx)
        self._out_inner_layout.removeWidget(row["frame"])
        row["frame"].setParent(None)
        row["frame"].deleteLater()
        self._on_output_change()

    def _on_output_change(self, _=None):
        self._cfg["outputs"] = self._collect_outputs()
        self._save_cb()

    def _collect_outputs(self) -> list[dict]:
        out = []
        for r in self._out_rows:
            name = r["name_entry"].text().strip() or "Output"
            ip   = r["ip_entry"].text().strip()   or "127.0.0.1"
            try:
                port = int(r["port_entry"].text())
            except ValueError:
                port = 9000
            sources = [n for n, cb in r["src_vars"].items() if cb.isChecked()]
            out.append({"name": name, "ip": ip, "port": port, "sources": sources})
        return out

    def _rebuild_output_source_checks(self):
        """After sources change, rebuild every output row's checkbox list
        so new sources appear and removed ones disappear. Preserves
        existing checked state by name where possible."""
        current_outputs = self._collect_outputs()

        for r in self._out_rows:
            self._out_inner_layout.removeWidget(r["frame"])
            r["frame"].setParent(None)
            r["frame"].deleteLater()
        self._out_rows.clear()

        for o in current_outputs:
            self.add_output_row(o["name"], o["ip"], o["port"], o["sources"])

    # ── Stats tick ────────────────────────────────────────────────────────────

    def tick(self):
        if self._router.running:
            active_src = sum(1 for s in self._router.sources if s.running)
            total_src  = len(self._router.sources)
            active_out = sum(1 for o in self._router.outputs if not o.failed)
            total_out  = len(self._router.outputs)

            self._lbl_fwd.setText(f"Forwarded: {self._router.total_forwarded:,}")
            self._lbl_conflict.setText(f"Conflicts: {self._router.live_conflicts} live")
            self._lbl_sources.setText(f"Sources: {active_src} / {total_src}")
            self._lbl_outputs.setText(f"Outputs: {active_out} / {total_out}")

            src_by_name = {s.name: s for s in self._router.sources}
            for r in self._src_rows:
                name = r["name_entry"].text().strip()
                src = src_by_name.get(name)
                if src:
                    if src.running:
                        r["stats_label"].setText(f"● {src.rx_count:,} rx")
                        r["stats_label"].setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
                    else:
                        r["stats_label"].setText("✗ failed")
                        r["stats_label"].setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
                else:
                    r["stats_label"].setText("●")
                    r["stats_label"].setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")

            out_by_name = {o.name: o for o in self._router.outputs}
            for r in self._out_rows:
                name = r["name_entry"].text().strip()
                out = out_by_name.get(name)
                if out:
                    if out.failed:
                        r["stats_label"].setText("✗ failed")
                        r["stats_label"].setStyleSheet(f"color: {theme.RED}; background: transparent; border: none;")
                    else:
                        r["stats_label"].setText(f"▶ {out.fwd_total:,} sent")
                        r["stats_label"].setStyleSheet(f"color: {theme.GREEN}; background: transparent; border: none;")
                else:
                    r["stats_label"].setText("●")
                    r["stats_label"].setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")
        else:
            self._lbl_fwd.setText("Forwarded: —")
            self._lbl_conflict.setText("Conflicts: —")
            self._lbl_sources.setText(f"Sources: 0 / {len(self._src_rows)}")
            self._lbl_outputs.setText(f"Outputs: 0 / {len(self._out_rows)}")
            for r in self._src_rows + self._out_rows:
                r["stats_label"].setText("●")
                r["stats_label"].setStyleSheet(f"color: {theme.SUBTEXT}; background: transparent; border: none;")

    def set_status(self, text: str):
        colour = theme.GREEN if "running" in text.lower() else theme.RED
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(f"color: {colour}; background: transparent; border: none;")

    # ── collect_config (for app.py to use at start time) ───────────────────────

    def collect_config(self) -> dict:
        return {
            "sources": self._collect_sources(),
            "outputs": self._collect_outputs(),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _entry(self, value: str = "", width: int = None) -> QLineEdit:
        e = QLineEdit(value)
        e.setFont(theme.qt_font(9))
        e.setStyleSheet(theme.line_edit_qss())
        if width:
            e.setFixedWidth(width)
        return e

    def _scrollable(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background-color: {theme.BG}; border: none;")

        inner = QWidget()
        inner.setStyleSheet(f"background-color: {theme.BG};")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 4, 0)
        inner_layout.setSpacing(3)
        inner_layout.addStretch(1)

        scroll.setWidget(inner)
        return scroll, inner_layout