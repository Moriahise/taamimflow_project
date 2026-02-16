"""Reference normalisation utilities.

This module provides helpers for converting TropeTrainer‑style
three‑letter book codes into the dotted notation used by Sefaria.
The ``normalize_ref`` function attempts to interpret strings of the
form ``GEN1:1-2:3`` or ``GEN1:1-GEN2:3`` and convert them into a
format Sefaria understands, such as ``Genesis.1.1-2.3``.  If the
pattern does not match, the original reference is returned
unchanged.

Only the codes required for Torah and Haftarah books are included.
Missing mappings will simply pass through the three‑letter code as
the book name.
"""

from __future__ import annotations

import re
from typing import Dict

# Map TropeTrainer three‑letter codes to Sefaria book names.
BOOK_MAP: Dict[str, str] = {
    "GEN": "Genesis",
    "EXO": "Exodus",
    "LEV": "Leviticus",
    "NUM": "Numbers",
    "DEU": "Deuteronomy",
    "JOS": "Joshua",
    "JDG": "Judges",
    "1SA": "I Samuel",
    "2SA": "II Samuel",
    "1KI": "I Kings",
    "2KI": "II Kings",
    "ISA": "Isaiah",
    "JER": "Jeremiah",
    "EZE": "Ezekiel",
    "HOS": "Hosea",
    "JOE": "Joel",
    "AMO": "Amos",
    "OBA": "Obadiah",
    "JON": "Jonah",
    "MIC": "Micah",
    "NAH": "Nahum",
    "HAB": "Habakkuk",
    "ZEP": "Zephaniah",
    "HAG": "Haggai",
    "ZEC": "Zechariah",
    "MAL": "Malachi",
    "PSA": "Psalms",
    "PRO": "Proverbs",
    "JOB": "Job",
    "SNG": "Song of Songs",
    "RUT": "Ruth",
    "LAM": "Lamentations",
    "ECC": "Ecclesiastes",
    "EST": "Esther",
    "DAN": "Daniel",
    "EZR": "Ezra",
    "NEH": "Nehemiah",
    "1CH": "I Chronicles",
    "2CH": "II Chronicles",
}


def normalize_ref(ref: str) -> str:
    """Normalise TropeTrainer references to Sefaria dotted notation.

    If the string matches the pattern ``ABCc:v-ABCc:v``, where ABC is
    a three‑letter book code, c is a chapter number and v a verse
    number, it is converted.  If only one book code is present after
    the hyphen, the same book is assumed.  If the pattern does not
    match, the original string is returned unchanged.
    """
    if not ref:
        return ref
    s = ref.strip().replace(" ", "")
    # Example: GEN1:1-2:3 or GEN1:1-GEN2:3
    pattern = re.compile(
        r"^([A-Z0-9]{3})(\d+):(\d+)(?:-([A-Z0-9]{3})?(\d+):(\d+))?$"
    )
    m = pattern.match(s)
    if not m:
        return ref
    code1, ch1, v1, code2, ch2, v2 = m.groups()
    book1 = BOOK_MAP.get(code1, code1)
    # Determine second book; if not provided, same as first
    if ch2 and v2:
        # Use code2 if given, else fallback to code1
        book2 = BOOK_MAP.get(code2, code2) if code2 else book1
        if book2 == book1:
            # same book: dotted range within the book
            return f"{book1}.{ch1}.{v1}-{ch2}.{v2}"
        # two different books
        return f"{book1}.{ch1}.{v1}-{book2}.{ch2}.{v2}"
    # only a single point reference
    return f"{book1}.{ch1}.{v1}"