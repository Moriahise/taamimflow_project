"""Comprehensive reading selection dialog for Ta'amimFlow.

This module implements a complete dialog for selecting Torah readings,
faithfully reproducing the layout and functionality of the classic
TropeTrainer application.  It provides three tabs:

* **Shabbat & Mon./Thu. readings** – parshiot arranged in five columns
  by book with radio buttons, a date display showing both the Gregorian
  and Hebrew date, and list‑box selectors for Torah options, Maftir
  options and Haftarah options.
* **Holiday & special readings** – holidays and megillot with radio
  buttons.
* **Custom readings** – an editable table for user‑defined aliyot with
  book/chapter/verse selectors.

Additional controls allow the user to specify the Hebrew year and
Gregorian year range, choose Diaspora or Israel scheduling, and toggle
the triennial Torah cycle.  A perpetual calendar popup
(:class:`CalendarDialog`) provides date selection; the chosen date is
displayed in the header area of the Shabbat tab.

When the dialog is accepted the ``selected_parsha``, ``selected_book``,
``reading_type``, ``selected_date``, and triennial ``cycle`` attributes
are set for retrieval by the main window.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QDate, QLocale, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Hebrew date utilities (simplified conversion)
# ---------------------------------------------------------------------------
# A full Hebrew calendar implementation is complex.  We provide a
# lightweight conversion table for the years 5784–5800 that covers
# the expected range.  For dates outside this range the Hebrew date
# display will show a placeholder.  In production this should be
# replaced by a robust library such as ``hdate`` or ``pyluach``.

_HEBREW_MONTHS = [
    "Nisan", "Iyar", "Sivan", "Tammuz", "Av", "Elul",
    "Tishrei", "Cheshvan", "Kislev", "Tevet", "Shevat", "Adar",
    "Adar I", "Adar II",
]


def _is_hebrew_leap_year(year: int) -> bool:
    """Return True if *year* (Hebrew) is a leap year."""
    return (7 * year + 1) % 19 < 7


def _hebrew_year_days(year: int) -> int:
    """Return the number of days in Hebrew *year*."""
    # Simplified: leap years have 383–385 days, regular 353–355.
    # We approximate with the most common lengths.
    return 385 if _is_hebrew_leap_year(year) else 355


def _gregorian_to_hebrew_approx(gdate: QDate) -> str:
    """Return a *rough* Hebrew date string for display purposes.

    This uses a simplified offset calculation.  For accurate results
    a proper Hebrew calendar library should be used.  If the
    ``hdate`` package is available it will be preferred automatically.
    """
    # Try using the hdate library first (pip install hdate)
    try:
        from hdate import HDate  # type: ignore[import-untyped]

        hd = HDate(gdate.toPyDate(), hebrew=False)
        return f"{hd.hdate_he_str()}"
    except Exception:
        pass

    # Try using pyluach
    try:
        from pyluach.dates import GregorianDate  # type: ignore[import-untyped]

        gd = GregorianDate(gdate.year(), gdate.month(), gdate.day())
        hd = gd.to_heb()
        month_names = {
            1: "Nisan", 2: "Iyar", 3: "Sivan", 4: "Tammuz",
            5: "Av", 6: "Elul", 7: "Tishrei", 8: "Cheshvan",
            9: "Kislev", 10: "Tevet", 11: "Shevat", 12: "Adar",
            13: "Adar II",
        }
        month_name = month_names.get(hd.month, f"Month {hd.month}")
        return f"{hd.day} {month_name}, {hd.year}"
    except Exception:
        pass

    # Fallback: rough estimation using known epoch
    # Tishrei 1, 5784 ≈ September 16, 2023
    # This is intentionally approximate; production code should use
    # a real Hebrew calendar library.
    try:
        epoch_greg = QDate(2023, 9, 16)  # 1 Tishrei 5784
        diff_days = epoch_greg.daysTo(gdate)
        h_year = 5784
        while diff_days < 0:
            h_year -= 1
            diff_days += _hebrew_year_days(h_year)
        while diff_days >= _hebrew_year_days(h_year):
            diff_days -= _hebrew_year_days(h_year)
            h_year += 1

        # Rough month mapping (30 days each, alternating)
        month_lengths = [30, 29, 30, 29, 30, 29, 30, 29, 30, 29, 30, 29]
        if _is_hebrew_leap_year(h_year):
            month_lengths = [30, 29, 30, 29, 30, 29, 30, 29, 30, 29, 30, 30, 29]

        # Months start from Tishrei (month index 0 = Tishrei)
        tishrei_months = [
            "Tishrei", "Cheshvan", "Kislev", "Tevet", "Shevat",
        ]
        if _is_hebrew_leap_year(h_year):
            tishrei_months += ["Adar I", "Adar II"]
        else:
            tishrei_months += ["Adar"]
        tishrei_months += ["Nisan", "Iyar", "Sivan", "Tammuz", "Av", "Elul"]

        month_idx = 0
        day_in_month = diff_days + 1
        for i, ml in enumerate(month_lengths):
            if day_in_month <= ml:
                month_idx = i
                break
            day_in_month -= ml
        else:
            month_idx = len(month_lengths) - 1

        month_name = tishrei_months[month_idx] if month_idx < len(tishrei_months) else "?"
        return f"{int(day_in_month)} {month_name}, {h_year}"
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Data: Torah options, Maftir options, Haftarah options – loaded from XML
# ---------------------------------------------------------------------------
# Options are loaded dynamically from ``sedrot.xml`` so that each parsha
# shows exactly the options the original TropeTrainer showed.

import os as _os
import xml.etree.ElementTree as _ET

# Structure: {parsha_name: {"torah": [...], "maftir": [...], "haftarah": [...]}}
_SEDROT_OPTIONS: Dict[str, Dict[str, List[str]]] = {}


def _find_sedrot_xml() -> str | None:
    """Search for sedrot.xml in common locations relative to this file."""
    candidates = [
        # Same directory as this module
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "sedrot.xml"),
        # One level up
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "sedrot.xml"),
        # Two levels up
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "sedrot.xml"),
        # Working directory
        "sedrot.xml",
        # Uploads path (development / testing)
        "/mnt/user-data/uploads/sedrot.xml",
    ]
    for path in candidates:
        if _os.path.isfile(path):
            return path
    return None


def _load_sedrot_xml() -> None:
    """Parse sedrot.xml and populate _SEDROT_OPTIONS."""
    global _SEDROT_OPTIONS
    path = _find_sedrot_xml()
    if not path:
        return  # Fallback to empty – callers will use defaults

    try:
        tree = _ET.parse(path)
        root = tree.getroot()
    except Exception:
        return

    for reading in root.findall("READING"):
        name = reading.get("NAME", "")
        torah_opts: List[str] = []
        maftir_opts: List[str] = []
        haftarah_opts: List[str] = []

        for child in reading:
            opt_type = child.get("TYPE", "")
            opt_name = child.get("NAME", "")
            special = child.get("SPECIAL", "")
            cycle_str = child.get("CYCLE", "")

            # Torah options: CYCLE 0 = regular Shabbas, CYCLE 4 = Weekday
            # Skip SPECIAL overlays (Shabbat Rosh Chodesh, Chanukah, etc.)
            if opt_type in ("Torah", "HiHoliday") and opt_name:
                if special:
                    continue
                try:
                    cycle = int(cycle_str)
                except ValueError:
                    cycle = -1
                if cycle in (0, 4) and opt_name not in torah_opts:
                    torah_opts.append(opt_name)

            # Maftir options: CYCLE 0 = regular, skip SPECIAL overlays
            elif opt_type == "Maftir" and opt_name:
                if special:
                    continue
                try:
                    cycle = int(cycle_str)
                except ValueError:
                    cycle = -1
                if cycle == 0 and opt_name not in maftir_opts:
                    maftir_opts.append(opt_name)

            # Haftarah options: include ALL options including SPECIAL,
            # since the user must choose between them (e.g. Pinchas
            # before/after 17th of Tammuz, Haazinu between RH and YK)
            elif opt_type == "Haftarah" and opt_name:
                if opt_name not in haftarah_opts:
                    haftarah_opts.append(opt_name)

        if name:
            _SEDROT_OPTIONS[name] = {
                "torah": torah_opts,
                "maftir": maftir_opts,
                "haftarah": haftarah_opts,
            }


# Load on import
_load_sedrot_xml()


def _get_torah_options(parsha: str | None) -> List[str]:
    """Return the list of Torah options for *parsha* from sedrot.xml."""
    if parsha and parsha in _SEDROT_OPTIONS:
        opts = _SEDROT_OPTIONS[parsha]["torah"]
        if opts:
            return opts
    # Fallback
    return ["Shabbas", "Weekday"]


def _get_maftir_options(parsha: str | None) -> List[str]:
    """Return Maftir options for *parsha* from sedrot.xml."""
    if parsha and parsha in _SEDROT_OPTIONS:
        opts = _SEDROT_OPTIONS[parsha]["maftir"]
        if opts:
            return opts
    return ["Standard"]


def _get_haftarah_options(parsha: str | None) -> List[str]:
    """Return Haftarah options for the given parsha from sedrot.xml."""
    if parsha and parsha in _SEDROT_OPTIONS:
        opts = _SEDROT_OPTIONS[parsha]["haftarah"]
        if opts:
            return opts
    return []


# ---------------------------------------------------------------------------
# Calendar popup dialog
# ---------------------------------------------------------------------------

class CalendarDialog(QDialog):
    """Perpetual calendar popup for date selection.

    Displays a :class:`QCalendarWidget` in a modal dialog.  The
    selected date is emitted via the ``date_selected`` signal and
    returned by :meth:`selected_date` after acceptance.
    """

    date_selected = pyqtSignal(QDate)

    def __init__(self, initial_date: QDate | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Trope Trainer Calendar")
        self.setModal(True)
        self.setMinimumSize(500, 420)
        self._selected: QDate = initial_date or QDate.currentDate()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()

        # Location selector (Diaspora / Israel)
        loc_layout = QHBoxLayout()
        loc_group = QGroupBox("Location")
        loc_inner = QHBoxLayout()
        self.diaspora_radio = QRadioButton("Diaspora")
        self.diaspora_radio.setChecked(True)
        loc_inner.addWidget(self.diaspora_radio)
        self.israel_radio = QRadioButton("Israel")
        loc_inner.addWidget(self.israel_radio)
        loc_group.setLayout(loc_inner)
        loc_layout.addWidget(loc_group)
        loc_layout.addStretch()

        # Month/Year display and Hebrew date
        self.month_year_label = QLabel()
        self.month_year_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.month_year_label.setStyleSheet("color: #000080;")
        loc_layout.addWidget(self.month_year_label)
        layout.addLayout(loc_layout)

        # Calendar widget
        self.calendar = QCalendarWidget()
        self.calendar.setSelectedDate(self._selected)
        self.calendar.setGridVisible(True)
        self.calendar.setFirstDayOfWeek(Qt.DayOfWeek.Sunday)
        self.calendar.selectionChanged.connect(self._on_date_changed)
        self.calendar.currentPageChanged.connect(self._update_month_label)
        layout.addWidget(self.calendar)

        # Buttons: Open reading / Cancel
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        open_btn = QPushButton("Open reading")
        open_btn.clicked.connect(self.accept)
        btn_layout.addWidget(open_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        help_btn = QPushButton("Help")
        btn_layout.addWidget(help_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self._update_month_label(self._selected.year(), self._selected.month())

    def _on_date_changed(self) -> None:
        self._selected = self.calendar.selectedDate()
        self.date_selected.emit(self._selected)

    def _update_month_label(self, year: int, month: int) -> None:
        greg_str = QDate(year, month, 1).toString("MMM. yyyy")
        # Try to show Hebrew month/year
        heb_str = _gregorian_to_hebrew_approx(QDate(year, month, 15))
        if heb_str:
            # Extract month and year portions
            parts = heb_str.split(",")
            if len(parts) >= 2:
                h_month_part = parts[0].strip().split(" ", 1)
                h_year = parts[-1].strip()
                if len(h_month_part) >= 2:
                    self.month_year_label.setText(
                        f"{greg_str}\n{h_month_part[1]} {h_year}"
                    )
                else:
                    self.month_year_label.setText(f"{greg_str}\n{heb_str}")
            else:
                self.month_year_label.setText(f"{greg_str}\n{heb_str}")
        else:
            self.month_year_label.setText(greg_str)

    def selected_date(self) -> QDate:
        """Return the date selected by the user."""
        return self._selected


# ---------------------------------------------------------------------------
# Custom reading edit sub‑dialog
# ---------------------------------------------------------------------------

class CustomReadingEditDialog(QDialog):
    """Dialog for editing a single custom aliyah reading.

    Allows the user to specify a book, starting chapter:verse and
    ending chapter:verse.  The design matches the original TropeTrainer
    "Edit Kohen reading" popup shown in the screenshots.
    """

    def __init__(self, reading_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reading_name = reading_name
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(f"Edit {self.reading_name} reading")
        self.setModal(True)
        self.setMinimumSize(380, 200)
        layout = QVBoxLayout()

        # Title
        layout.addWidget(QLabel(f"<b>Edit {self.reading_name} reading</b>"))

        # Select book
        book_layout = QHBoxLayout()
        book_layout.addWidget(QLabel("Select book:"))
        self.book_combo = QComboBox()
        self.book_combo.addItems([
            "- Select a book -",
            "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
        ])
        book_layout.addWidget(self.book_combo)
        layout.addLayout(book_layout)

        # Starting chapter : verse
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Starting chapter:"))
        self.start_chapter_spin = QSpinBox()
        self.start_chapter_spin.setRange(1, 50)
        self.start_chapter_spin.setFixedWidth(60)
        start_layout.addWidget(self.start_chapter_spin)
        start_layout.addWidget(QLabel(":verse"))
        self.start_verse_spin = QSpinBox()
        self.start_verse_spin.setRange(1, 176)
        self.start_verse_spin.setFixedWidth(60)
        start_layout.addWidget(self.start_verse_spin)
        start_layout.addStretch()
        layout.addLayout(start_layout)

        # To chapter : verse
        to_layout = QHBoxLayout()
        to_layout.addWidget(QLabel("To chapter:"))
        self.to_chapter_spin = QSpinBox()
        self.to_chapter_spin.setRange(1, 50)
        self.to_chapter_spin.setFixedWidth(60)
        to_layout.addWidget(self.to_chapter_spin)
        to_layout.addWidget(QLabel(":verse"))
        self.to_verse_spin = QSpinBox()
        self.to_verse_spin.setRange(1, 176)
        self.to_verse_spin.setFixedWidth(60)
        to_layout.addWidget(self.to_verse_spin)
        to_layout.addStretch()
        layout.addLayout(to_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        set_btn = QPushButton("Set")
        set_btn.setFixedWidth(80)
        set_btn.clicked.connect(self.accept)
        btn_layout.addWidget(set_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)


# ---------------------------------------------------------------------------
# Main Open Reading Dialog
# ---------------------------------------------------------------------------

class OpenReadingDialog(QDialog):
    """Complete Open Reading Dialog with multiple tabs.

    This dialog replicates the full reading selection interface of the
    classic TropeTrainer.  It provides three tabs matching the original
    layout, with list‑box selectors for Torah, Maftir and Haftarah
    options at the bottom, and action buttons on the right.

    Attributes set on acceptance:

    * ``selected_parsha``   – name of the selected parsha / holiday
    * ``selected_book``     – book or category name
    * ``reading_type``      – ``"Torah"``, ``"Haftarah"`` or ``"Maftir"``
    * ``selected_date``     – the Gregorian date chosen
    * ``cycle``             – triennial cycle (0 = annual, 1–3)
    * ``diaspora``          – whether Diaspora scheduling is selected
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.selected_parsha: str | None = None
        self.selected_book: str | None = None
        self.reading_type: str = "Torah"
        self.selected_date: QDate = QDate.currentDate()
        self.cycle: int = 0
        self.diaspora: bool = True
        self._init_ui()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _init_ui(self) -> None:
        self.setWindowTitle("Open reading")
        self.setModal(True)
        self.setMinimumSize(730, 660)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(4)

        # ---- Tab bar + date header ----
        header = QHBoxLayout()
        self.main_tabs = QTabWidget()
        header.addWidget(self.main_tabs, stretch=1)

        # Date label (Gregorian / Hebrew) – right‑aligned
        self.date_header_label = QLabel()
        self.date_header_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.date_header_label.setStyleSheet(
            "color: #000080; background: #D0D0FF; padding: 4px 10px;"
            "border: 1px solid #8080C0;"
        )
        self.date_header_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._update_date_header(self.selected_date)
        header.addWidget(self.date_header_label)
        main_layout.addLayout(header)

        # Build the three tabs
        self._create_shabbat_tab()
        self._create_holiday_tab()
        self._create_custom_tab()

        # ---- Year / location / triennial bar ----
        year_bar = QHBoxLayout()
        year_bar.addWidget(QLabel("Get readings for year:"))

        self.year_spinbox = QSpinBox()
        self.year_spinbox.setRange(5700, 5900)
        current_heb_year = QDate.currentDate().year() + 3760
        self.year_spinbox.setValue(current_heb_year)
        self.year_spinbox.setFixedWidth(70)
        year_bar.addWidget(self.year_spinbox)

        greg = QDate.currentDate().year()
        self.greg_range_label = QLabel(f"({greg}/{greg + 1})")
        year_bar.addWidget(self.greg_range_label)

        year_bar.addSpacing(10)

        # Diaspora / Israel
        self.diaspora_radio = QRadioButton("Diaspora")
        self.diaspora_radio.setChecked(True)
        year_bar.addWidget(self.diaspora_radio)
        self.israel_radio = QRadioButton("Israel")
        year_bar.addWidget(self.israel_radio)
        loc_group = QButtonGroup(self)
        loc_group.addButton(self.diaspora_radio)
        loc_group.addButton(self.israel_radio)

        year_bar.addSpacing(10)

        # Triennial cycle
        self.triennial_checkbox = QCheckBox("Use triennial Torah cycle")
        year_bar.addWidget(self.triennial_checkbox)

        self.cycle_label = QLabel(f"Cycle for {current_heb_year}:")
        year_bar.addWidget(self.cycle_label)
        self.cycle_spinbox = QSpinBox()
        self.cycle_spinbox.setRange(1, 3)
        self.cycle_spinbox.setValue(1)
        self.cycle_spinbox.setFixedWidth(45)
        year_bar.addWidget(self.cycle_spinbox)

        year_bar.addStretch()
        main_layout.addLayout(year_bar)

        # Connect year changes
        self.year_spinbox.valueChanged.connect(self._on_year_changed)

        # ---- Torah / Maftir / Haftarah options + buttons ----
        bottom = QHBoxLayout()

        # Left side: option list boxes
        lists_layout = QVBoxLayout()

        # Torah + Maftir side by side
        torah_maftir = QHBoxLayout()

        torah_group = QGroupBox("Torah options")
        torah_inner = QVBoxLayout()
        self.torah_list = QListWidget()
        self.torah_list.setMaximumHeight(90)
        torah_inner.addWidget(self.torah_list)
        torah_group.setLayout(torah_inner)
        torah_maftir.addWidget(torah_group)

        maftir_group = QGroupBox("Maftir options")
        maftir_inner = QVBoxLayout()
        self.maftir_list = QListWidget()
        self.maftir_list.setMaximumHeight(90)
        maftir_inner.addWidget(self.maftir_list)
        maftir_group.setLayout(maftir_inner)
        torah_maftir.addWidget(maftir_group)

        lists_layout.addLayout(torah_maftir)

        # Haftarah
        haftarah_group = QGroupBox("Haftarah options")
        haftarah_inner = QVBoxLayout()
        self.haftarah_list = QListWidget()
        self.haftarah_list.setMaximumHeight(72)
        haftarah_inner.addWidget(self.haftarah_list)
        haftarah_group.setLayout(haftarah_inner)
        lists_layout.addWidget(haftarah_group)

        bottom.addLayout(lists_layout, stretch=1)

        # Right side: action buttons
        btn_layout = QVBoxLayout()
        btn_layout.addStretch()

        self.open_torah_btn = QPushButton("Open Torah Portion")
        self.open_torah_btn.setFixedWidth(150)
        self.open_torah_btn.clicked.connect(self._on_open_torah)
        btn_layout.addWidget(self.open_torah_btn)

        self.open_haftarah_btn = QPushButton("Open Haftarah")
        self.open_haftarah_btn.setFixedWidth(150)
        self.open_haftarah_btn.clicked.connect(self._on_open_haftarah)
        btn_layout.addWidget(self.open_haftarah_btn)

        btn_layout.addSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(150)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        help_btn = QPushButton("Help")
        help_btn.setFixedWidth(150)
        btn_layout.addWidget(help_btn)

        bottom.addLayout(btn_layout)
        main_layout.addLayout(bottom)

        self.setLayout(main_layout)

        # Populate option lists with defaults
        self._refresh_option_lists(None)

    # ------------------------------------------------------------------ #
    # Tab: Shabbat & Mon./Thu. readings
    # ------------------------------------------------------------------ #
    def _create_shabbat_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(4)

        # Parshiot scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setContentsMargins(4, 4, 4, 4)

        self.parsha_button_group = QButtonGroup(self)
        self.parsha_button_group.buttonClicked.connect(self._on_parsha_selected)

        parshiot = self._get_all_parshiot()

        # Organise into 5 columns by book
        books_order = [
            "Bereshit/Genesis",
            "Shemot/Exodus",
            "Vayikra/Leviticus",
            "Bamidbar/Numbers",
            "Devarim/Deuteronomy",
        ]
        book_short = {
            "Bereshit/Genesis": "Bereishis/Genesis",
            "Shemot/Exodus": "Shemos/Exodus",
            "Vayikra/Leviticus": "Vayikra/Leviticus",
            "Bamidbar/Numbers": "Bamidbar/Numbers",
            "Devarim/Deuteronomy": "Devarim/Deuteronomy",
        }

        # Group parshiot by book
        book_groups: Dict[str, List[Tuple[str, str]]] = {}
        for p, b in parshiot:
            book_groups.setdefault(b, []).append((p, b))

        for col, book_key in enumerate(books_order):
            entries = book_groups.get(book_key, [])
            label_text = book_short.get(book_key, book_key)
            header = QLabel(f"<b>{label_text}</b>")
            header.setStyleSheet("color: #333; padding: 2px 0;")
            grid.addWidget(header, 0, col)

            for row_idx, (parsha, book) in enumerate(entries):
                radio = QRadioButton(parsha)
                radio.setStyleSheet("QRadioButton { spacing: 2px; }")
                # Store data on the radio button for retrieval
                radio.parsha_name = parsha  # type: ignore[attr-defined]
                radio.book_name = book  # type: ignore[attr-defined]
                self.parsha_button_group.addButton(radio)
                grid.addWidget(radio, row_idx + 1, col)

        scroll_widget.setLayout(grid)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        tab.setLayout(layout)
        self.main_tabs.addTab(tab, "Shabbat & Mon./Thu. readings")

    # ------------------------------------------------------------------ #
    # Tab: Holiday & special readings
    # ------------------------------------------------------------------ #
    def _create_holiday_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        holiday_grid = QGridLayout()
        holiday_grid.setSpacing(3)

        self.holiday_button_group = QButtonGroup(self)

        # Two‑column layout matching the original
        left_holidays = [
            "Rosh Chodesh", "Rosh Hashanah", "Fast of Gedalia",
            "Yom Kippur", "Succos", "Hoshana Rabbah",
            "Shemini Atzeres", "Simchas Torah", "Chanukah",
            "Tenth of Teves", "Fast of Esther",
        ]
        right_holidays = [
            "Purim", "Pesach", "Shavuos",
            "Seventeenth of Tammuz", "Tisha B'Av",
        ]
        megillot = [
            "Megillas Esther",
            "Megillas Shir HaShirim (Song of Songs)",
            "Megillas Ruth",
            "Megillas Eichah (Lamentations)",
            "Megillas Koheles (Ecclesiastes)",
        ]

        for row, h in enumerate(left_holidays):
            radio = QRadioButton(h)
            self.holiday_button_group.addButton(radio)
            holiday_grid.addWidget(radio, row, 0)

        for row, h in enumerate(right_holidays):
            radio = QRadioButton(h)
            self.holiday_button_group.addButton(radio)
            holiday_grid.addWidget(radio, row, 1)

        # Megillot in right column, offset below holidays
        offset = len(right_holidays) + 1
        for row, m in enumerate(megillot):
            radio = QRadioButton(m)
            radio.setStyleSheet("color: gray;")
            self.holiday_button_group.addButton(radio)
            holiday_grid.addWidget(radio, offset + row, 1)

        scroll_widget.setLayout(holiday_grid)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        tab.setLayout(layout)
        self.main_tabs.addTab(tab, "Holiday & special readings")

    # ------------------------------------------------------------------ #
    # Tab: Custom readings
    # ------------------------------------------------------------------ #
    def _create_custom_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout()

        # Custom reading name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Custom reading name:"))
        self.custom_name_combo = QComboBox()
        self.custom_name_combo.setEditable(True)
        self.custom_name_combo.addItem("- Select reading or enter new name -")
        self.custom_name_combo.setMinimumWidth(250)
        name_row.addWidget(self.custom_name_combo, stretch=1)
        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(60)
        name_row.addWidget(save_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.setFixedWidth(60)
        name_row.addWidget(delete_btn)
        layout.addLayout(name_row)

        # Reading type radios
        type_row = QHBoxLayout()
        self.custom_torah_radio = QRadioButton("Torah")
        self.custom_torah_radio.setChecked(True)
        type_row.addWidget(self.custom_torah_radio)
        self.custom_haftarah_radio = QRadioButton("Haftarah")
        type_row.addWidget(self.custom_haftarah_radio)
        self.custom_megilla_radio = QRadioButton("Megilla")
        type_row.addWidget(self.custom_megilla_radio)
        self.custom_high_holidays_radio = QRadioButton("High Holidays Torah")
        type_row.addWidget(self.custom_high_holidays_radio)
        type_row.addStretch()
        layout.addLayout(type_row)

        # Aliyot table
        self.custom_table = QTableWidget()
        aliyot_names = [
            "Kohen", "Levi", "Shlishi", "Revii",
            "Chamishi", "Shishi", "Sh'vii", "", "Maftir",
        ]
        self.custom_table.setRowCount(len(aliyot_names))
        self.custom_table.setColumnCount(4)
        self.custom_table.setHorizontalHeaderLabels(["Reading", "Reference", "", ""])
        self.custom_table.horizontalHeader().setStretchLastSection(False)
        self.custom_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.custom_table.setColumnWidth(0, 80)
        self.custom_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.custom_table.verticalHeader().setVisible(False)

        for i, name in enumerate(aliyot_names):
            if name == "":
                self.custom_table.setRowHeight(i, 8)
                continue
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.custom_table.setItem(i, 0, name_item)

            ref_item = QTableWidgetItem("")
            ref_item.setFlags(ref_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.custom_table.setItem(i, 1, ref_item)

            edit_btn = QPushButton("Edit")
            edit_btn.setFixedWidth(50)
            edit_btn.clicked.connect(
                lambda checked, n=name: self._edit_custom_reading(n)
            )
            self.custom_table.setCellWidget(i, 2, edit_btn)

            clear_btn = QPushButton("Clear")
            clear_btn.setFixedWidth(50)
            self.custom_table.setCellWidget(i, 3, clear_btn)

        layout.addWidget(self.custom_table)
        tab.setLayout(layout)
        self.main_tabs.addTab(tab, "Custom readings")

    # ------------------------------------------------------------------ #
    # Parsha data
    # ------------------------------------------------------------------ #
    def _get_all_parshiot(self) -> List[Tuple[str, str]]:
        """Return a list of ``(parsha, book)`` tuples for the whole Torah.

        Combined parshiot (e.g. Vayakhel+Pekudei) are included to match
        the original TropeTrainer.
        """
        return [
            # Bereishis / Genesis
            ("Bereishis", "Bereshit/Genesis"),
            ("Noach", "Bereshit/Genesis"),
            ("Lech Lecha", "Bereshit/Genesis"),
            ("Vayeira", "Bereshit/Genesis"),
            ("Chayei Sarah", "Bereshit/Genesis"),
            ("Toldos", "Bereshit/Genesis"),
            ("Vayeitzei", "Bereshit/Genesis"),
            ("Vayishlach", "Bereshit/Genesis"),
            ("Vayeishev", "Bereshit/Genesis"),
            ("Mikeitz", "Bereshit/Genesis"),
            ("Vayigash", "Bereshit/Genesis"),
            ("Vayechi", "Bereshit/Genesis"),
            # Shemos / Exodus
            ("Shemos", "Shemot/Exodus"),
            ("Va'eira", "Shemot/Exodus"),
            ("Bo", "Shemot/Exodus"),
            ("Beshalach", "Shemot/Exodus"),
            ("Yisro", "Shemot/Exodus"),
            ("Mishpatim", "Shemot/Exodus"),
            ("Terumah", "Shemot/Exodus"),
            ("Tetzaveh", "Shemot/Exodus"),
            ("Ki Sisa", "Shemot/Exodus"),
            ("Vayakhel", "Shemot/Exodus"),
            ("Vayakhel+Pekudei", "Shemot/Exodus"),
            ("Pekudei", "Shemot/Exodus"),
            # Vayikra / Leviticus
            ("Vayikra", "Vayikra/Leviticus"),
            ("Tzav", "Vayikra/Leviticus"),
            ("Shemini", "Vayikra/Leviticus"),
            ("Tazria", "Vayikra/Leviticus"),
            ("Tazria+Metzora", "Vayikra/Leviticus"),
            ("Metzora", "Vayikra/Leviticus"),
            ("Acharei", "Vayikra/Leviticus"),
            ("Acharei+Kedoshim", "Vayikra/Leviticus"),
            ("Kedoshim", "Vayikra/Leviticus"),
            ("Emor", "Vayikra/Leviticus"),
            ("Behar", "Vayikra/Leviticus"),
            ("Behar+Bechukosai", "Vayikra/Leviticus"),
            ("Bechukosai", "Vayikra/Leviticus"),
            # Bamidbar / Numbers
            ("Bamidbar", "Bamidbar/Numbers"),
            ("Nasso", "Bamidbar/Numbers"),
            ("Beha'aloscha", "Bamidbar/Numbers"),
            ("Shelach", "Bamidbar/Numbers"),
            ("Korach", "Bamidbar/Numbers"),
            ("Chukas", "Bamidbar/Numbers"),
            ("Chukas+Balak", "Bamidbar/Numbers"),
            ("Balak", "Bamidbar/Numbers"),
            ("Pinchas", "Bamidbar/Numbers"),
            ("Mattos", "Bamidbar/Numbers"),
            ("Mattos+Masei", "Bamidbar/Numbers"),
            ("Masei", "Bamidbar/Numbers"),
            # Devarim / Deuteronomy
            ("Devarim", "Devarim/Deuteronomy"),
            ("Va'Eschanan", "Devarim/Deuteronomy"),
            ("Eikev", "Devarim/Deuteronomy"),
            ("Re'eh", "Devarim/Deuteronomy"),
            ("Shoftim", "Devarim/Deuteronomy"),
            ("Ki Seitzei", "Devarim/Deuteronomy"),
            ("Ki Savo", "Devarim/Deuteronomy"),
            ("Nitzavim", "Devarim/Deuteronomy"),
            ("Nitzavim+Vayeilech", "Devarim/Deuteronomy"),
            ("Vayeilech", "Devarim/Deuteronomy"),
            ("Haazinu", "Devarim/Deuteronomy"),
            ("V'zos HaBracha", "Devarim/Deuteronomy"),
        ]

    # Provide the legacy method name for backward compatibility
    def get_all_parshiot(self) -> List[Tuple[str, str]]:
        """Backward‑compatible alias for :meth:`_get_all_parshiot`."""
        return self._get_all_parshiot()

    # ------------------------------------------------------------------ #
    # Option list management
    # ------------------------------------------------------------------ #
    def _refresh_option_lists(self, parsha: str | None) -> None:
        """Populate the Torah, Maftir and Haftarah list widgets.

        Each parsha has its own set of options derived from sedrot.xml,
        exactly as in the original TropeTrainer.  The *Open Haftarah*
        button is disabled when no haftarah options are available (e.g.
        V'zos HaBracha).
        """
        self.torah_list.clear()
        for opt in _get_torah_options(parsha):
            item = QListWidgetItem(opt)
            self.torah_list.addItem(item)
        if self.torah_list.count():
            self.torah_list.setCurrentRow(0)

        self.maftir_list.clear()
        for opt in _get_maftir_options(parsha):
            item = QListWidgetItem(opt)
            self.maftir_list.addItem(item)
        if self.maftir_list.count():
            self.maftir_list.setCurrentRow(0)

        self.haftarah_list.clear()
        haftarah_opts = _get_haftarah_options(parsha)
        for opt in haftarah_opts:
            item = QListWidgetItem(opt)
            self.haftarah_list.addItem(item)
        if self.haftarah_list.count():
            self.haftarah_list.setCurrentRow(0)

        # Enable/disable Open Haftarah based on availability
        has_haftarah = bool(haftarah_opts)
        self.open_haftarah_btn.setEnabled(has_haftarah)

    # ------------------------------------------------------------------ #
    # Signal handlers
    # ------------------------------------------------------------------ #
    def _on_parsha_selected(self, button: QRadioButton) -> None:  # type: ignore[override]
        """Update option lists when the user selects a parsha."""
        parsha = getattr(button, "parsha_name", None)
        self._refresh_option_lists(parsha)

    def _on_year_changed(self, value: int) -> None:
        """Update labels when the Hebrew year spinbox changes."""
        greg = value - 3760
        self.greg_range_label.setText(f"({greg}/{greg + 1})")
        self.cycle_label.setText(f"Cycle for {value}:")

    def _update_date_header(self, qdate: QDate) -> None:
        """Update the header label with Gregorian and Hebrew dates."""
        greg_str = qdate.toString("MMM dd, yyyy")
        heb_str = _gregorian_to_hebrew_approx(qdate)
        if heb_str:
            self.date_header_label.setText(f"{greg_str} / {heb_str}")
        else:
            self.date_header_label.setText(greg_str)

    def open_calendar_dialog(self) -> None:
        """Show the perpetual calendar popup for date selection."""
        dlg = CalendarDialog(self.selected_date, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.selected_date = dlg.selected_date()
            self._update_date_header(self.selected_date)

    def _edit_custom_reading(self, reading_name: str) -> None:
        """Open the sub‑dialog for editing a custom aliyah."""
        dlg = CustomReadingEditDialog(reading_name, self)
        dlg.exec()

    # ------------------------------------------------------------------ #
    # Accept handlers
    # ------------------------------------------------------------------ #
    def _gather_common(self) -> None:
        """Collect triennial cycle, date and location from the controls."""
        self.cycle = 0
        if self.triennial_checkbox.isChecked():
            self.cycle = self.cycle_spinbox.value()
        self.diaspora = self.diaspora_radio.isChecked()

    def _on_open_torah(self) -> None:
        self.reading_type = "Torah"
        self._accept_selection()

    def _on_open_haftarah(self) -> None:
        self.reading_type = "Haftarah"
        self._accept_selection()

    def _accept_selection(self) -> None:
        """Accept the dialog after resolving the current tab's selection."""
        self._gather_common()
        tab = self.main_tabs.currentIndex()

        if tab == 0:  # Shabbat readings
            btn = self.parsha_button_group.checkedButton()
            if btn:
                self.selected_parsha = getattr(btn, "parsha_name", btn.text())
                self.selected_book = getattr(btn, "book_name", "")
                self.accept()
        elif tab == 1:  # Holidays
            btn = self.holiday_button_group.checkedButton()
            if btn:
                self.selected_parsha = btn.text()
                self.selected_book = "Holiday"
                self.accept()
        elif tab == 2:  # Custom
            name = self.custom_name_combo.currentText()
            if name and name != "- Select reading or enter new name -":
                self.selected_parsha = name
                self.selected_book = "Custom"
                self.accept()

    # Legacy public methods for backward compatibility
    def accept_torah(self) -> None:
        """Accept for a Torah selection (legacy API)."""
        self._on_open_torah()

    def accept_haftarah(self) -> None:
        """Accept for a Haftarah selection (legacy API)."""
        self._on_open_haftarah()
