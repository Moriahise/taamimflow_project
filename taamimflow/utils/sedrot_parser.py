"""Parser for sedrot.xml – Torah reading aliyah boundaries.

Handles Torah, Haftarah, Megillot, and Holiday readings.
Returns exact (chapter, verse) aliyah start points and the correct
book name/number for display.

Key improvement: ``option_name`` parameter allows looking up a specific
sub-option within a holiday reading (e.g. "Day 8 (Weekday)" within Pesach).
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

# ── Book abbreviation → (book_num, full_display_name) ────────────────
# book_num: 1-5 = Torah, 6+ = Nevi'im/Ketuvim (no chapter-wrap needed)
_BOOK_INFO: Dict[str, Tuple[int, str]] = {
    # Torah
    "GEN": (1, "Bereshit/Genesis"),
    "EXO": (2, "Shemot/Exodus"),
    "LEV": (3, "Vayikra/Leviticus"),
    "NUM": (4, "Bamidbar/Numbers"),
    "DEU": (5, "Devarim/Deuteronomy"),
    # Nevi'im – Former
    "JOS": (6,  "Joshua"),
    "JUD": (7,  "Judges"),
    "1SA": (8,  "I Samuel"),
    "2SA": (9,  "II Samuel"),
    "1KI": (10, "I Kings"),
    "2KI": (11, "II Kings"),
    # Nevi'im – Latter
    "ISA": (12, "Isaiah"),
    "JER": (13, "Jeremiah"),
    "EZE": (14, "Ezekiel"),
    "HOS": (15, "Hosea"),
    "JOE": (16, "Joel"),
    "AMO": (17, "Amos"),
    "OBA": (18, "Obadiah"),
    "JON": (19, "Jonah"),
    "MIC": (20, "Micah"),
    "NAH": (21, "Nahum"),
    "HAB": (22, "Habakkuk"),
    "ZEP": (23, "Zephaniah"),
    "HAG": (24, "Haggai"),
    "ZEC": (25, "Zechariah"),
    "MAL": (26, "Malachi"),
    # Ketuvim
    "PSA": (27, "Psalms"),
    "PRO": (28, "Proverbs"),
    "JOB": (29, "Job"),
    "RUT": (30, "Ruth"),
    "LAM": (31, "Lamentations"),
    "QOH": (32, "Kohelet/Ecclesiastes"),
    "EST": (33, "Esther"),
    "SOS": (34, "Shir HaShirim"),
    "NEH": (35, "Nehemiah"),
    "EZR": (36, "Ezra"),
    "1CH": (37, "I Chronicles"),
    "2CH": (38, "II Chronicles"),
}

# ── Aliyah attribute names ────────────────────────────────────────────
_ALIYAH_ATTRS: List[Tuple[str, int, str]] = [
    ("KOHEN",    1, "Rishon"),
    ("LEVI",     2, "Sheni"),
    ("SHLISHI",  3, "Shlishi"),
    ("REVII",    4, "Revi'i"),
    ("CHAMISHI", 5, "Chamishi"),
    ("SHISHI",   6, "Shishi"),
    ("SHVII",    7, "Shevi'i"),
    ("MAFTIR",   8, "Maftir"),
]

# Haftarah/Megilla use R1, R2, … as consecutive sections (no aliyot)
_HAFTARAH_REFS = ["R1", "R2", "R3", "R4", "R5"]

# ── Reading types that are Megilla/non-Torah ──────────────────────────
_MEGILLA_TYPES = frozenset({
    "megilla", "ruth", "esther", "koheles", "eichah",
    "ruth-koheles-shirhashirim", "lamentations", "shirhashirim",
    "tehillim",
})


def _book_code(ref: str) -> str:
    """Extract 3-letter book code from a verse reference like 'JER1:1'."""
    if ref and ref[0].isdigit():
        return ref[:3].upper()
    return ref[:3].upper()


def _parse_verse_ref(ref: str) -> Tuple[int, int, int]:
    """Parse 'JER1:1' or 'NUM25:10' → (book_num, chapter, verse)."""
    code = _book_code(ref)
    rest = ref[len(code):]
    if ":" not in rest:
        raise ValueError(f"Invalid verse ref: {ref!r}")
    ch_str, v_str = rest.split(":", 1)
    book_num = _BOOK_INFO.get(code, (0, "Unknown"))[0]
    return book_num, int(ch_str), int(v_str)


def get_book_display_name(ref: str) -> str:
    """Return the human-readable book name for a verse reference."""
    code = _book_code(ref)
    return _BOOK_INFO.get(code, (0, "Unknown"))[1]


def _normalise_name(name: str) -> str:
    return " ".join(name.lower().split())


_PARSED_ROOTS: Dict[str, ET.Element] = {}


def _get_root(xml_path: str) -> ET.Element:
    if xml_path not in _PARSED_ROOTS:
        tree = ET.parse(xml_path)
        _PARSED_ROOTS[xml_path] = tree.getroot()
    return _PARSED_ROOTS[xml_path]


def _resolve_xml_path(xml_path: Optional[str]) -> Optional[str]:
    if xml_path is not None:
        return xml_path if os.path.isfile(xml_path) else None
    this_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(this_dir, "sedrot.xml"),
        os.path.join(this_dir, "..", "data", "sedrot.xml"),
        os.path.join(this_dir, "..", "assets", "sedrot.xml"),
        os.path.join(this_dir, "..", "sedrot.xml"),
        os.path.join(this_dir, "..", "..", "data", "sedrot.xml"),
        os.path.join(this_dir, "..", "..", "sedrot.xml"),
    ]
    for path in candidates:
        norm = os.path.normpath(path)
        if os.path.isfile(norm):
            return norm
    return None


def _strip_suffix(name: str) -> str:
    """Remove TropeTrainer UI suffixes like ': Shabbas'."""
    for suffix in (
        ": shabbas", ": weekday", ": shabbat", ": holiday",
        " shabbas", " weekday", " shabbat", " holiday",
    ):
        if name.endswith(suffix):
            return name[: -len(suffix)].strip()
    return name


def _find_reading(root: ET.Element, parsha_name: str) -> Optional[ET.Element]:
    """Find the <READING> element matching parsha_name (case-insensitive)."""
    target = _strip_suffix(_normalise_name(parsha_name))
    if not target:
        return None
    # Pass 1: exact match
    for reading in root.findall("READING"):
        xml_name = _normalise_name(reading.get("NAME", ""))
        if not xml_name:
            continue
        if xml_name == target:
            return reading
    # Pass 2: prefix match
    for reading in root.findall("READING"):
        xml_name = _normalise_name(reading.get("NAME", ""))
        if not xml_name:
            continue
        if xml_name.startswith(target) or target.startswith(xml_name):
            return reading
    return None


def _find_option_by_name(
    reading: ET.Element, option_name: str
) -> Optional[ET.Element]:
    """Find an OPTION or HAFTARAH element by its NAME attribute (case-insensitive).

    Searches both <OPTION> and <HAFTARAH> child elements, since Haftarah
    readings may be stored under either tag in sedrot.xml.
    """
    target = _normalise_name(option_name)
    all_children = reading.findall("OPTION") + reading.findall("HAFTARAH")
    # Pass 1: exact match
    for opt in all_children:
        if _normalise_name(opt.get("NAME", "")) == target:
            return opt
    # Pass 2: substring match (tolerate minor wording differences)
    for opt in all_children:
        xml_name = _normalise_name(opt.get("NAME", ""))
        if target in xml_name or xml_name in target:
            return opt
    return None


def _find_torah_option(
    reading: ET.Element,
    cycle: int,
    option_name: Optional[str] = None,
) -> Optional[ET.Element]:
    """Find the best Torah/HiHoliday OPTION for the given cycle.

    If *option_name* is provided, that specific named option is returned
    (irrespective of cycle).  Falls back to cycle-based selection if the
    named option is not found.
    """
    # Priority 0: named option explicitly requested
    if option_name:
        opt = _find_option_by_name(reading, option_name)
        if opt is not None and opt.get("TYPE", "").lower() in ("torah", "hiholiday"):
            return opt

    cycle_str = str(cycle)
    # Prefer exact cycle match with Torah type
    for opt in reading.findall("OPTION"):
        t = opt.get("TYPE", "").lower()
        if t in ("torah", "hiholiday") and opt.get("CYCLE", "") == cycle_str:
            return opt
    # Fallback: cycle 5 (holiday) or 0
    for fallback_cycle in ("5", "0"):
        for opt in reading.findall("OPTION"):
            t = opt.get("TYPE", "").lower()
            if t in ("torah", "hiholiday") and opt.get("CYCLE", "") == fallback_cycle:
                return opt
    # Any Torah option
    for opt in reading.findall("OPTION"):
        if opt.get("TYPE", "").lower() in ("torah", "hiholiday"):
            return opt
    return None


def _find_haftarah_option(
    reading: ET.Element,
    haftarah_name: Optional[str] = None,
    option_name: Optional[str] = None,
) -> Optional[ET.Element]:
    """Find the best Haftarah OPTION.

    Priority:
      1. Named option + TYPE=Haftarah (exact name match, searches all child tags)
      2. Named option + TYPE=Haftarah (substring match)
      3. Standard HAFTARAH tags first (avoid returning special overlay OPTIONs
         such as Shabbas Shekalim/Parah/Rosh-Chodesh that have TYPE=Haftarah)
      4. First HAFTARAH or OPTION element with TYPE=Haftarah (fallback)
    """
    all_children = reading.findall("OPTION") + reading.findall("HAFTARAH")
    haftarah_children = [
        c for c in all_children if c.get("TYPE", "").lower() == "haftarah"
    ]

    if option_name:
        target = _normalise_name(option_name)
        # Pass 1: exact name + TYPE=Haftarah
        for opt in haftarah_children:
            if _normalise_name(opt.get("NAME", "")) == target:
                return opt
        # Pass 2: substring name + TYPE=Haftarah
        for opt in haftarah_children:
            xml_name = _normalise_name(opt.get("NAME", ""))
            if target in xml_name or xml_name in target:
                return opt

    # No option_name (or not found): prefer <HAFTARAH> tag over <OPTION> tag
    # to avoid returning special-day overlays when the standard reading is wanted.
    for tag in ("HAFTARAH", "OPTION"):
        for opt in reading.findall(tag):
            if opt.get("TYPE", "").lower() == "haftarah":
                if haftarah_name is None:
                    return opt
                if haftarah_name.lower() in opt.get("NAME", "").lower():
                    return opt

    # Final fallback: any haftarah child
    return haftarah_children[0] if haftarah_children else None


def _find_megilla_option(
    reading: ET.Element,
    reading_type: str = "",
    option_name: Optional[str] = None,
) -> Optional[ET.Element]:
    """Find Megilla/Ruth/Esther/Koheles/Shir/Eichah/Tehillim reading option."""
    # Priority 0: named option explicitly requested
    if option_name:
        opt = _find_option_by_name(reading, option_name)
        if opt is not None and opt.get("TYPE", "").lower() in _MEGILLA_TYPES:
            return opt

    rt_lower = reading_type.lower()
    # First: try to match the exact reading_type
    for opt in reading.findall("OPTION"):
        if opt.get("TYPE", "").lower() == rt_lower and opt.get("R1"):
            return opt
    # Second: any megilla-type option
    for opt in reading.findall("OPTION"):
        if opt.get("TYPE", "").lower() in _MEGILLA_TYPES and opt.get("R1"):
            return opt
    return None


# ── Public API ────────────────────────────────────────────────────────

def get_aliyah_boundaries(
    parsha_name: str,
    cycle: int = 0,
    reading_type: str = "Torah",
    haftarah_name: Optional[str] = None,
    option_name: Optional[str] = None,
    xml_path: Optional[str] = None,
) -> Optional[Dict[Tuple[int, int], Tuple[int, str]]]:
    """Return aliyah/section start-verse boundaries from sedrot.xml.

    For Torah readings returns ``{(chapter, verse): (aliyah_num, name)}``.
    For Haftarah/Megilla returns a single entry marking the first verse.

    :param option_name: For holiday readings, the exact NAME of the specific
        sub-option (e.g. "Day 8 (Weekday)" for Pesach).  When provided this
        takes precedence over cycle-based selection.
    :return: Boundaries dict, or ``None`` if not found.
    """
    xml_path = _resolve_xml_path(xml_path)
    if not xml_path:
        return None
    try:
        root = _get_root(xml_path)
    except Exception:
        return None

    reading = _find_reading(root, parsha_name)
    if reading is None:
        return None

    rt = reading_type.lower()

    if rt == "haftarah":
        opt = _find_haftarah_option(reading, haftarah_name, option_name)
        if opt is None:
            return None
        return _extract_haftarah_boundaries(opt)

    if rt in _MEGILLA_TYPES:
        opt = _find_megilla_option(reading, reading_type, option_name)
        if opt is None:
            return None
        return _extract_haftarah_boundaries(opt)

    # Torah / HiHoliday / Maftir – use named option if supplied
    opt = _find_torah_option(reading, cycle, option_name)
    if opt is None:
        return None
    return _extract_torah_boundaries(opt)


def _extract_torah_boundaries(
    option: ET.Element,
) -> Dict[Tuple[int, int], Tuple[int, str]]:
    result: Dict[Tuple[int, int], Tuple[int, str]] = {}
    for attr_name, aliyah_num, aliyah_display in _ALIYAH_ATTRS:
        val = option.get(attr_name)
        if not val:
            continue
        start_ref = val.split("-")[0].strip()
        try:
            _, chapter, verse = _parse_verse_ref(start_ref)
            result[(chapter, verse)] = (aliyah_num, aliyah_display)
        except (ValueError, IndexError):
            continue
    return result


def _extract_haftarah_boundaries(
    option: ET.Element,
) -> Dict[Tuple[int, int], Tuple[int, str]]:
    """For Haftarah/Megilla: mark the start of the reading as section 1."""
    result: Dict[Tuple[int, int], Tuple[int, str]] = {}
    for r_attr in _HAFTARAH_REFS:
        val = option.get(r_attr)
        if not val:
            continue
        start_ref = val.split("-")[0].strip()
        try:
            _, chapter, verse = _parse_verse_ref(start_ref)
            if not result:  # only mark the very first ref
                result[(chapter, verse)] = (1, "Rishon")
        except (ValueError, IndexError):
            continue
    return result


def get_parsha_start(
    parsha_name: str,
    cycle: int = 0,
    reading_type: str = "Torah",
    haftarah_name: Optional[str] = None,
    option_name: Optional[str] = None,
    xml_path: Optional[str] = None,
) -> Optional[Tuple[int, int, int]]:
    """Return (book_num, chapter, verse) of the first verse of a reading.

    :param option_name: For holiday readings, the exact NAME of the specific
        sub-option (e.g. "Day 8 (Weekday)" for Pesach).
    :return: ``(book_num, chapter, verse)`` or ``None``.
    """
    xml_path = _resolve_xml_path(xml_path)
    if not xml_path:
        return None
    try:
        root = _get_root(xml_path)
    except Exception:
        return None

    reading = _find_reading(root, parsha_name)
    if reading is None:
        return None

    rt = reading_type.lower()

    if rt == "haftarah":
        opt = _find_haftarah_option(reading, haftarah_name, option_name)
        if opt is None:
            return None
        for r_attr in _HAFTARAH_REFS:
            val = opt.get(r_attr)
            if val:
                start_ref = val.split("-")[0].strip()
                try:
                    return _parse_verse_ref(start_ref)
                except (ValueError, IndexError):
                    continue
        return None

    if rt in _MEGILLA_TYPES:
        opt = _find_megilla_option(reading, reading_type, option_name)
        if opt is None:
            return None
        for r_attr in _HAFTARAH_REFS:
            val = opt.get(r_attr)
            if val:
                start_ref = val.split("-")[0].strip()
                try:
                    return _parse_verse_ref(start_ref)
                except (ValueError, IndexError):
                    continue
        return None

    # Torah / HiHoliday
    opt = _find_torah_option(reading, cycle, option_name)
    if opt is None:
        return None
    first_val = opt.get("KOHEN") or opt.get("R1")
    if not first_val:
        return None
    start_ref = first_val.split("-")[0].strip()
    try:
        return _parse_verse_ref(start_ref)
    except (ValueError, IndexError):
        return None


def get_book_name_for_reading(
    parsha_name: str,
    cycle: int = 0,
    reading_type: str = "Torah",
    haftarah_name: Optional[str] = None,
    option_name: Optional[str] = None,
    xml_path: Optional[str] = None,
) -> Optional[str]:
    """Return the human-readable book name for the first verse of a reading.

    e.g. "Bamidbar/Numbers", "Jeremiah", "Ruth", "I Samuel".

    :param option_name: For holiday readings, the specific sub-option name.
    :return: Display name string, or ``None`` if not found.
    """
    start = get_parsha_start(
        parsha_name,
        cycle=cycle,
        reading_type=reading_type,
        haftarah_name=haftarah_name,
        option_name=option_name,
        xml_path=xml_path,
    )
    if start is None:
        return None
    book_num = start[0]
    for code, (num, display) in _BOOK_INFO.items():
        if num == book_num:
            return display
    return None


def get_option_type(
    parsha_name: str,
    option_name: str,
    xml_path: Optional[str] = None,
) -> Optional[str]:
    """Return the TYPE of a named option within a reading.

    Useful to determine whether a holiday Torah list item is actually
    a Megilla (Esther, Ruth-Koheles-ShirHashirim, Eichah) or regular Torah.

    :return: TYPE string (e.g. "Torah", "HiHoliday", "Esther", "Eichah")
        or ``None`` if not found.
    """
    xml_path = _resolve_xml_path(xml_path)
    if not xml_path:
        return None
    try:
        root = _get_root(xml_path)
    except Exception:
        return None
    reading = _find_reading(root, parsha_name)
    if reading is None:
        return None
    opt = _find_option_by_name(reading, option_name)
    if opt is None:
        return None
    return opt.get("TYPE")

def get_haftarah_refs(
    parsha_name: str,
    option_name: Optional[str] = None,
    haftarah_name: Optional[str] = None,
    xml_path: Optional[str] = None,
) -> List[str]:
    """Return the verse-range references (R1, R2 …) for a Haftarah reading.

    When *option_name* is supplied the specific named sub-option is used
    (e.g. "Shabbas Chanukah" for Mikeitz).  Without it the default/first
    Haftarah option is returned.

    :return: List of reference strings like ["ZEC2:14-4:7"] or multiple
        entries when a Haftarah spans more than one range (R1, R2 …).
    """
    xml_path = _resolve_xml_path(xml_path)
    if not xml_path:
        return []
    try:
        root = _get_root(xml_path)
    except Exception:
        return []
    reading = _find_reading(root, parsha_name)
    if reading is None:
        return []
    opt = _find_haftarah_option(reading, haftarah_name, option_name)
    if opt is None:
        return []
    refs: List[str] = []
    for r_attr in _HAFTARAH_REFS:
        val = opt.get(r_attr)
        if val:
            refs.append(val.strip())
    return refs


def get_maftir_refs(
    parsha_name: str,
    option_name: Optional[str] = None,
    cycle: int = 0,
    xml_path: Optional[str] = None,
) -> List[str]:
    """Return the MAFTIR verse-range reference(s) for a Maftir reading.

    When *option_name* is supplied the specific named option is used
    (e.g. "Chanukah Day 6").  Falls back to cycle-based selection
    and finally to the first Maftir option.

    :return: List with one reference string (e.g. ["NUM7:42-7:47"]),
        or an empty list if nothing is found.
    """
    xml_path = _resolve_xml_path(xml_path)
    if not xml_path:
        return []
    try:
        root = _get_root(xml_path)
    except Exception:
        return []
    reading = _find_reading(root, parsha_name)
    if reading is None:
        return []

    all_maftir = reading.findall("OPTION")

    # Priority 1: named option
    if option_name:
        target = _normalise_name(option_name)
        for opt in all_maftir:
            if opt.get("TYPE", "").lower() == "maftir":
                if _normalise_name(opt.get("NAME", "")) == target:
                    ref = opt.get("MAFTIR") or opt.get("STDMAFTIR")
                    if ref:
                        return [ref.strip()]
        # substring match
        for opt in all_maftir:
            if opt.get("TYPE", "").lower() == "maftir":
                xml_name = _normalise_name(opt.get("NAME", ""))
                if target in xml_name or xml_name in target:
                    ref = opt.get("MAFTIR") or opt.get("STDMAFTIR")
                    if ref:
                        return [ref.strip()]

    # Priority 2: cycle match
    cycle_str = str(cycle)
    for opt in all_maftir:
        if (opt.get("TYPE", "").lower() == "maftir"
                and opt.get("CYCLE", "") == cycle_str
                and not opt.get("SPECIAL")):
            ref = opt.get("MAFTIR") or opt.get("STDMAFTIR")
            if ref:
                return [ref.strip()]

    # Priority 3: first Maftir with CYCLE=0 and no SPECIAL
    for opt in all_maftir:
        if (opt.get("TYPE", "").lower() == "maftir"
                and opt.get("CYCLE", "") in ("0", "")
                and not opt.get("SPECIAL")):
            ref = opt.get("MAFTIR") or opt.get("STDMAFTIR")
            if ref:
                return [ref.strip()]

    # Fallback: first Maftir option at all
    for opt in all_maftir:
        if opt.get("TYPE", "").lower() == "maftir":
            ref = opt.get("MAFTIR") or opt.get("STDMAFTIR")
            if ref:
                return [ref.strip()]

    return []
