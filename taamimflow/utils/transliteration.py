"""Hebrew to Latin transliteration for cantillation display.

This module converts Hebrew biblical text (with nikkud/vowels) into
Latin-script pronunciation syllables.  The output is intended for
display beneath musical notation, matching the original TropeTrainer
behaviour where each word is broken into syllables shown under the
corresponding notes.

The transliteration follows Sephardi pronunciation by default but
can be switched to Ashkenazi or other traditions by selecting a
different mapping table.

Example::

    >>> transliterate_word("פָּקַד")
    ['pah', 'kahd']

    >>> transliterate_word("וַיִּמָּל")
    ['vah', 'yim', 'mahl']
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import unicodedata


# ── Unicode constants ───────────────────────────────────────────────

# Dagesh / Mapiq
DAGESH = '\u05BC'
# Shin / Sin dots
SHIN_DOT = '\u05C1'
SIN_DOT = '\u05C2'
# Maqaf (hyphen)
MAQAF = '\u05BE'
# Sof Pasuq
SOF_PASUQ = '\u05C3'
# Meteg
METEG = '\u05BD'
# Paseq
PASEQ = '\u05C0'

# Vowels
SHEVA     = '\u05B0'
HATAF_SEG = '\u05B1'
HATAF_PAT = '\u05B2'
HATAF_QAM = '\u05B3'
HIRIQ     = '\u05B4'
TSERE     = '\u05B5'
SEGOL_V   = '\u05B6'
PATACH    = '\u05B7'
QAMATS    = '\u05B8'
HOLAM     = '\u05B9'
HOLAM_VAV = '\u05BA'
QUBUTS    = '\u05BB'

# Consonant range
ALEF  = '\u05D0'
BET   = '\u05D1'
GIMEL = '\u05D2'
DALET = '\u05D3'
HE    = '\u05D4'
VAV   = '\u05D5'
ZAYIN = '\u05D6'
CHET  = '\u05D7'
TET   = '\u05D8'
YOD   = '\u05D9'
FINAL_KAF = '\u05DA'
KAF   = '\u05DB'
LAMED = '\u05DC'
FINAL_MEM = '\u05DD'
MEM   = '\u05DE'
FINAL_NUN = '\u05DF'
NUN   = '\u05E0'
SAMEKH = '\u05E1'
AYIN  = '\u05E2'
FINAL_PE = '\u05E3'
PE    = '\u05E4'
FINAL_TSADE = '\u05E5'
TSADE = '\u05E6'
QOF   = '\u05E7'
RESH  = '\u05E8'
SHIN  = '\u05E9'
TAV   = '\u05EA'

ALL_VOWELS = {SHEVA, HATAF_SEG, HATAF_PAT, HATAF_QAM, HIRIQ,
              TSERE, SEGOL_V, PATACH, QAMATS, HOLAM, HOLAM_VAV, QUBUTS}

TROPE_RANGE = range(0x0591, 0x05B0)

# Letters that change pronunciation with dagesh (begadkefat)
BEGADKEFAT = {BET, GIMEL, DALET, KAF, FINAL_KAF, PE, FINAL_PE, TAV}


# ── Pronunciation tables ────────────────────────────────────────────

class PronunciationTable:
    """Holds consonant and vowel mappings for a pronunciation tradition."""

    def __init__(
        self,
        name: str,
        consonants_hard: Dict[str, str],
        consonants_soft: Dict[str, str],
        vowels: Dict[str, str],
        qamats_as_o: bool = False,
    ):
        self.name = name
        self.consonants_hard = consonants_hard  # with dagesh
        self.consonants_soft = consonants_soft   # without dagesh
        self.vowels = vowels
        self.qamats_as_o = qamats_as_o


# Common consonant base (shared between traditions)
_CONSONANTS_BASE_HARD: Dict[str, str] = {
    ALEF: "",    BET: "b",     GIMEL: "g",    DALET: "d",
    HE: "h",    VAV: "v",     ZAYIN: "z",    CHET: "ch",
    TET: "t",   YOD: "y",     KAF: "k",      FINAL_KAF: "k",
    LAMED: "l", MEM: "m",     FINAL_MEM: "m", NUN: "n",
    FINAL_NUN: "n", SAMEKH: "s", AYIN: "",    PE: "p",
    FINAL_PE: "p",  TSADE: "ts", FINAL_TSADE: "ts",
    QOF: "k",   RESH: "r",    TAV: "t",
}

_CONSONANTS_BASE_SOFT: Dict[str, str] = {
    ALEF: "",    BET: "v",     GIMEL: "g",    DALET: "d",
    HE: "h",    VAV: "v",     ZAYIN: "z",    CHET: "ch",
    TET: "t",   YOD: "y",     KAF: "ch",     FINAL_KAF: "ch",
    LAMED: "l", MEM: "m",     FINAL_MEM: "m", NUN: "n",
    FINAL_NUN: "n", SAMEKH: "s", AYIN: "",    PE: "f",
    FINAL_PE: "f",  TSADE: "ts", FINAL_TSADE: "ts",
    QOF: "k",   RESH: "r",    TAV: "t",
}

# Sephardi vowels
_VOWELS_SEPHARDI: Dict[str, str] = {
    SHEVA:     "",       # silent or very short
    HATAF_SEG: "eh",
    HATAF_PAT: "ah",
    HATAF_QAM: "o",
    HIRIQ:     "ee",
    TSERE:     "ey",
    SEGOL_V:   "eh",
    PATACH:    "ah",
    QAMATS:    "ah",
    HOLAM:     "o",
    HOLAM_VAV: "o",
    QUBUTS:    "oo",
}

# Ashkenazi vowels
_VOWELS_ASHKENAZI: Dict[str, str] = {
    SHEVA:     "",
    HATAF_SEG: "eh",
    HATAF_PAT: "ah",
    HATAF_QAM: "o",
    HIRIQ:     "ee",
    TSERE:     "ey",
    SEGOL_V:   "eh",
    PATACH:    "ah",
    QAMATS:    "o",     # Key difference: Qamats → 'o' in Ashkenazi
    HOLAM:     "oy",
    HOLAM_VAV: "oy",
    QUBUTS:    "oo",
}

# Ashkenazi soft consonant overrides
_CONSONANTS_SOFT_ASHKENAZI = dict(_CONSONANTS_BASE_SOFT)
_CONSONANTS_SOFT_ASHKENAZI[TAV] = "s"  # Tav without dagesh = 's' in Ashkenazi


SEPHARDI = PronunciationTable(
    name="Sephardi",
    consonants_hard=_CONSONANTS_BASE_HARD,
    consonants_soft=_CONSONANTS_BASE_SOFT,
    vowels=_VOWELS_SEPHARDI,
)

ASHKENAZI = PronunciationTable(
    name="Ashkenazi",
    consonants_hard=_CONSONANTS_BASE_HARD,
    consonants_soft=_CONSONANTS_SOFT_ASHKENAZI,
    vowels=_VOWELS_ASHKENAZI,
    qamats_as_o=True,
)

TABLES = {"Sephardi": SEPHARDI, "Ashkenazi": ASHKENAZI}


# ── Parsing helpers ─────────────────────────────────────────────────

def _is_hebrew_consonant(ch: str) -> bool:
    return '\u05D0' <= ch <= '\u05EA'


def _is_vowel(ch: str) -> bool:
    return ch in ALL_VOWELS


def _is_trope(ch: str) -> bool:
    return 0x0591 <= ord(ch) <= 0x05AF


def _is_special(ch: str) -> bool:
    return ch in {DAGESH, SHIN_DOT, SIN_DOT, METEG, MAQAF, SOF_PASUQ, PASEQ}


# ── Main transliteration functions ──────────────────────────────────

def _parse_characters(word: str) -> List[dict]:
    """Parse a Hebrew word into a list of character records.

    Each record has: consonant, has_dagesh, has_shin_dot, has_sin_dot,
    vowel, is_final.
    """
    # Strip cantillation marks and maqaf/sof pasuq
    chars = []
    for ch in word:
        if _is_trope(ch):
            continue
        if ch in {MAQAF, SOF_PASUQ, PASEQ}:
            continue
        chars.append(ch)

    records: List[dict] = []
    i = 0
    while i < len(chars):
        ch = chars[i]
        if _is_hebrew_consonant(ch):
            rec = {
                "consonant": ch,
                "has_dagesh": False,
                "has_shin_dot": False,
                "has_sin_dot": False,
                "vowel": None,
                "is_final": False,
            }
            # Consume following modifiers and vowel
            j = i + 1
            while j < len(chars):
                nch = chars[j]
                if nch == DAGESH:
                    rec["has_dagesh"] = True
                elif nch == SHIN_DOT:
                    rec["has_shin_dot"] = True
                elif nch == SIN_DOT:
                    rec["has_sin_dot"] = True
                elif nch == METEG:
                    pass  # ignore meteg
                elif _is_vowel(nch):
                    rec["vowel"] = nch
                elif _is_hebrew_consonant(nch):
                    break  # next consonant
                else:
                    pass  # skip unknown
                j += 1
            # Check if this is the last consonant
            remaining_consonants = sum(
                1 for k in range(j, len(chars)) if _is_hebrew_consonant(chars[k])
            )
            if remaining_consonants == 0:
                rec["is_final"] = True
            records.append(rec)
            i = j
        else:
            i += 1

    return records


def transliterate_word(
    word: str,
    table: PronunciationTable | None = None,
) -> List[str]:
    """Convert a Hebrew word to a list of pronunciation syllables.

    Each syllable is a string like ``'pah'``, ``'kahd'``, etc.
    The syllables are suitable for display beneath musical notation
    notes.

    :param word: Hebrew word with nikkud (vowel points).
    :param table: Pronunciation table to use (defaults to Sephardi).
    :return: List of syllable strings.
    """
    if table is None:
        table = SEPHARDI

    records = _parse_characters(word)
    if not records:
        return []

    syllables: List[str] = []
    current_syllable = ""

    for idx, rec in enumerate(records):
        con = rec["consonant"]
        has_dagesh = rec["has_dagesh"]
        vowel = rec["vowel"]
        is_final = rec["is_final"]

        # ── Determine consonant sound ──
        # Handle Shin/Sin
        if con == SHIN:
            if rec["has_sin_dot"]:
                con_sound = "s"
            else:
                con_sound = "sh"  # default to shin
        elif con in BEGADKEFAT and has_dagesh:
            con_sound = table.consonants_hard.get(con, "")
        elif con in BEGADKEFAT:
            con_sound = table.consonants_soft.get(con, "")
        else:
            con_sound = table.consonants_hard.get(con, "")

        # Vav as vowel letter (shuruk: vav + dagesh without other vowel)
        if con == VAV and has_dagesh and vowel is None:
            # Shuruk - append 'oo' to current syllable
            current_syllable += "oo"
            continue

        # Vav with holam (holam male)
        if con == VAV and vowel == HOLAM:
            current_syllable += "o"
            continue

        # Yod as vowel (hiriq male: yod after hiriq)
        # This is handled implicitly since the yod following a hiriq
        # just becomes 'y' + no vowel → absorbed into syllable

        # ── Determine vowel sound ──
        vowel_sound = ""
        if vowel is not None:
            vowel_sound = table.vowels.get(vowel, "")

        # Sheva: decide if it starts a new syllable or closes one
        if vowel == SHEVA:
            if idx == 0:
                # Word-initial sheva is mobile → short 'e'
                vowel_sound = "e"
            elif has_dagesh and con in BEGADKEFAT and idx > 0:
                # Dagesh after sheva usually means sheva na
                vowel_sound = "e"
            else:
                # Sheva nach (silent) → close the syllable
                if current_syllable:
                    current_syllable += con_sound
                    syllables.append(current_syllable)
                    current_syllable = ""
                    continue
                else:
                    current_syllable = con_sound
                    continue

        # He at end of word without mappiq is silent
        if con == HE and is_final and not has_dagesh and vowel is None:
            # Silent He - just close
            if current_syllable:
                syllables.append(current_syllable)
                current_syllable = ""
            continue

        # Alef/Ayin at start can be silent
        if con in (ALEF, AYIN) and not con_sound:
            # Silent letter, just add vowel
            if vowel_sound:
                current_syllable += vowel_sound
                if is_final:
                    syllables.append(current_syllable)
                    current_syllable = ""
            continue

        # ── Build syllable ──
        # If we have a vowel, this consonant+vowel forms part of a syllable
        if vowel_sound:
            current_syllable += con_sound + vowel_sound
            # Check if next consonant has no vowel (closed syllable)
            if idx + 1 < len(records):
                next_rec = records[idx + 1]
                next_vowel = next_rec["vowel"]
                next_is_sheva_nach = (
                    next_vowel == SHEVA
                    and not next_rec["has_dagesh"]
                    and (idx + 1) > 0
                    and not next_rec["is_final"]
                )
                # If the next char has a vowel, emit current syllable
                if next_vowel and next_vowel != SHEVA:
                    syllables.append(current_syllable)
                    current_syllable = ""
            else:
                # Last consonant
                syllables.append(current_syllable)
                current_syllable = ""
        else:
            # No vowel → this consonant closes the previous syllable
            current_syllable += con_sound
            if is_final and current_syllable:
                syllables.append(current_syllable)
                current_syllable = ""

    # Flush remaining
    if current_syllable:
        syllables.append(current_syllable)

    # Clean up: remove empty syllables, strip whitespace
    syllables = [s.strip() for s in syllables if s.strip()]

    return syllables


def transliterate_phrase(
    text: str,
    table: PronunciationTable | None = None,
) -> str:
    """Transliterate a Hebrew phrase into Latin script.

    Words are separated by spaces.  Within each word, syllables are
    joined with hyphens (for display alignment purposes, use
    :func:`transliterate_word` instead).

    :param text: Hebrew text with nikkud.
    :param table: Pronunciation table.
    :return: Transliterated string.
    """
    words = text.replace(MAQAF, " ").replace(SOF_PASUQ, "").split()
    result = []
    for w in words:
        syls = transliterate_word(w, table)
        result.append(" ".join(syls))
    return "  ".join(result)


def get_table(name: str) -> PronunciationTable:
    """Get a pronunciation table by name."""
    return TABLES.get(name, SEPHARDI)
