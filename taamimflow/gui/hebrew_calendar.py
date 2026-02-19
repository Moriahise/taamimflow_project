"""
hebrew_calendar.py – Ta'amimFlow perpetual Jewish calendar engine.

Provides:
  - Accurate Gregorian <-> Hebrew date conversion (astronomical algorithm).
    The -1 correction ensures dates match TropeTrainer's convention that
    the Hebrew day visible during Gregorian daytime is the one that began
    at the PREVIOUS sunset.
  - Full Jewish holiday table for Diaspora and Israel
  - Special Shabbatot (Shekalim, Zachor, Parah, HaChodesh, HaGadol,
    Shuva, Rosh Chodesh, Chanukah)
  - Shabbat parasha schedule with correct doubling rules

Self-contained – no external library required.
"""

from __future__ import annotations
import datetime as _dt
import calendar as _cal
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Julian Day conversions
# ---------------------------------------------------------------------------
_HEBREW_EPOCH_JD = 347998  # JD of 1 Tishrei, Year 1


def _jd(y: int, m: int, d: int) -> int:
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045


def _greg(jd: int) -> _dt.date:
    a = jd + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    d2 = (4 * c + 3) // 1461
    e = c - (1461 * d2) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d2 - 4800 + m // 10
    return _dt.date(year, month, day)


# ---------------------------------------------------------------------------
# Hebrew year arithmetic
# ---------------------------------------------------------------------------

def is_leap(year: int) -> bool:
    """True if Hebrew year is a leap year (13 months)."""
    return (7 * year + 1) % 19 < 7


def _elapsed_days(year: int) -> int:
    mo = (235 * year - 234) // 19
    parts = 12084 + 13753 * mo
    day = mo * 29 + parts // 25920
    if (3 * (day + 1)) % 7 < 3:
        day += 1
    return day


def year_length(year: int) -> int:
    return _elapsed_days(year + 1) - _elapsed_days(year)


def rh_jd(year: int) -> int:
    """Julian Day Number for 1 Tishrei of Hebrew year."""
    return _HEBREW_EPOCH_JD + _elapsed_days(year) - 1


def rh_date(year: int) -> _dt.date:
    return _greg(rh_jd(year))


def month_lengths(year: int) -> List[int]:
    """Month lengths from Tishrei (index 0)."""
    yd = year_length(year)
    if is_leap(year):
        ch, kl = (29, 29) if yd == 383 else (29, 30) if yd == 384 else (30, 30)
        return [30, ch, kl, 29, 30, 30, 29, 30, 29, 30, 29, 30, 29]
    else:
        ch, kl = (29, 29) if yd == 353 else (29, 30) if yd == 354 else (30, 30)
        return [30, ch, kl, 29, 30, 29, 30, 29, 30, 29, 30, 29]


_MN_REG  = ["Tishrei","Cheshvan","Kislev","Tevet","Shevat","Adar",
             "Nisan","Iyar","Sivan","Tammuz","Av","Elul"]
_MN_LEAP = ["Tishrei","Cheshvan","Kislev","Tevet","Shevat","Adar I",
             "Adar II","Nisan","Iyar","Sivan","Tammuz","Av","Elul"]


def month_names(year: int) -> List[str]:
    return _MN_LEAP if is_leap(year) else _MN_REG


# ---------------------------------------------------------------------------
# Gregorian -> Hebrew  (with sunset correction)
# ---------------------------------------------------------------------------

def greg_to_hebrew(y: int, m: int, d: int) -> Tuple[int, int, int, str]:
    """
    Returns (h_year, h_month_1indexed, h_day, month_name).
    h_month is 1-indexed from Tishrei.

    Sunset correction: subtract 1 from day_in_year so the Hebrew date
    shown corresponds to the daytime portion of the Gregorian date,
    matching TropeTrainer's display convention exactly.
    """
    jdv = _jd(y, m, d)
    hy = int((jdv - _HEBREW_EPOCH_JD) / 365.25) + 3760
    while rh_jd(hy + 1) <= jdv:
        hy += 1
    while rh_jd(hy) > jdv:
        hy -= 1
    day_in_year = jdv - rh_jd(hy) - 1  # -1: sunset correction
    ml = month_lengths(hy)
    mn = month_names(hy)
    for mi, mlen in enumerate(ml):
        if day_in_year < mlen:
            return hy, mi + 1, day_in_year + 1, mn[mi]
        day_in_year -= mlen
    return hy, len(ml), ml[-1], mn[-1]


def greg_to_hebrew_label(y: int, m: int, d: int) -> str:
    """Return 'DD MonthName' for calendar cell display."""
    _, _, hd, mname = greg_to_hebrew(y, m, d)
    return f"{hd} {mname}"


def greg_to_hebrew_str(y: int, m: int, d: int) -> str:
    """Return 'DD MonthName YYYY'."""
    hy, _, hd, mname = greg_to_hebrew(y, m, d)
    return f"{hd} {mname} {hy}"


# ---------------------------------------------------------------------------
# Hebrew -> Gregorian
# ---------------------------------------------------------------------------

def hebrew_to_greg(h_year: int, h_month_1: int, h_day: int) -> _dt.date:
    """h_month_1 is 1-indexed from Tishrei."""
    base_jd = rh_jd(h_year) + 1  # +1 reverses sunset correction
    ml = month_lengths(h_year)
    for mi in range(h_month_1 - 1):
        base_jd += ml[mi]
    base_jd += h_day - 1
    return _greg(base_jd)


# ---------------------------------------------------------------------------
# Day-of-week utilities (0=Sun … 6=Sat)
# ---------------------------------------------------------------------------

def _dow(d: _dt.date) -> int:
    return (d.weekday() + 1) % 7


def _prev_or_on_shabbat(d: _dt.date) -> _dt.date:
    """Last Saturday on or before d."""
    return d - _dt.timedelta(days=(_dow(d) - 6) % 7)


def _next_shabbat(d: _dt.date) -> _dt.date:
    """Next Saturday on or after d."""
    return d + _dt.timedelta(days=(6 - _dow(d)) % 7)


def _shabbat_before(d: _dt.date) -> _dt.date:
    """Saturday strictly before d."""
    s = _prev_or_on_shabbat(d)
    return s if s < d else s - _dt.timedelta(7)


# ---------------------------------------------------------------------------
# Month index helpers
# ---------------------------------------------------------------------------

def _midx(h_year: int, prefix: str) -> int:
    """1-indexed Tishrei-based month whose name starts with prefix."""
    for i, n in enumerate(month_names(h_year)):
        if n.startswith(prefix):
            return i + 1
    return 0


def _adar(h_year: int) -> int:
    """Adar II in leap years, Adar in regular years (1-indexed)."""
    return _midx(h_year, "Adar II") if is_leap(h_year) else _midx(h_year, "Adar")


def _adar1(h_year: int) -> int:
    """Adar I index (= Adar in non-leap)."""
    return _midx(h_year, "Adar")


# ---------------------------------------------------------------------------
# Holiday builders
# ---------------------------------------------------------------------------

def _add(r: Dict[_dt.date, List[str]], d: _dt.date, lbl: str) -> None:
    r.setdefault(d, []).append(lbl)


def _tishrei_holidays(hy: int, diaspora: bool) -> Dict[_dt.date, List[str]]:
    r: Dict[_dt.date, List[str]] = {}
    rh1 = hebrew_to_greg(hy, 1, 1)
    _add(r, rh1,                           "Rosh Hashana 1")
    _add(r, rh1 + _dt.timedelta(1),        "Rosh Hashana 2")
    fg = hebrew_to_greg(hy, 1, 3)
    if _dow(fg) == 6: fg += _dt.timedelta(1)
    _add(r, fg,                            "Fast of Gedaliah")
    yk = hebrew_to_greg(hy, 1, 10)
    _add(r, yk,                            "Yom Kippur")
    suk = hebrew_to_greg(hy, 1, 15)
    _add(r, suk,                           "Sukkot 1")
    if diaspora: _add(r, suk + _dt.timedelta(1), "Sukkot 2")
    for i in range(2, 6):
        _add(r, suk + _dt.timedelta(i),    "Chol HaMoed Sukkot")
    _add(r, suk + _dt.timedelta(6),        "Hoshana Rabbah")
    sa = suk + _dt.timedelta(7)
    if diaspora:
        _add(r, sa,                        "Shemini Atzeret")
        _add(r, sa + _dt.timedelta(1),     "Simchat Torah")
    else:
        _add(r, sa,                        "Shemini Atzeret/Simchat Torah")
    return r


def _chanukah(hy: int) -> Dict[_dt.date, List[str]]:
    r: Dict[_dt.date, List[str]] = {}
    chan1 = hebrew_to_greg(hy, 3, 25)  # 25 Kislev
    for i in range(8):
        _add(r, chan1 + _dt.timedelta(i), "Chanukah" if i == 0 else f"Chanukah Day {i+1}")
    _add(r, hebrew_to_greg(hy, 4, 10), "Asara B'Tevet")  # 10 Tevet
    return r


def _shevat_holidays(hy: int) -> Dict[_dt.date, List[str]]:
    r: Dict[_dt.date, List[str]] = {}
    _add(r, hebrew_to_greg(hy, 5, 15), "Tu B'Shvat")
    return r


def _adar_holidays(hy: int) -> Dict[_dt.date, List[str]]:
    r: Dict[_dt.date, List[str]] = {}
    if is_leap(hy):
        _add(r, hebrew_to_greg(hy, _adar1(hy), 14), "Purim Katan")
        _add(r, hebrew_to_greg(hy, _adar1(hy), 15), "Shushan Purim Katan")
    am = _adar(hy)
    ta = hebrew_to_greg(hy, am, 13)
    if _dow(ta) == 6: ta -= _dt.timedelta(2)
    _add(r, ta,                           "Ta'anit Esther")
    _add(r, hebrew_to_greg(hy, am, 14),   "Purim")
    _add(r, hebrew_to_greg(hy, am, 15),   "Shushan Purim")
    return r


def _nisan_holidays(hy: int, diaspora: bool) -> Dict[_dt.date, List[str]]:
    r: Dict[_dt.date, List[str]] = {}
    ni = _midx(hy, "Nisan")
    pes1 = hebrew_to_greg(hy, ni, 15)
    _add(r, pes1 - _dt.timedelta(1),      "Erev Pesach")
    _add(r, pes1,                          "Pesach 1")
    if diaspora: _add(r, pes1 + _dt.timedelta(1), "Pesach 2")
    for i in range(2, 6):
        _add(r, pes1 + _dt.timedelta(i),  "Chol HaMoed Pesach")
    _add(r, pes1 + _dt.timedelta(6),      "Pesach 7")
    if diaspora: _add(r, pes1 + _dt.timedelta(7), "Pesach 8")
    yhs = hebrew_to_greg(hy, ni, 27)
    dw = _dow(yhs)
    if dw == 5: yhs -= _dt.timedelta(1)
    elif dw == 0: yhs += _dt.timedelta(1)
    _add(r, yhs, "Yom HaShoah")
    return r


def _iyar_holidays(hy: int) -> Dict[_dt.date, List[str]]:
    r: Dict[_dt.date, List[str]] = {}
    iy = _midx(hy, "Iyar")
    yzk = hebrew_to_greg(hy, iy, 4)
    dw = _dow(yzk)
    if dw == 5: yzk -= _dt.timedelta(1)
    elif dw == 6: yzk -= _dt.timedelta(2)
    elif dw == 0: yzk += _dt.timedelta(1)
    _add(r, yzk,                           "Yom HaZikaron")
    _add(r, yzk + _dt.timedelta(1),        "Yom HaAtzmaut")
    _add(r, hebrew_to_greg(hy, iy, 18),    "Lag B'Omer")
    _add(r, hebrew_to_greg(hy, iy, 28),    "Yom Yerushalayim")
    return r


def _sivan_holidays(hy: int, diaspora: bool) -> Dict[_dt.date, List[str]]:
    r: Dict[_dt.date, List[str]] = {}
    si = _midx(hy, "Sivan")
    shav1 = hebrew_to_greg(hy, si, 6)
    _add(r, shav1, "Shavuot 1")
    if diaspora: _add(r, shav1 + _dt.timedelta(1), "Shavuot 2")
    return r


def _av_holidays(hy: int) -> Dict[_dt.date, List[str]]:
    r: Dict[_dt.date, List[str]] = {}
    ta = _midx(hy, "Tammuz")
    av = _midx(hy, "Av")
    t17 = hebrew_to_greg(hy, ta, 17)
    if _dow(t17) == 6: t17 += _dt.timedelta(1)
    _add(r, t17, "17 Tammuz")
    tab = hebrew_to_greg(hy, av, 9)
    if _dow(tab) == 6: tab += _dt.timedelta(1)
    _add(r, tab, "Tisha B'Av")
    _add(r, hebrew_to_greg(hy, av, 15), "Tu B'Av")
    return r


# ---------------------------------------------------------------------------
# Rosh Chodesh
# ---------------------------------------------------------------------------

def _rosh_chodesh(hy: int) -> Dict[_dt.date, List[str]]:
    r: Dict[_dt.date, List[str]] = {}
    ml = month_lengths(hy)
    mn = month_names(hy)
    base_jd = rh_jd(hy) + 1  # sunset correction
    offset = 0
    for mi, (mlen, mname) in enumerate(zip(ml, mn)):
        next_mi = (mi + 1) % len(ml)
        next_name = mn[next_mi] if next_mi < len(mn) else month_names(hy + 1)[0]
        lbl = f"Rosh Chodesh {next_name}"
        # Day 1 of next month
        rc_jd = base_jd + offset + mlen
        _add(r, _greg(rc_jd), lbl)
        if mlen == 30:
            # Two-day: also day 30 of current month
            _add(r, _greg(rc_jd - 1), lbl)
        offset += mlen
    return r


# ---------------------------------------------------------------------------
# Special Shabbatot
# ---------------------------------------------------------------------------

def _special_shabbatot(hy: int) -> Dict[_dt.date, List[str]]:
    r: Dict[_dt.date, List[str]] = {}

    # Shabbat Shuva (between RH and Yom Kippur)
    rh1 = hebrew_to_greg(hy, 1, 1)
    yk  = hebrew_to_greg(hy, 1, 10)
    ss = rh1 + _dt.timedelta((6 - _dow(rh1)) % 7)
    if ss < yk:
        _add(r, ss, "Shabbas Shuva")

    # Chanukah Shabbatot
    chan1 = hebrew_to_greg(hy, 3, 25)
    chan8 = chan1 + _dt.timedelta(7)
    sh1 = _next_shabbat(chan1)
    if sh1 <= chan8:
        _add(r, sh1, "Shabbas Chanukah")
    sh2 = sh1 + _dt.timedelta(7)
    if sh2 <= chan8:
        _add(r, sh2, "Shabbas Chanukah II")

    # Shabbat Shekalim: Shabbat on or immediately before 1 Adar I
    rc_adar1 = hebrew_to_greg(hy, _adar1(hy), 1)
    sh_shekalim = _prev_or_on_shabbat(rc_adar1)
    _add(r, sh_shekalim, "Shabbas Shekalim")

    # Purim date (Adar or Adar II)
    purim = hebrew_to_greg(hy, _adar(hy), 14)

    # Shabbat Zachor: Shabbat immediately before Purim
    _add(r, _shabbat_before(purim), "Shabbas Zachor")

    # Shabbat HaChodesh: Shabbat on or immediately before 1 Nisan
    rc_nisan = hebrew_to_greg(hy, _midx(hy, "Nisan"), 1)
    sh_haChodesh = _prev_or_on_shabbat(rc_nisan)
    _add(r, sh_haChodesh, "Shabbas HaChodesh")

    # Shabbat Parah: Shabbat before Shabbat HaChodesh
    _add(r, sh_haChodesh - _dt.timedelta(7), "Shabbas Parah")

    # Shabbat HaGadol: Shabbat before Pesach
    pes1 = hebrew_to_greg(hy, _midx(hy, "Nisan"), 15)
    _add(r, _shabbat_before(pes1), "Shabbas HaGadol")

    return r


# ---------------------------------------------------------------------------
# Master event table
# ---------------------------------------------------------------------------

def get_year_events(hy: int, diaspora: bool = True) -> Dict[_dt.date, List[str]]:
    """All events (holidays + Rosh Chodesh + special Shabbatot) for Hebrew year."""
    result: Dict[_dt.date, List[str]] = {}

    def _merge(d: Dict[_dt.date, List[str]]) -> None:
        for date, labels in d.items():
            result.setdefault(date, []).extend(labels)

    _merge(_tishrei_holidays(hy, diaspora))
    _merge(_chanukah(hy))
    _merge(_shevat_holidays(hy))
    _merge(_adar_holidays(hy))
    _merge(_nisan_holidays(hy, diaspora))
    _merge(_iyar_holidays(hy))
    _merge(_sivan_holidays(hy, diaspora))
    _merge(_av_holidays(hy))
    _merge(_rosh_chodesh(hy))
    _merge(_special_shabbatot(hy))

    # Shabbat Rosh Chodesh (wherever Shabbat and Rosh Chodesh coincide)
    rc_dates = {d for d, lbls in result.items()
                if any("Rosh Chodesh" in l for l in lbls) and _dow(d) == 6}
    for d in rc_dates:
        _add(result, d, "Shabbas Rosh Chodesh")

    return result


# ---------------------------------------------------------------------------
# Parasha schedule
# ---------------------------------------------------------------------------

_PARSHA_ORDER = [
    "Bereishis","Noach","Lech Lecha","Vayeira","Chayei Sarah",
    "Toldos","Vayeitzei","Vayishlach","Vayeishev","Mikeitz",
    "Vayigash","Vayechi",
    "Shemos","Va'eira","Bo","Beshalach","Yisro","Mishpatim",
    "Terumah","Tetzaveh","Ki Sisa","Vayakhel","Pekudei",
    "Vayikra","Tzav","Shemini","Tazria","Metzora",
    "Acharei","Kedoshim","Emor","Behar","Bechukosai",
    "Bamidbar","Nasso","Beha'aloscha","Shelach","Korach",
    "Chukas","Balak","Pinchas","Mattos","Masei",
    "Devarim","Va'Eschanan","Eikev","Re'eh","Shoftim",
    "Ki Seitzei","Ki Savo","Nitzavim","Vayeilech","Haazinu",
    "V'zos HaBracha",
]

_COMBINE_NON_LEAP = [
    ("Nitzavim","Vayeilech"),("Vayakhel","Pekudei"),
    ("Tazria","Metzora"),("Acharei","Kedoshim"),
    ("Behar","Bechukosai"),("Mattos","Masei"),
]
_COMBINE_LEAP = [("Mattos","Masei"),("Nitzavim","Vayeilech")]


def get_parsha_schedule(hy: int) -> Dict[str, _dt.date]:
    """Return {parsha_name: Gregorian_date} for Diaspora reading schedule."""
    # Simchat Torah = 23 Tishrei (diaspora)
    st_jd = rh_jd(hy) + 22 + 1  # +1 sunset correction
    st_date = _greg(st_jd)
    # First Shabbat AFTER Simchat Torah
    delta = (6 - _dow(st_date)) % 7
    if delta == 0: delta = 7
    first_shabbat = st_date + _dt.timedelta(delta)

    # Last Shabbat before next RH
    next_rh = rh_date(hy + 1)
    last_shabbat = next_rh - _dt.timedelta((_dow(next_rh) + 1) % 7 or 7)

    num_shabbatot = (last_shabbat - first_shabbat).days // 7 + 1
    portions = list(_PARSHA_ORDER[:-1])
    candidates = _COMBINE_LEAP if is_leap(hy) else _COMBINE_NON_LEAP
    sched = list(portions)

    while len(sched) > num_shabbatot:
        for a, b in candidates:
            if a in sched and b in sched:
                ia, ib = sched.index(a), sched.index(b)
                if ib == ia + 1:
                    sched[ia] = f"{a}+{b}"
                    sched.pop(ib)
                    break
        else:
            break

    result: Dict[str, _dt.date] = {}
    for i, p in enumerate(sched):
        result[p] = first_shabbat + _dt.timedelta(weeks=i)
    result["V'zos HaBracha"] = st_date
    return result


# ---------------------------------------------------------------------------
# Main entry point for calendar widget
# ---------------------------------------------------------------------------

def build_month_data(
    year: int, month: int, diaspora: bool = True
) -> Dict[int, Tuple[str, str, str]]:
    """
    Return {day: (heb_label, parsha_label, event_label)} for every day
    in Gregorian (year, month).  Used by _ParshaCalendarWidget.
    """
    days_in = _cal.monthrange(year, month)[1]
    hy_mid = greg_to_hebrew(year, month, 15)[0]

    # Gather events across relevant Hebrew years
    events: Dict[_dt.date, List[str]] = {}
    for hy in range(hy_mid - 1, hy_mid + 2):
        for d, lbls in get_year_events(hy, diaspora).items():
            events.setdefault(d, []).extend(lbls)

    # Parsha schedule
    parsha_map: Dict[_dt.date, str] = {}
    for hy in range(hy_mid - 1, hy_mid + 2):
        try:
            for p, gd in get_parsha_schedule(hy).items():
                parsha_map[gd] = p
        except Exception:
            pass

    result: Dict[int, Tuple[str, str, str]] = {}
    for d in range(1, days_in + 1):
        gdate = _dt.date(year, month, d)
        heb_label = greg_to_hebrew_label(year, month, d)
        parsha_label = parsha_map.get(gdate, "") if _dow(gdate) == 6 else ""
        ev_list = events.get(gdate, [])
        event_label = ", ".join(ev_list)
        result[d] = (heb_label, parsha_label, event_label)

    return result


def header_hebrew_months(year: int, month: int) -> str:
    """Return e.g. 'Shevat 5786' or 'Shevat 5786 / Adar 5786' for header."""
    last_day = _cal.monthrange(year, month)[1]
    hy1, _, _, mn1 = greg_to_hebrew(year, month, 1)
    hy2, _, _, mn2 = greg_to_hebrew(year, month, last_day)
    if mn1 == mn2:
        return f"{mn1} {hy1}"
    return f"{mn1} {hy1} / {mn2} {hy2}"
