"""
Qt replacement for ui/builder.py. Same structure: a scrollable list of
page cards, each with a header (enable toggle, title, duration stepper,
reorder arrows, copy/paste page, delete) and a list of slot rows (reorder
arrows, module capsules with optional inline text, add/copy/paste/remove controls).

GPU/VRAM modules use their inline text field as a zero-based GPU index.
"""

import json
import copy
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QFrame, QMenu, QFileDialog,
)

from core.registry import CATEGORIES, MODULE_BY_ID
from ui.circle_toggle import CircleToggle
from ui import theme
from ui.theme import StripeBackground


def _label_btn(
        parent_layout,
        text,
        fg,
        command,
        *,
        bg=None,
        font_size=9,
        bold=True,
        padding="2px 6px",
):
    bg = bg or theme.PANEL

    lbl = QLabel(text)
    lbl.setCursor(Qt.PointingHandCursor)
    lbl.setStyleSheet(
        f"color: {fg}; "
        f"background-color: {bg}; "
        f"padding: {padding}; "
        f"border: none;"
    )
    lbl.setFont(
        theme.qt_font(
            font_size,
            bold=bold,
        )
    )

    def _enter(_e):
        lbl.setStyleSheet(
            f"color: {fg}; "
            f"background-color: {theme.BORDER}; "
            f"padding: {padding}; "
            f"border: none;"
        )

    def _leave(_e):
        lbl.setStyleSheet(
            f"color: {fg}; "
            f"background-color: {bg}; "
            f"padding: {padding}; "
            f"border: none;"
        )

    lbl.enterEvent = _enter
    lbl.leaveEvent = _leave
    lbl.mousePressEvent = lambda _e: command()

    parent_layout.addWidget(lbl)

    return lbl


def _hline(parent_layout):
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(
        f"background-color: {theme.BORDER}; "
        f"border: none;"
    )
    parent_layout.addWidget(line)


class ToastNotification(QLabel):
    """Floating notification popup for clipboard actions."""
    def __init__(self, parent, message, is_error=False):
        super().__init__(message, parent)
        clr = theme.RED if is_error else theme.ACCENT
        self.setStyleSheet(
            f"color: {theme.BG}; "
            f"background-color: {clr}; "
            f"padding: 6px 14px; "
            f"border-radius: 4px; "
            f"font-weight: bold;"
        )
        self.setFont(theme.qt_font(9, bold=True))
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.adjustSize()

        # Center toast at the top of the tab
        px = (parent.width() - self.width()) // 2
        self.move(max(10, px), 10)
        self.show()

        QTimer.singleShot(2000, self.deleteLater)


class BuilderTab(StripeBackground):

    def __init__(self, cfg: dict, save_cb):
        super().__init__()

        self._cfg = cfg
        self._save_cb = save_cb
        self._sel_page = 0

        self._build_ui()


    # ── Toast Notification System ─────────────────────────────────────────

    def _show_toast(self, message, is_error=False):
        ToastNotification(self, message, is_error=is_error)


    # ── System Clipboard Engine ───────────────────────────────────────────

    def _copy_to_clipboard(self, prefix: str, data: dict):
        clipboard = QGuiApplication.clipboard()
        payload = f"{prefix}:{json.dumps(data)}"
        clipboard.setText(payload)

    def _read_from_clipboard(self, prefix: str):
        clipboard = QGuiApplication.clipboard()
        text = clipboard.text().strip()
        if text.startswith(f"{prefix}:"):
            raw_json = text[len(prefix) + 1:]
            try:
                return json.loads(raw_json)
            except json.JSONDecodeError:
                return None
        return None

    def _has_clipboard_prefix(self, prefix: str) -> bool:
        clipboard = QGuiApplication.clipboard()
        return clipboard.text().strip().startswith(f"{prefix}:")


    # ── Layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            4,
            8,
            4,
            8,
        )

        header_row = QHBoxLayout()

        title = QLabel("Output Pages Setup")
        title.setStyleSheet(
            f"color: {theme.TEXT}; "
            f"background: {theme.BG}; "
            f"border: none;"
        )
        title.setFont(
            theme.qt_font(
                11,
                bold=True,
            )
        )

        header_row.addWidget(title)
        header_row.addStretch(1)

        _label_btn(
            header_row,
            "Import All",
            theme.ACCENT2,
            self._import_all_pages,
            font_size=9,
            padding="4px 10px",
        )

        _label_btn(
            header_row,
            "Export All",
            theme.ACCENT2,
            self._export_all_pages,
            font_size=9,
            padding="4px 10px",
        )

        page_paste_clr = theme.ACCENT if self._has_clipboard_prefix("page_cfg") else theme.SUBTEXT
        _label_btn(
            header_row,
            "+ Paste Page",
            page_paste_clr,
            self._paste_page,
            font_size=9,
            padding="4px 10px",
        )

        _label_btn(
            header_row,
            "+ Create Page",
            theme.ACCENT,
            self._add_page,
            font_size=9,
            padding="4px 12px",
        )

        outer.addLayout(header_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "background: transparent; border: none;"
        )

        outer.addWidget(
            self._scroll,
            1,
        )

        self._refresh_pages()


    # ── Refresh ───────────────────────────────────────────────────────────

    def _refresh_pages(self):
        container = QWidget()
        container.setStyleSheet(
            "background: transparent;"
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            0,
            0,
            8,
            0,
        )
        layout.setSpacing(12)

        pages = self._cfg.get(
            "pages",
            [],
        )

        for page_idx, page in enumerate(pages):
            layout.addWidget(
                self._build_page_card(
                    page_idx,
                    page,
                )
            )

        layout.addStretch(1)

        self._scroll.setWidget(container)


    # ── Page card ─────────────────────────────────────────────────────────

    def _build_page_card(self, page_idx, page):
        is_sel = (
                page_idx == self._sel_page
        )

        border_clr = (
            theme.ACCENT
            if is_sel
            else theme.BORDER
        )

        card = QFrame()

        card.setStyleSheet(
            f"background-color: {theme.PANEL}; "
            f"border: 1px solid {border_clr};"
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            12,
            8,
            12,
            8,
        )


        def _select(_evt=None, idx=page_idx):
            if self._sel_page != idx:
                self._sel_page = idx
                self._refresh_pages()


        card.mousePressEvent = _select


        # ── Header row ────────────────────────────────────────────────────

        header = QHBoxLayout()


        def _toggle_enabled(is_enabled):
            page["enabled"] = is_enabled
            self._save()


        chk_toggle = CircleToggle(
            enabled=page.get(
                "enabled",
                True,
            ),
            color=theme.ACCENT,
        )

        chk_toggle.toggled.connect(
            _toggle_enabled
        )

        header.addWidget(chk_toggle)


        # Page reorder arrows
        _label_btn(
            header,
            "▲",
            theme.SUBTEXT,
            lambda pi=page_idx: self._move_page(pi, -1),
            font_size=9,
            padding="1px 3px",
        )

        _label_btn(
            header,
            "▼",
            theme.SUBTEXT,
            lambda pi=page_idx: self._move_page(pi, 1),
            font_size=9,
            padding="1px 3px",
        )


        lbl_title = QLabel(
            f"Page {page_idx + 1}"
        )

        lbl_title.setStyleSheet(
            f"color: {theme.TEXT}; "
            f"background: transparent; "
            f"border: none;"
        )

        lbl_title.setFont(
            theme.qt_font(
                10,
                bold=True,
            )
        )

        header.addWidget(lbl_title)

        header.addSpacing(8)


        dur_lbl = QLabel("Duration:")
        dur_lbl.setStyleSheet(
            f"color: {theme.SUBTEXT}; "
            f"background: transparent; "
            f"border: none;"
        )

        dur_lbl.setFont(
            theme.qt_font(8)
        )

        header.addWidget(dur_lbl)


        counter = QHBoxLayout()
        counter.setSpacing(1)


        dur_entry = QLineEdit(
            str(page.get("duration", 20))
        )

        dur_entry.setFixedWidth(34)
        dur_entry.setAlignment(Qt.AlignCenter)
        dur_entry.setFont(
            theme.qt_font(
                9,
                bold=True,
            )
        )
        dur_entry.setStyleSheet(
            theme.line_edit_qss()
        )


        def _decrement():
            try:
                value = int(
                    dur_entry.text().strip()
                )
            except ValueError:
                value = 1

            dur_entry.setText(
                str(max(1, value - 1))
            )

            _dur_changed()


        def _increment():
            try:
                value = int(
                    dur_entry.text().strip()
                )
            except ValueError:
                value = 20

            dur_entry.setText(
                str(min(3600, value + 1))
            )

            _dur_changed()


        minus_lbl = QLabel("-")
        minus_lbl.setCursor(
            Qt.PointingHandCursor
        )

        minus_lbl.setStyleSheet(
            f"color: {theme.SUBTEXT}; "
            f"background-color: {theme.PANEL}; "
            f"padding: 1px 4px; "
            f"border: none;"
        )

        minus_lbl.setFont(
            theme.qt_font(8)
        )

        minus_lbl.mousePressEvent = (
            lambda _e: _decrement()
        )

        counter.addWidget(minus_lbl)
        counter.addWidget(dur_entry)


        plus_lbl = QLabel("+")
        plus_lbl.setCursor(
            Qt.PointingHandCursor
        )

        plus_lbl.setStyleSheet(
            f"color: {theme.SUBTEXT}; "
            f"background-color: {theme.PANEL}; "
            f"padding: 1px 4px; "
            f"border: none;"
        )

        plus_lbl.setFont(
            theme.qt_font(8)
        )

        plus_lbl.mousePressEvent = (
            lambda _e: _increment()
        )

        counter.addWidget(plus_lbl)


        counter_wrap = QWidget()
        counter_wrap.setLayout(counter)

        counter_wrap.setStyleSheet(
            f"background-color: {theme.BG}; "
            f"border: {theme.BORDER};"
        )

        header.addWidget(counter_wrap)


        def _dur_changed():
            value = dur_entry.text().strip()

            if not value:
                return

            try:
                self._cfg["pages"][page_idx]["duration"] = int(value)
                self._save()
            except (
                    ValueError,
                    KeyError,
                    IndexError,
            ):
                pass


        dur_entry.editingFinished.connect(
            _dur_changed
        )

        header.addStretch(1)

        # Page level [C] (Copy) and [P] (Paste) buttons matching line controls order
        _label_btn(
            header,
            "[C]",
            theme.ACCENT,
            lambda pi=page_idx: self._copy_page(pi),
            font_size=8,
            padding="2px 4px",
        )

        page_paste_clr = theme.ACCENT if self._has_clipboard_prefix("page_cfg") else theme.SUBTEXT
        _label_btn(
            header,
            "[P]",
            page_paste_clr,
            lambda pi=page_idx: self._paste_onto_page(pi),
            font_size=8,
            padding="2px 4px",
        )

        _label_btn(
            header,
            "✕",
            theme.RED,
            lambda: self._delete_page(page_idx),
            font_size=9,
        )

        card_layout.addLayout(header)
        _hline(card_layout)


        # ── Slots ─────────────────────────────────────────────────────────

        slots_layout = QVBoxLayout()
        slots_layout.setSpacing(3)

        slots = page.get(
            "slots",
            [],
        )

        for slot_idx, slot in enumerate(slots):
            slots_layout.addWidget(
                self._build_slot_row(
                    page_idx,
                    slot_idx,
                    slot,
                )
            )


        if not slots:
            none_lbl = QLabel(
                "No modules on this page yet."
            )

            none_lbl.setStyleSheet(
                f"color: {theme.SUBTEXT}; "
                f"background: transparent; "
                f"border: none;"
            )

            none_lbl.setFont(
                theme.qt_font(8)
            )

            slots_layout.addWidget(
                none_lbl
            )


        card_layout.addLayout(
            slots_layout
        )


        add_row = QHBoxLayout()
        add_row.setSpacing(6)

        _label_btn(
            add_row,
            "+ Add New Line",
            theme.ACCENT2,
            lambda pi=page_idx:
            self._prompt_add_new_line_row(pi),
            bg=theme.BG,
            font_size=9,
            padding="3px 10px",
        )

        line_paste_clr = theme.ACCENT if self._has_clipboard_prefix("line_cfg") else theme.SUBTEXT
        _label_btn(
            add_row,
            "+ Paste Line",
            line_paste_clr,
            lambda pi=page_idx:
            self._paste_line_to_page(pi),
            bg=theme.BG,
            font_size=9,
            padding="3px 10px",
        )

        add_row.addStretch(1)

        card_layout.addLayout(
            add_row
        )

        return card


    # ── Slot row ──────────────────────────────────────────────────────────

    def _build_slot_row(
            self,
            page_idx,
            slot_idx,
            slot,
    ):
        if "modules" not in slot:
            slot["modules"] = [
                {
                    "module": slot.get(
                        "module",
                        "",
                    ),
                    "text": slot.get(
                        "text",
                        "",
                    ),
                }
            ]


        row = QFrame()

        row.setStyleSheet(
            f"background-color: {theme.PANEL}; "
            f"border: none;"
        )

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(
            0,
            2,
            0,
            2,
        )


        up_lbl = QLabel("▲")
        up_lbl.setCursor(
            Qt.PointingHandCursor
        )

        up_lbl.setStyleSheet(
            f"color: {theme.SUBTEXT}; "
            f"background-color: {theme.PANEL}; "
            f"padding: 1px 3px; "
            f"border: none;"
        )

        up_lbl.setFont(
            theme.qt_font(10)
        )

        up_lbl.mousePressEvent = (
            lambda _e, pi=page_idx, si=slot_idx:
            self._move_slot(pi, si, -1)
        )

        row_layout.addWidget(up_lbl)


        down_lbl = QLabel("▼")
        down_lbl.setCursor(
            Qt.PointingHandCursor
        )

        down_lbl.setStyleSheet(
            f"color: {theme.SUBTEXT}; "
            f"background-color: {theme.PANEL}; "
            f"padding: 1px 3px; "
            f"border: none;"
        )

        down_lbl.setFont(
            theme.qt_font(10)
        )

        down_lbl.mousePressEvent = (
            lambda _e, pi=page_idx, si=slot_idx:
            self._move_slot(pi, si, 1)
        )

        row_layout.addWidget(down_lbl)


        capsule = QHBoxLayout()
        capsule.setSpacing(4)


        for m_idx, sub_slot in enumerate(
                slot["modules"]
        ):
            mod = MODULE_BY_ID.get(
                sub_slot.get(
                    "module",
                    "",
                )
            )

            label = (
                mod["label"]
                if mod
                else sub_slot.get(
                    "module",
                    "unknown",
                )
            )


            mod_block = QFrame()

            mod_block.setStyleSheet(
                f"background-color: {theme.BORDER}; "
                f"border: none;"
            )

            mod_block_layout = QHBoxLayout(
                mod_block
            )

            mod_block_layout.setContentsMargins(
                4,
                2,
                4,
                2,
            )


            mlbl = QLabel(label)

            mlbl.setStyleSheet(
                f"color: {theme.TEXT}; "
                f"background: transparent; "
                f"border: none;"
            )

            mlbl.setFont(
                theme.qt_font(9)
            )

            mod_block_layout.addWidget(mlbl)


            # ── Optional text field ──────────────────────────────────────

            if mod and mod.get("has_text"):
                module_id = str(
                    sub_slot.get(
                        "module",
                        "",
                    )
                )

                is_gpu_index = module_id.startswith(
                    (
                        "gpu_",
                        "vram_",
                    )
                )


                if (
                        is_gpu_index
                        and not str(
                    sub_slot.get(
                        "text",
                        "",
                    )
                ).strip()
                ):
                    sub_slot["text"] = "0"


                entry = QLineEdit(
                    sub_slot.get(
                        "text",
                        "",
                    )
                )

                entry.setFixedWidth(
                    58 if is_gpu_index else 90
                )

                entry.setFont(
                    theme.qt_font(9)
                )

                entry.setStyleSheet(
                    theme.line_edit_qss()
                )


                if is_gpu_index:
                    entry.setPlaceholderText(
                        "GPU #"
                    )

                    entry.setToolTip(
                        "GPU index: "
                        "0 = first GPU, "
                        "1 = second GPU, "
                        "2 = third GPU, etc."
                    )


                def _text_changed(
                        text,
                        pi=page_idx,
                        si=slot_idx,
                        mi=m_idx,
                ):
                    try:
                        self._cfg[
                            "pages"
                        ][pi][
                            "slots"
                        ][si][
                            "modules"
                        ][mi]["text"] = text

                        self._save()

                    except IndexError:
                        pass


                entry.textChanged.connect(
                    _text_changed
                )

                mod_block_layout.addWidget(
                    entry
                )


            if len(slot["modules"]) > 1:
                x_lbl = QLabel("✕")
                x_lbl.setCursor(
                    Qt.PointingHandCursor
                )

                x_lbl.setStyleSheet(
                    f"color: {theme.SUBTEXT}; "
                    f"background-color: {theme.BORDER}; "
                    f"padding: 1px 3px; "
                    f"border: none;"
                )

                x_lbl.setFont(
                    theme.qt_font(8)
                )

                x_lbl.mousePressEvent = (
                    lambda _e,
                           pi=page_idx,
                           si=slot_idx,
                           mi=m_idx:
                    self._remove_sub_module(
                        pi,
                        si,
                        mi,
                    )
                )

                mod_block_layout.addWidget(
                    x_lbl
                )


            capsule.addWidget(
                mod_block
            )


        capsule.addStretch(1)

        row_layout.addLayout(
            capsule,
            1,
        )


        _label_btn(
            row_layout,
            "+",
            theme.ACCENT2,
            lambda pi=page_idx,
                   si=slot_idx:
            self._prompt_append_module(
                pi,
                si,
            ),
            font_size=13,
            padding="1px 6px",
        )

        _label_btn(
            row_layout,
            "[C]",
            theme.ACCENT,
            lambda pi=page_idx,
                   si=slot_idx:
            self._copy_slot(
                pi,
                si,
            ),
            font_size=8,
            padding="2px 4px",
        )

        paste_clr = theme.ACCENT if self._has_clipboard_prefix("line_cfg") else theme.SUBTEXT
        _label_btn(
            row_layout,
            "[P]",
            paste_clr,
            lambda pi=page_idx,
                   si=slot_idx:
            self._paste_slot(
                pi,
                si,
            ),
            font_size=8,
            padding="2px 4px",
        )

        _label_btn(
            row_layout,
            "x",
            theme.RED,
            lambda pi=page_idx,
                   si=slot_idx:
            self._remove_slot(
                pi,
                si,
            ),
            font_size=13,
            padding="1px 6px",
        )

        return row


    # ── Import/Export All Pages ───────────────────────────────────────────

    def _export_all_pages(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export All Pages",
            "pages.json",
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            try:
                pages_data = self._cfg.get("pages", [])
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(pages_data, f, indent=4)
                self._show_toast("Pages exported successfully!")
            except Exception as e:
                self._show_toast(f"Export failed: {str(e)}", is_error=True)

    def _import_all_pages(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import All Pages",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    pages_data = json.load(f)
                if isinstance(pages_data, list):
                    self._cfg["pages"] = pages_data
                    self._sel_page = 0
                    self._save()
                    self._refresh_pages()
                    self._show_toast("Pages imported successfully!")
                else:
                    self._show_toast("Invalid format: expected a list of pages", is_error=True)
            except Exception as e:
                self._show_toast(f"Import failed: {str(e)}", is_error=True)


    # ── Page Mutators ──────────────────────────────────────────────────────

    def _add_page(self):
        self._cfg.setdefault(
            "pages",
            [],
        ).append(
            {
                "enabled": True,
                "duration": 6,
                "slots": [],
            }
        )

        self._sel_page = (
                len(self._cfg["pages"]) - 1
        )

        self._save()
        self._refresh_pages()


    def _delete_page(self, page_idx):
        pages = self._cfg.get(
            "pages",
            [],
        )

        if 0 <= page_idx < len(pages):
            pages.pop(page_idx)

            if self._sel_page >= len(pages):
                self._sel_page = max(
                    0,
                    len(pages) - 1,
                    )

            self._save()
            self._refresh_pages()


    def _move_page(self, page_idx, direction):
        pages = self._cfg.get("pages", [])
        new_idx = page_idx + direction

        if 0 <= new_idx < len(pages):
            pages[page_idx], pages[new_idx] = pages[new_idx], pages[page_idx]

            if self._sel_page == page_idx:
                self._sel_page = new_idx
            elif self._sel_page == new_idx:
                self._sel_page = page_idx

            self._save()
            self._refresh_pages()


    def _copy_page(self, page_idx):
        try:
            page_data = self._cfg["pages"][page_idx]
            self._copy_to_clipboard("page_cfg", page_data)
            self._show_toast(f"Page {page_idx + 1} copied to clipboard!")
            self._refresh_pages()
        except IndexError:
            pass


    def _paste_page(self):
        page_data = self._read_from_clipboard("page_cfg")
        if page_data:
            self._cfg.setdefault("pages", []).append(copy.deepcopy(page_data))
            self._sel_page = len(self._cfg["pages"]) - 1
            self._save()
            self._refresh_pages()
            self._show_toast("New page pasted from clipboard!")
        else:
            self._show_toast("No page data in clipboard!", is_error=True)


    def _paste_onto_page(self, page_idx):
        page_data = self._read_from_clipboard("page_cfg")
        if page_data:
            try:
                self._cfg["pages"][page_idx] = copy.deepcopy(page_data)
                self._save()
                self._refresh_pages()
                self._show_toast(f"Page {page_idx + 1} overwritten from clipboard!")
            except IndexError:
                pass
        else:
            self._show_toast("No page data in clipboard!", is_error=True)


    # ── Slot Mutators ──────────────────────────────────────────────────────

    def _copy_slot(
            self,
            page_idx,
            slot_idx,
    ):
        try:
            slots = self._cfg[
                "pages"
            ][page_idx][
                "slots"
            ]

            self._copy_to_clipboard("line_cfg", slots[slot_idx])
            self._show_toast(f"Line {slot_idx + 1} copied to clipboard!")
            self._refresh_pages()

        except IndexError:
            pass


    def _paste_slot(
            self,
            page_idx,
            slot_idx,
    ):
        slot_data = self._read_from_clipboard("line_cfg")
        if slot_data:
            try:
                slots = self._cfg[
                    "pages"
                ][page_idx][
                    "slots"
                ]

                slots[slot_idx] = copy.deepcopy(slot_data)

                self._save()
                self._refresh_pages()
                self._show_toast(f"Line {slot_idx + 1} overwritten from clipboard!")

            except IndexError:
                pass
        else:
            self._show_toast("No line data in clipboard!", is_error=True)


    def _paste_line_to_page(self, page_idx):
        slot_data = self._read_from_clipboard("line_cfg")
        if slot_data:
            try:
                pages = self._cfg.get("pages", [])
                pages[page_idx].setdefault("slots", []).append(copy.deepcopy(slot_data))
                self._save()
                self._refresh_pages()
                self._show_toast(f"Line appended to Page {page_idx + 1}!")
            except IndexError:
                pass
        else:
            self._show_toast("No line data in clipboard!", is_error=True)


    def _remove_slot(
            self,
            page_idx,
            slot_idx,
    ):
        try:
            self._cfg[
                "pages"
            ][page_idx][
                "slots"
            ].pop(slot_idx)

            self._save()
            self._refresh_pages()

        except IndexError:
            pass


    def _move_slot(
            self,
            page_idx,
            slot_idx,
            direction,
    ):
        try:
            slots = self._cfg[
                "pages"
            ][page_idx][
                "slots"
            ]

            new_idx = (
                    slot_idx + direction
            )

            if 0 <= new_idx < len(slots):
                slots[slot_idx], slots[new_idx] = (
                    slots[new_idx],
                    slots[slot_idx],
                )

                self._save()
                self._refresh_pages()

        except IndexError:
            pass


    def _save(self):
        self._save_cb()


    # ── Module picker menus ─────────────────────────────────────────────────

    def _build_category_menu(
            self,
            on_pick,
    ):
        menu = QMenu(self)

        menu.setStyleSheet(
            f"QMenu {{ "
            f"background-color: {theme.PANEL}; "
            f"color: {theme.TEXT}; "
            f"border: 1px solid {theme.BORDER}; "
            f"}} "
            f"QMenu::item:selected {{ "
            f"background-color: {theme.ACCENT}; "
            f"color: {theme.BG}; "
            f"}}"
        )


        for cat, mods in CATEGORIES.items():
            sub = menu.addMenu(cat)
            sub.setStyleSheet(
                menu.styleSheet()
            )

            for m in mods:
                action = sub.addAction(
                    m["label"]
                )

                action.triggered.connect(
                    lambda _checked=False,
                           m_id=m["id"]:
                    on_pick(m_id)
                )


        return menu


    def _prompt_append_module(
            self,
            page_idx,
            slot_idx,
    ):
        menu = self._build_category_menu(
            lambda m_id:
            self._append_module_to_slot(
                page_idx,
                slot_idx,
                m_id,
            )
        )

        menu.exec(
            QCursor.pos()
        )


    def _append_module_to_slot(
            self,
            page_idx,
            slot_idx,
            module_id,
    ):
        try:
            slots = self._cfg[
                "pages"
            ][page_idx][
                "slots"
            ]

            default_text = (
                "0"
                if (
                        module_id.startswith("gpu_")
                        or module_id.startswith("vram_")
                )
                else ""
            )

            slots[slot_idx][
                "modules"
            ].append(
                {
                    "module": module_id,
                    "text": default_text,
                }
            )

            self._save()
            self._refresh_pages()

        except IndexError:
            pass


    def _remove_sub_module(
            self,
            page_idx,
            slot_idx,
            module_idx,
    ):
        try:
            slots = self._cfg[
                "pages"
            ][page_idx][
                "slots"
            ]

            slots[slot_idx][
                "modules"
            ].pop(module_idx)

            self._save()
            self._refresh_pages()

        except IndexError:
            pass


    def _prompt_add_new_line_row(
            self,
            page_idx,
    ):
        menu = self._build_category_menu(
            lambda m_id:
            self._add_slot_for_page(
                page_idx,
                m_id,
            )
        )

        menu.exec(
            QCursor.pos()
        )


    def _add_slot_for_page(
            self,
            page_idx,
            module_id,
    ):
        try:
            pages = self._cfg.get(
                "pages",
                [],
            )

            default_text = (
                "0"
                if (
                        module_id.startswith("gpu_")
                        or module_id.startswith("vram_")
                )
                else ""
            )

            slot = {
                "modules": [
                    {
                        "module": module_id,
                        "text": default_text,
                    }
                ]
            }

            pages[page_idx].setdefault(
                "slots",
                [],
            ).append(slot)

            self._save()
            self._refresh_pages()

        except IndexError:
            pass


    # ── External refresh ─────────────────────────────────────────────────

    def refresh(self):
        self._refresh_pages()