"""Hebrew text utilities.

Functions in this module operate on Unicode Hebrew strings,
particularly those containing cantillation marks (te'amim) and
vowels (nikkud).  They rely on Python's :mod:`unicodedata` to
identify combining characters and remove them.  If you require
fine‑grained control over which diacritics are retained (for
example, remove vowels but keep tropes), consider implementing
custom filters here.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List


HEBREW_LETTER_RANGE = (0x0590, 0x05FF)
COMBINING_RANGE = (0x0591, 0x05C7)


def is_hebrew_letter(ch: str) -> bool:
    """Return True if the character is a Hebrew base letter (not a mark)."""
    cp = ord(ch)
    return 0x05D0 <= cp <= 0x05EA or cp == 0x05F3 or cp == 0x05F4


def strip_cantillation(text: str, *, remove_vowels: bool = True, remove_tropes: bool = True) -> str:
    """Remove Hebrew vowel points (nikkud) and trope marks (te'amim).

    :param text: String containing Hebrew text with diacritics.
    :param remove_vowels: Whether to remove vowel points (U+05B0–U+05BD).
    :param remove_tropes: Whether to remove trope marks (U+0591–U+05AF).
    :return: Normalised string without the selected combining marks.
    """
    result_chars: List[str] = []
    for ch in text:
        # Keep all non-Hebrew characters
        if not (0x0590 <= ord(ch) <= 0x05FF):
            result_chars.append(ch)
            continue
        if unicodedata.combining(ch):
            # Diacritics start at 0x0591 (tropes) and include vowels up to 0x05BD
            code = ord(ch)
            if remove_tropes and 0x0591 <= code <= 0x05AF:
                continue
            if remove_vowels and 0x05B0 <= code <= 0x05BD:
                continue
        result_chars.append(ch)
    return "".join(result_chars)


def split_words(text: str) -> List[str]:
    """Split Hebrew text into words using whitespace and punctuation.

    Hebrew uses several punctuation marks inside the range U+05BE–U+05C3.
    This simple splitter uses a regex to break on whitespace and these
    punctuation characters.  It is not aware of context or special
    punctuation used in modern Hebrew (e.g. maqaf).  For advanced
    splitting, consider using PyArabic or other morphological tools.
    """
    # Remove maqaf (U+05BE) and sof pasuq (U+05C3) by replacing them with spaces
    cleaned = re.sub("[\u05BE\u05C3]", " ", text)
    return [word for word in re.split(r"\s+", cleaned) if word]