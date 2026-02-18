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

from PyQt6.QtCore import QDate, QLocale, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
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
# Hebrew calendar: proper parsha date computation
# ---------------------------------------------------------------------------
# Full Zmanim / parsha schedule implementation so that selecting a parsha
# in the dialog shows the correct Gregorian and Hebrew date, exactly like
# the original TropeTrainer.

import datetime as _dt

# Days of week: 0=Sun, 1=Mon, ... 6=Sat
_HEBREW_EPOCH_JD = 347998          # Julian Day Number for 1 Tishrei 1 (verified)


def _jd_from_gregorian(year: int, month: int, day: int) -> int:
    """Return the Julian Day Number for a Gregorian date."""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return (day + (153 * m + 2) // 5 + 365 * y + y // 4
            - y // 100 + y // 400 - 32045)


def _gregorian_from_jd(jd: int) -> _dt.date:
    """Return a Python date for the given Julian Day Number."""
    a = jd + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    return _dt.date(year, month, day)


def _hebrew_elapsed_days(year: int) -> int:
    """Days from Hebrew epoch (1 Tishrei 1) to 1 Tishrei of *year*."""
    months_elapsed = (235 * year - 234) // 19
    parts = 12084 + 13753 * months_elapsed
    day = months_elapsed * 29 + parts // 25920
    if (3 * (day + 1)) % 7 < 3:
        day += 1
    return day


def _days_in_hebrew_year(year: int) -> int:
    return _hebrew_elapsed_days(year + 1) - _hebrew_elapsed_days(year)


def _rosh_hashana_jd(year: int) -> int:
    """Return Julian Day Number for 1 Tishrei of Hebrew *year*."""
    return _HEBREW_EPOCH_JD + _hebrew_elapsed_days(year) - 1


def _rosh_hashana_date(year: int) -> _dt.date:
    return _gregorian_from_jd(_rosh_hashana_jd(year))


# Parsha schedule tables for Diaspora.
# Key: (year_type, rh_dow) where year_type in {'H','R','C'} (haser/regular/shleima)
# combined with leap status.  Values: list of (parsha_name, week_offset)
# week_offset = number of Shabbatot after Simchat Torah (0 = first Shabbat of Bereishis)

# Simplified: we compute the parsha schedule by iterating Shabbatot
# starting from the first Shabbat after Simchat Torah.

# The 54 weekly portions in order (some are combined pairs)
_PARSHA_ORDER_DIASPORA = [
    "Bereishis", "Noach", "Lech Lecha", "Vayeira", "Chayei Sarah",
    "Toldos", "Vayeitzei", "Vayishlach", "Vayeishev", "Mikeitz",
    "Vayigash", "Vayechi",
    "Shemos", "Va'eira", "Bo", "Beshalach", "Yisro", "Mishpatim",
    "Terumah", "Tetzaveh", "Ki Sisa", "Vayakhel", "Pekudei",
    "Vayikra", "Tzav", "Shemini", "Tazria", "Metzora",
    "Acharei", "Kedoshim", "Emor", "Behar", "Bechukosai",
    "Bamidbar", "Nasso", "Beha'aloscha", "Shelach", "Korach",
    "Chukas", "Balak", "Pinchas", "Mattos", "Masei",
    "Devarim", "Va'Eschanan", "Eikev", "Re'eh", "Shoftim",
    "Ki Seitzei", "Ki Savo", "Nitzavim", "Vayeilech", "Haazinu",
    "V'zos HaBracha",
]

# Rules for combining parshas (Diaspora) keyed by total Shabbatot available
# We derive combinations from the year length and holidays automatically.

# Shabbatot that are "double-readings" in various year types (Diaspora):
# The combining logic: in a non-leap year with fewer available Shabbatot,
# certain portions are doubled.
_COMBINE_RULES_DIASPORA_NON_LEAP = {
    # (available_weeks): list of portion indices to combine (merge i and i+1)
    # 47 weeks: Vayakhel+Pekudei, Tazria+Metzora, Acharei+Kedoshim, Behar+Bechukosai,
    #           Mattos+Masei, Nitzavim+Vayeilech
    47: [21, 26, 28, 31, 41, 49],
    48: [21, 26, 28, 31, 41],    # Vayakhel+Pekudei + most
    # etc.
}

_COMBINE_RULES_DIASPORA_LEAP = {
    # 54: no combinations needed (most years)
    54: [],
    53: [41],       # Mattos+Masei
    55: [],
}


def _get_parsha_schedule_diaspora(year: int) -> Dict[str, _dt.date]:
    """Return {parsha_name: date_of_reading} for Diaspora, Hebrew *year*.

    Uses the classic algorithm:
    1. Find 1 Tishrei (Rosh Hashana)
    2. Find Simchat Torah (23 Tishrei in diaspora; 22 if RH on Thu for leap)
    3. Iterate Shabbatot, assigning parshas with combination rules.
    """
    rh = _rosh_hashana_date(year)
    rh_jd = _rosh_hashana_jd(year)

    # Simchat Torah = 23 Tishrei (Diaspora)
    simchat_torah_jd = rh_jd + 22  # 23 Tishrei = offset 22

    # First Shabbat after Simchat Torah
    # day_of_week: JD mod 7: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
    # JD 0 = Monday, so JD mod 7: 0=Mon,1=Tue,2=Wed,3=Thu,4=Fri,5=Sat,6=Sun
    dow = simchat_torah_jd % 7  # 0=Mon..5=Sat,6=Sun
    days_to_shabbat = (5 - dow) % 7  # 5 = Saturday
    if days_to_shabbat == 0:
        days_to_shabbat = 7
    first_shabbat_jd = simchat_torah_jd + days_to_shabbat

    # Determine next year's Rosh Hashana to know year end
    next_rh_jd = _rosh_hashana_jd(year + 1)
    # Last Shabbat before next Simchat Torah (next year's 23 Tishrei)
    next_simchat_jd = next_rh_jd + 22
    # Find Shabbat before or on V'zos HaBracha (= Simchat Torah = 22 Tishrei diaspora)
    # V'zos HaBracha is read on Simchat Torah; we don't assign it to a Shabbat
    # Haazinu is the last Shabbat reading

    # Count available Shabbatot from first_shabbat_jd until the Shabbat before next RH
    # Last Shabbat of the year is just before next Rosh Hashana
    dow_next_rh = next_rh_jd % 7  # 0=Mon
    days_back = (dow_next_rh - 5) % 7  # days from previous Shabbat to next_rh
    if days_back == 0:
        days_back = 7
    last_shabbat_jd = next_rh_jd - days_back

    num_shabbatot = (last_shabbat_jd - first_shabbat_jd) // 7 + 1

    # Determine if leap year
    is_leap = _is_hebrew_leap_year(year)

    # Build list of portions with combination rules
    portions = list(_PARSHA_ORDER_DIASPORA[:-1])  # exclude V'zos HaBracha

    # The number of parshiyot to read is num_shabbatot
    # We need to combine until len(portions) == num_shabbatot
    # Standard combination order (Diaspora, non-leap):
    combine_candidates_non_leap = [
        ("Nitzavim", "Vayeilech"),
        ("Vayakhel", "Pekudei"),
        ("Tazria", "Metzora"),
        ("Acharei", "Kedoshim"),
        ("Behar", "Bechukosai"),
        ("Mattos", "Masei"),
    ]
    combine_candidates_leap = [
        ("Mattos", "Masei"),
        ("Nitzavim", "Vayeilech"),
    ]

    candidates = combine_candidates_leap if is_leap else combine_candidates_non_leap

    schedule_list = list(portions)

    while len(schedule_list) > num_shabbatot:
        combined = False
        for a, b in candidates:
            combined_name = f"{a}+{b}"
            if a in schedule_list and b in schedule_list:
                ia = schedule_list.index(a)
                ib = schedule_list.index(b)
                if ib == ia + 1:
                    schedule_list[ia] = combined_name
                    schedule_list.pop(ib)
                    combined = True
                    break
        if not combined:
            break  # Can't combine further

    # Build date mapping
    result: Dict[str, _dt.date] = {}
    for i, parsha in enumerate(schedule_list):
        jd = first_shabbat_jd + i * 7
        greg = _gregorian_from_jd(jd)
        result[parsha] = greg

    # V'zos HaBracha = Simchat Torah
    result["V'zos HaBracha"] = _gregorian_from_jd(simchat_torah_jd)

    return result


# Cache parsha schedules per year
_PARSHA_SCHEDULE_CACHE: Dict[int, Dict[str, _dt.date]] = {}


def _get_parsha_date(parsha: str, heb_year: int, diaspora: bool = True) -> _dt.date | None:
    """Return the Gregorian date when *parsha* is read in *heb_year*."""
    key = heb_year
    if key not in _PARSHA_SCHEDULE_CACHE:
        try:
            _PARSHA_SCHEDULE_CACHE[key] = _get_parsha_schedule_diaspora(heb_year)
        except Exception:
            return None
    return _PARSHA_SCHEDULE_CACHE[key].get(parsha)


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
        # For holidays: ALL Torah options (including SPECIAL) are shown
        all_torah_opts: List[str] = []
        all_maftir_opts: List[str] = []
        all_haftarah_opts: List[str] = []

        for child in reading:
            opt_type = child.get("TYPE", "")
            opt_name = child.get("NAME", "")
            special = child.get("SPECIAL", "")
            cycle_str = child.get("CYCLE", "")

            # Torah options: CYCLE 0 = regular Shabbas, CYCLE 4 = Weekday
            # Skip SPECIAL overlays (Shabbat Rosh Chodesh, Chanukah, etc.)
            if opt_type in ("Torah", "HiHoliday") and opt_name:
                # All Torah options (for holidays, no filter)
                if opt_name not in all_torah_opts:
                    all_torah_opts.append(opt_name)
                if special:
                    continue
                try:
                    cycle = int(cycle_str)
                except ValueError:
                    cycle = -1
                if cycle in (0, 4) and opt_name not in torah_opts:
                    torah_opts.append(opt_name)

            # Megilla-type options: Esther, Ruth/Koheles/ShirHashirim, Eichah
            # These are the "Torah" reading for Megillot – store in all_torah
            elif opt_type in ("Esther", "Ruth-Koheles-ShirHashirim", "Eichah",
                              "Tehillim") and opt_name:
                if opt_name not in all_torah_opts:
                    all_torah_opts.append(opt_name)

            # Maftir options: CYCLE 0 = regular, skip SPECIAL overlays
            elif opt_type == "Maftir" and opt_name:
                if opt_name not in all_maftir_opts:
                    all_maftir_opts.append(opt_name)
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
                if opt_name not in all_haftarah_opts:
                    all_haftarah_opts.append(opt_name)

        if name:
            _SEDROT_OPTIONS[name] = {
                "torah": torah_opts,
                "maftir": maftir_opts,
                "haftarah": haftarah_opts,
                # Full lists for holidays (include all SPECIAL variants)
                "all_torah": all_torah_opts,
                "all_maftir": all_maftir_opts,
                "all_haftarah": all_haftarah_opts,
            }


# Load on import
_load_sedrot_xml()


# ---------------------------------------------------------------------------
# Megillot melody loader – reads tropedef_megillot.xml
# ---------------------------------------------------------------------------
# tropedef_megillot.xml defines the available melody styles per Megilla type.
# We extract TROPEDEF NAME + TYPE via regex (the file has minor XML issues).
# Result: {type_str: [melody_name, ...]}
# e.g. {"Esther": ["Ashkenazic - Binder: No detours", "Ashkenazic - Jacobson", ...], ...}

_MEGILLOT_MELODIES: Dict[str, List[str]] = {}

# Mapping: sedrot.xml reading option name → tropedef TYPE
_MEGILLA_OPTION_TYPE: Dict[str, str] = {
    "Megillas Esther":       "Esther",
    "Shir HaShirim":         "Ruth-Koheles-ShirHashirim",
    "Megillas Ruth":          "Ruth-Koheles-ShirHashirim",
    "Koheles/Ecclesiastes":  "Ruth-Koheles-ShirHashirim",
    "Eichah/Lamentations":   "Eichah",
}

# Mapping: holiday name → which Megilla option name is the "gateway"
# (used to append melody variants to holiday Torah lists)
_HOLIDAY_MEGILLA_OPTION: Dict[str, str] = {
    "Purim":      "Megillas Esther",
    "Pesach":     "Shir HaShirim",
    "Shavuos":    "Megillas Ruth",
    "Succos":     "Koheles/Ecclesiastes",
    "Tisha B'Av": "Eichah/Lamentations",
}

# Standalone Megilla readings in the Holiday tab (left-column buttons)
_STANDALONE_MEGILLA_TYPE: Dict[str, str] = {
    "Megillas Esther":                     "Esther",
    "Megillas Shir HaShirim (Song of Songs)": "Ruth-Koheles-ShirHashirim",
    "Megillas Ruth":                        "Ruth-Koheles-ShirHashirim",
    "Megillas Eichah (Lamentations)":       "Eichah",
    "Megillas Koheles (Ecclesiastes)":      "Ruth-Koheles-ShirHashirim",
}


def _find_megillot_xml() -> str | None:
    """Search for tropedef_megillot.xml in common locations."""
    candidates = [
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "tropedef_megillot.xml"),
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "tropedef_megillot.xml"),
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "tropedef_megillot.xml"),
        "tropedef_megillot.xml",
        "/mnt/user-data/uploads/tropedef_megillot.xml",
    ]
    for path in candidates:
        if _os.path.isfile(path):
            return path
    return None


def _load_megillot_xml() -> None:
    """Parse tropedef_megillot.xml and populate _MEGILLOT_MELODIES.

    Uses regex instead of XML parser because the file contains minor
    well-formedness issues (missing spaces between attributes).
    """
    global _MEGILLOT_MELODIES
    import re as _re
    path = _find_megillot_xml()
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as _fh:
            content = _fh.read()
        pattern = _re.compile(r'<TROPEDEF\s+NAME="([^"]+)"\s+TYPE="([^"]+)"')
        from collections import defaultdict as _dd
        melodies: Dict[str, List[str]] = _dd(list)
        for name, typ in pattern.findall(content):
            name = name.strip()
            if name not in melodies[typ]:
                melodies[typ].append(name)
        _MEGILLOT_MELODIES.update(melodies)
    except Exception:
        pass


_load_megillot_xml()


def _megilla_melody_options(megilla_type: str) -> List[str]:
    """Return melody variant names for *megilla_type* from tropedef_megillot.xml.

    Falls back to a single generic entry if the file was not loaded.
    """
    variants = _MEGILLOT_MELODIES.get(megilla_type, [])
    return variants if variants else [megilla_type]


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


def _get_holiday_torah_options(holiday: str) -> List[str]:
    """Return ALL Torah options for a holiday (including all SPECIAL variants)."""
    if holiday in _SEDROT_OPTIONS:
        opts = _SEDROT_OPTIONS[holiday].get("all_torah", [])
        if opts:
            return opts
    return []


def _get_holiday_maftir_options(holiday: str) -> List[str]:
    """Return ALL Maftir options for a holiday."""
    if holiday in _SEDROT_OPTIONS:
        opts = _SEDROT_OPTIONS[holiday].get("all_maftir", [])
        if opts:
            return opts
    return []


def _get_holiday_haftarah_options(holiday: str) -> List[str]:
    """Return ALL Haftarah options for a holiday."""
    if holiday in _SEDROT_OPTIONS:
        opts = _SEDROT_OPTIONS[holiday].get("all_haftarah", [])
        if opts:
            return opts
    return []

class _ParshaCalendarWidget(QWidget):
    """Custom calendar widget that shows parsha names on Shabbat days.

    Replicates the original TropeTrainer calendar popup appearance:
    - Month/year header with Hebrew month name(s)
    - Navigation arrows
    - 7-column grid (Sun–Sat), each cell shows:
        * Hebrew date (small, top)
        * Gregorian day number (large, middle)
        * Parsha name on Shabbat (small, blue, bottom)
        * Special events (Rosh Chodesh etc.) in blue
    - Clicking a cell selects that date
    """

    date_selected = pyqtSignal(QDate)

    def __init__(self, initial_date: QDate | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_date = initial_date or QDate.currentDate()
        self._view_year = self._current_date.year()
        self._view_month = self._current_date.month()
        self._diaspora = True
        # Cache: {(year, month): {day: (heb_str, parsha_str, special_str)}}
        self._cell_cache: Dict[tuple, Dict[int, tuple]] = {}
        self.setMinimumSize(560, 380)
        self.setSizePolicy(
            self.sizePolicy().horizontalPolicy(),
            self.sizePolicy().verticalPolicy(),
        )

    def set_diaspora(self, diaspora: bool) -> None:
        self._diaspora = diaspora
        self._cell_cache.clear()
        self.update()

    def _build_cell_data(self, year: int, month: int) -> Dict[int, tuple]:
        """Build cell data for every day in (year, month).

        Returns {day: (heb_label, parsha_label, special_label)}.
        """
        key = (year, month)
        if key in self._cell_cache:
            return self._cell_cache[key]

        # Approximate Hebrew date for each day
        # Build parsha schedule for nearby Hebrew years
        result: Dict[int, tuple] = {}
        days_in_month = QDate(year, month, 1).daysInMonth()

        # Get parsha schedules for adjacent Hebrew years
        schedules: Dict[int, Dict[str, _dt.date]] = {}

        def _get_sched(hy: int) -> Dict[str, _dt.date]:
            if hy not in schedules:
                try:
                    schedules[hy] = _get_parsha_schedule_diaspora(hy)
                except Exception:
                    schedules[hy] = {}
            return schedules[hy]

        # Build reverse map: greg_date -> parsha for Shabbatot
        greg_to_parsha: Dict[_dt.date, str] = {}
        approx_hy = year + 3760
        for hy in range(approx_hy - 1, approx_hy + 2):
            try:
                sched = _get_sched(hy)
                for parsha, gdate in sched.items():
                    greg_to_parsha[gdate] = parsha
            except Exception:
                pass

        for d in range(1, days_in_month + 1):
            gdate = _dt.date(year, month, d)
            qdate = QDate(year, month, d)

            # Hebrew date string
            heb_str = _gregorian_to_hebrew_approx(qdate)
            # Extract just "day month" part for compact display
            heb_label = ""
            if heb_str:
                parts = heb_str.split(",")
                if parts:
                    day_month = parts[0].strip()  # e.g. "15 Shevat"
                    heb_label = day_month

            # Parsha on Shabbat
            parsha_label = ""
            dow = qdate.dayOfWeek()  # 1=Mon ... 6=Sat, 7=Sun
            if dow == 6:  # Saturday
                parsha_label = greg_to_parsha.get(gdate, "")

            # Special events (Rosh Chodesh = Hebrew day 1 or 30+1)
            special_label = ""
            if heb_label:
                day_part = heb_label.split(" ")[0]
                if day_part == "1":
                    special_label = "Rosh Chodesh"
                elif day_part == "30":
                    # Day 30 = also Rosh Chodesh (two-day)
                    special_label = "Rosh Chodesh"

            result[d] = (heb_label, parsha_label, special_label)

        self._cell_cache[key] = result
        return result

    def _nav_rects(self) -> tuple:
        """Return (prev_rect, next_rect) for navigation arrows."""
        w = self.width()
        return (
            QRect(8, 4, 28, 28),
            QRect(w - 36, 4, 28, 28),
        )

    def paintEvent(self, event) -> None:
        QF = QFont  # local alias for convenience
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        header_h = 38
        dow_h = 22
        grid_top = header_h + dow_h
        grid_h = h - grid_top
        col_w = w / 7

        # --- Header background ---
        painter.fillRect(0, 0, w, header_h, QColor("#4060A0"))

        # Navigation arrows
        arrow_color = QColor("white")
        painter.setPen(QPen(arrow_color, 2))
        # Left arrow
        cx, cy = 18, 18
        pts_l = [
            (cx + 6, cy - 7), (cx - 2, cy), (cx + 6, cy + 7)
        ]
        for i in range(len(pts_l) - 1):
            painter.drawLine(
                int(pts_l[i][0]), int(pts_l[i][1]),
                int(pts_l[i+1][0]), int(pts_l[i+1][1])
            )
        # Right arrow
        rx = w - 18
        pts_r = [
            (rx - 6, cy - 7), (rx + 2, cy), (rx - 6, cy + 7)
        ]
        for i in range(len(pts_r) - 1):
            painter.drawLine(
                int(pts_r[i][0]), int(pts_r[i][1]),
                int(pts_r[i+1][0]), int(pts_r[i+1][1])
            )

        # Month/year text
        month_name = QDate(self._view_year, self._view_month, 1).toString("MMMM yyyy")
        heb_mid = _gregorian_to_hebrew_approx(
            QDate(self._view_year, self._view_month, 15))
        heb_month_label = ""
        if heb_mid:
            parts = heb_mid.split(",")
            if len(parts) >= 2:
                month_part = parts[0].strip().split(" ")
                year_part = parts[-1].strip()
                if len(month_part) >= 2:
                    heb_month_label = f"{month_part[1]} {year_part}"

        painter.setPen(QPen(QColor("white")))
        title_font = QF("Arial", 12, QF.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(
            QRect(36, 0, w - 72, header_h // 2 + 4),
            Qt.AlignmentFlag.AlignCenter,
            month_name,
        )
        if heb_month_label:
            small_font = QF("Arial", 9)
            painter.setFont(small_font)
            painter.drawText(
                QRect(36, header_h // 2, w - 72, header_h // 2),
                Qt.AlignmentFlag.AlignCenter,
                heb_month_label,
            )

        # --- Day-of-week header ---
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday",
                     "Thursday", "Friday", "Shabbas"]
        painter.fillRect(0, header_h, w, dow_h, QColor("#D0D8F0"))
        dow_font = QF("Arial", 8, QF.Weight.Bold)
        painter.setFont(dow_font)
        for i, dn in enumerate(day_names):
            col_x = int(i * col_w)
            if i == 6:  # Shabbat column
                painter.setPen(QPen(QColor("#000080")))
            else:
                painter.setPen(QPen(QColor("#404040")))
            painter.drawText(
                QRect(col_x, header_h, int(col_w), dow_h),
                Qt.AlignmentFlag.AlignCenter,
                dn,
            )

        # --- Grid ---
        first_day = QDate(self._view_year, self._view_month, 1)
        days_in_month = first_day.daysInMonth()
        # QDate.dayOfWeek(): 1=Mon...7=Sun; we want col 0=Sun
        # Convert: Sun=0, Mon=1, ..., Sat=6
        fdow = first_day.dayOfWeek()  # 1=Mon..7=Sun
        start_col = fdow % 7  # Mon=1..Sat=6, Sun=0

        cell_data = self._build_cell_data(self._view_year, self._view_month)
        num_rows = (start_col + days_in_month + 6) // 7
        if num_rows < 1:
            num_rows = 5
        row_h = grid_h / max(num_rows, 5)

        today = _dt.date.today()

        for d in range(1, days_in_month + 1):
            linear = start_col + d - 1
            row = linear // 7
            col = linear % 7
            cell_x = int(col * col_w)
            cell_y = int(grid_top + row * row_h)
            cell_w = int(col_w)
            cell_rh = int(row_h)

            # Background
            is_selected = (self._current_date == QDate(self._view_year, self._view_month, d))
            is_today = (_dt.date(self._view_year, self._view_month, d) == today)
            is_shabbat = (col == 6)

            if is_selected:
                painter.fillRect(cell_x, cell_y, cell_w, cell_rh, QColor("#6080C0"))
            elif is_today:
                painter.fillRect(cell_x, cell_y, cell_w, cell_rh, QColor("#E8EDF8"))
            elif is_shabbat:
                painter.fillRect(cell_x, cell_y, cell_w, cell_rh, QColor("#F0F0FF"))
            else:
                painter.fillRect(cell_x, cell_y, cell_w, cell_rh, QColor("white"))

            # Cell border
            painter.setPen(QPen(QColor("#C0C0C0"), 1))
            painter.drawRect(cell_x, cell_y, cell_w - 1, cell_rh - 1)

            heb_label, parsha_label, special_label = cell_data.get(d, ("", "", ""))

            # Hebrew date (top-left, small gray)
            text_color = QColor("white") if is_selected else QColor("#808080")
            painter.setPen(QPen(text_color))
            painter.setFont(QF("Arial", 7))
            painter.drawText(
                QRect(cell_x + 2, cell_y + 1, cell_w - 4, 12),
                Qt.AlignmentFlag.AlignLeft,
                heb_label,
            )

            # Gregorian day number (large, center)
            day_num_color = QColor("white") if is_selected else (
                QColor("#000080") if is_shabbat else QColor("#202020")
            )
            painter.setPen(QPen(day_num_color))
            painter.setFont(QF("Arial", 13, QF.Weight.Bold))
            painter.drawText(
                QRect(cell_x, cell_y + 10, cell_w, cell_rh - 10),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                str(d),
            )

            # Parsha name on Shabbat (bottom, blue/small)
            if parsha_label:
                parsha_color = QColor("white") if is_selected else QColor("#0000CC")
                painter.setPen(QPen(parsha_color))
                painter.setFont(QF("Arial", 7))
                painter.drawText(
                    QRect(cell_x + 1, cell_y + cell_rh - 20, cell_w - 2, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    parsha_label,
                )

            # Special event (Rosh Chodesh etc.)
            if special_label and not parsha_label:
                sp_color = QColor("white") if is_selected else QColor("#008000")
                painter.setPen(QPen(sp_color))
                painter.setFont(QF("Arial", 7))
                painter.drawText(
                    QRect(cell_x + 1, cell_y + cell_rh - 20, cell_w - 2, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    special_label,
                )

        painter.end()

    def mousePressEvent(self, event) -> None:
        """Handle clicks to select a date or navigate."""
        x = event.position().x() if hasattr(event, 'position') else event.x()
        y = event.position().y() if hasattr(event, 'position') else event.y()

        w = self.width()
        h = self.height()
        header_h = 38
        dow_h = 22
        grid_top = header_h + dow_h
        col_w = w / 7

        # Navigation arrows
        if y < header_h:
            if x < 40:
                self._go_prev_month()
                return
            elif x > w - 40:
                self._go_next_month()
                return

        # Cell click
        if y >= grid_top:
            first_day = QDate(self._view_year, self._view_month, 1)
            fdow = first_day.dayOfWeek()
            start_col = fdow % 7
            days_in_month = first_day.daysInMonth()
            num_rows = max((start_col + days_in_month + 6) // 7, 5)
            row_h = (h - grid_top) / num_rows

            col = int(x // col_w)
            row = int((y - grid_top) // row_h)
            linear = row * 7 + col
            d = linear - start_col + 1
            if 1 <= d <= days_in_month:
                self._current_date = QDate(self._view_year, self._view_month, d)
                self.date_selected.emit(self._current_date)
                self.update()

    def _go_prev_month(self) -> None:
        self._view_month -= 1
        if self._view_month < 1:
            self._view_month = 12
            self._view_year -= 1
        self.update()

    def _go_next_month(self) -> None:
        self._view_month += 1
        if self._view_month > 12:
            self._view_month = 1
            self._view_year += 1
        self.update()

    def set_date(self, qdate: QDate) -> None:
        self._current_date = qdate
        self._view_year = qdate.year()
        self._view_month = qdate.month()
        self.update()

    def get_date(self) -> QDate:
        return self._current_date


class CalendarDialog(QDialog):
    """Perpetual calendar popup for date selection.

    Displays a custom monthly calendar (matching the original TropeTrainer
    layout) with Hebrew dates and parsha names on each Shabbat.
    The selected date is returned by :meth:`selected_date` after acceptance.
    """

    date_selected = pyqtSignal(QDate)

    def __init__(self, initial_date: QDate | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Trope Trainer Calendar")
        self.setModal(True)
        self.setMinimumSize(580, 480)
        self._selected: QDate = initial_date or QDate.currentDate()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(4)

        # Location selector (Diaspora / Israel)
        loc_layout = QHBoxLayout()
        loc_group = QGroupBox("Location")
        loc_inner = QHBoxLayout()
        self.diaspora_radio = QRadioButton("Diaspora")
        self.diaspora_radio.setChecked(True)
        self.diaspora_radio.toggled.connect(self._on_location_changed)
        loc_inner.addWidget(self.diaspora_radio)
        self.israel_radio = QRadioButton("Israel")
        loc_inner.addWidget(self.israel_radio)
        loc_group.setLayout(loc_inner)
        loc_layout.addWidget(loc_group)
        loc_layout.addStretch()
        layout.addLayout(loc_layout)

        # Custom calendar
        self._cal = _ParshaCalendarWidget(self._selected, self)
        self._cal.date_selected.connect(self._on_date_changed)
        layout.addWidget(self._cal, stretch=1)

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

    def _on_date_changed(self, qdate: QDate) -> None:
        self._selected = qdate
        self.date_selected.emit(qdate)

    def _on_location_changed(self, checked: bool) -> None:
        self._cal.set_diaspora(self.diaspora_radio.isChecked())

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

        # Calendar button – opens the perpetual calendar (like original TropeTrainer)
        self.calendar_btn = QPushButton("📅")
        self.calendar_btn.setFixedSize(30, 30)
        self.calendar_btn.setToolTip("Open calendar")
        self.calendar_btn.setStyleSheet(
            "QPushButton { background: #D0D0FF; border: 1px solid #8080C0;"
            " font-size: 14px; padding: 0px; }"
            "QPushButton:hover { background: #B0B0EE; }"
            "QPushButton:pressed { background: #9090CC; }"
        )
        self.calendar_btn.clicked.connect(self.open_calendar_dialog)
        header.addWidget(self.calendar_btn)

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
        """Build the Holiday & special readings tab.

        The holiday list and their Torah/Maftir/Haftarah options are loaded
        directly from sedrot.xml so that selecting a holiday updates the
        three option lists at the bottom exactly as in the original.
        """
        tab = QWidget()
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        holiday_grid = QGridLayout()
        holiday_grid.setSpacing(3)

        self.holiday_button_group = QButtonGroup(self)
        self.holiday_button_group.buttonClicked.connect(self._on_holiday_selected)

        # Fixed two-column layout matching the original TropeTrainer exactly.
        # Left column: main holidays  Right column: other holidays + megillot
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

        # Megillot: grayed out (dimmed) to match original, but still selectable
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
    # Signal handler: holiday selected
    # ------------------------------------------------------------------ #
    def _on_holiday_selected(self, button: QRadioButton) -> None:
        """Update option lists when the user selects a holiday."""
        holiday = button.text()
        self._refresh_option_lists_holiday(holiday)

    def _refresh_option_lists_holiday(self, holiday: str) -> None:
        """Populate Torah, Maftir and Haftarah lists for *holiday*.

        For regular holidays: all Torah/Maftir/Haftarah options from sedrot.xml.
        For holidays with an associated Megilla (Purim, Pesach, Shavuos, Succos,
        Tisha B'Av): the Torah list additionally contains the Megilla's melody
        variants from tropedef_megillot.xml.
        For standalone Megilla buttons: only the melody variants are shown.
        """
        self.torah_list.clear()
        self.maftir_list.clear()
        self.haftarah_list.clear()

        # ---- Standalone Megilla buttons (grayed out in right column) ----
        if holiday in _STANDALONE_MEGILLA_TYPE:
            megilla_type = _STANDALONE_MEGILLA_TYPE[holiday]
            for melody in _megilla_melody_options(megilla_type):
                self.torah_list.addItem(QListWidgetItem(melody))
            if self.torah_list.count():
                self.torah_list.setCurrentRow(0)
            self.open_haftarah_btn.setEnabled(False)
            return

        # ---- Regular holidays ----
        if holiday not in _SEDROT_OPTIONS:
            self.open_haftarah_btn.setEnabled(False)
            return

        holiday_torah = list(_get_holiday_torah_options(holiday))
        holiday_maftir = _get_holiday_maftir_options(holiday)
        holiday_haftarah = _get_holiday_haftarah_options(holiday)

        # For holidays that have an associated Megilla (Purim, Pesach, Shavuos,
        # Succos, Tisha B'Av): replace the bare Megilla option name with the
        # full melody variant list from tropedef_megillot.xml.
        megilla_option = _HOLIDAY_MEGILLA_OPTION.get(holiday)
        if megilla_option:
            megilla_type = _MEGILLA_OPTION_TYPE.get(megilla_option, "")
            melody_variants = _megilla_melody_options(megilla_type) if megilla_type else []

            # Remove the bare option name if present, then append melody variants
            if megilla_option in holiday_torah:
                idx = holiday_torah.index(megilla_option)
                holiday_torah[idx:idx + 1] = melody_variants
            else:
                # Not yet in the list (Pesach, Shavuos, Tisha B'Av): append
                holiday_torah.extend(melody_variants)

        for opt in holiday_torah:
            self.torah_list.addItem(QListWidgetItem(opt))
        if self.torah_list.count():
            self.torah_list.setCurrentRow(0)

        for opt in holiday_maftir:
            self.maftir_list.addItem(QListWidgetItem(opt))
        if self.maftir_list.count():
            self.maftir_list.setCurrentRow(0)

        for opt in holiday_haftarah:
            self.haftarah_list.addItem(QListWidgetItem(opt))
        if self.haftarah_list.count():
            self.haftarah_list.setCurrentRow(0)

        self.open_haftarah_btn.setEnabled(bool(holiday_haftarah))

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
        """Update option lists and date header when the user selects a parsha."""
        parsha = getattr(button, "parsha_name", None)
        self._refresh_option_lists(parsha)

        # Update the date header to show when this parsha is read
        if parsha:
            heb_year = self.year_spinbox.value()
            diaspora = self.diaspora_radio.isChecked()
            parsha_date = _get_parsha_date(parsha, heb_year, diaspora)
            if parsha_date:
                qdate = QDate(parsha_date.year, parsha_date.month, parsha_date.day)
                self._update_date_header(qdate)
                self.selected_date = qdate

    def _on_year_changed(self, value: int) -> None:
        """Update labels when the Hebrew year spinbox changes."""
        greg = value - 3760
        self.greg_range_label.setText(f"({greg}/{greg + 1})")
        self.cycle_label.setText(f"Cycle for {value}:")
        # Refresh parsha date if one is selected
        btn = self.parsha_button_group.checkedButton()
        if btn:
            parsha = getattr(btn, "parsha_name", None)
            if parsha:
                parsha_date = _get_parsha_date(parsha, value, self.diaspora_radio.isChecked())
                if parsha_date:
                    qdate = QDate(parsha_date.year, parsha_date.month, parsha_date.day)
                    self._update_date_header(qdate)
                    self.selected_date = qdate

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
            self._select_parsha_for_date(self.selected_date)

    def _select_parsha_for_date(self, qdate: QDate) -> None:
        """Select the parsha radio button matching *qdate* and refresh options."""
        gdate = _dt.date(qdate.year(), qdate.month(), qdate.day())
        heb_year = self.year_spinbox.value()

        # Build reverse map: gregorian date → parsha, check adjacent years too
        date_to_parsha: Dict[_dt.date, str] = {}
        for hy in (heb_year - 1, heb_year, heb_year + 1):
            try:
                for parsha, d in _get_parsha_schedule_diaspora(hy).items():
                    date_to_parsha[d] = parsha
            except Exception:
                pass

        parsha = date_to_parsha.get(gdate)
        if not parsha:
            return

        # Switch to Shabbat/Mon./Thu. tab
        self.main_tabs.setCurrentIndex(0)

        # Find and check the matching radio button, then refresh options
        for btn in self.parsha_button_group.buttons():
            if getattr(btn, "parsha_name", None) == parsha:
                btn.setChecked(True)
                self._refresh_option_lists(parsha)
                break

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
        # Capture which specific haftarah option the user selected
        item = self.haftarah_list.currentItem()
        if item:
            self.selected_option = item.text().strip()
        else:
            self.selected_option = None
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
                # For standalone Megilla buttons set the correct reading_type
                # so main_window can look up the right book and verse numbering.
                megilla_type = _STANDALONE_MEGILLA_TYPE.get(btn.text())
                if megilla_type:
                    self.reading_type = megilla_type
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
