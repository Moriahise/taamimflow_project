"""Trope (cantillation) parser for Hebrew biblical text.

This module analyses Hebrew text containing cantillation marks
(te'amim) and assigns each word to a *trope group* which determines
the display colour in the TropeTrainer UI.  The grouping follows the
traditional hierarchy of disjunctive and conjunctive accents used in
Torah reading.

The parser produces a list of ``Token`` named-tuples containing the
original word, the identified trope group and a representative
symbol character for display in symbol-colour mode.

Unicode ranges used:
    Trope marks (te'amim): U+0591 – U+05AF
    Vowels (nikkud):       U+05B0 – U+05BD
    Hebrew letters:        U+05D0 – U+05EA
    Sof Pasuq:             U+05C3
    Maqaf:                 U+05BE
    Paseq:                 U+05C0
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ── Unicode code-points for individual trope marks ──────────────────

# Disjunctive accents ("melakhim" / rulers)
ETNACHTA       = '\u0591'
SEGOL_ACCENT   = '\u0592'   # Segolta
SHALSHELET     = '\u0593'
ZAQEF_QATAN    = '\u0594'
ZAQEF_GADOL    = '\u0595'
TIPEHA         = '\u0596'   # also called Tarcha
REVIA          = '\u0597'
ZARQA          = '\u0598'
PASHTA         = '\u0599'
YETIV          = '\u059A'
TEVIR          = '\u059B'
GERESH         = '\u059C'
GERESH_MUQDAM  = '\u059D'
GERSHAYIM      = '\u059E'
QARNEY_PARA    = '\u059F'
TELISHA_GEDOLA = '\u05A0'
PAZER          = '\u05A1'
ATNAH_HAFUKH   = '\u05A2'

# Conjunctive accents ("meshartim" / servants)
MUNACH         = '\u05A3'
MAHPAKH        = '\u05A4'
MERKHA         = '\u05A5'
MERKHA_KEFULA  = '\u05A6'
DARGA          = '\u05A7'
QADMA          = '\u05A8'
TELISHA_QETANA = '\u05A9'
YERAH_BEN_YOMO = '\u05AA'   # Galgal
OLE            = '\u05AB'
ILUY           = '\u05AC'
DEHI           = '\u05AD'
ZINOR          = '\u05AE'

# Special marks
SOF_PASUQ      = '\u05C3'
SILLUQ         = '\u05BD'   # Meteg / Silluq share the same codepoint
MAQAF          = '\u05BE'
PASEQ          = '\u05C0'


# ── Trope group definitions ─────────────────────────────────────────
# Each group gets a name, a colour and a symbol.  The hierarchy
# follows the traditional classification of Torah cantillation.

@dataclass(frozen=True)
class TropeGroup:
    """Metadata for a trope group."""
    name: str
    color: str        # hex colour for background
    symbol: str       # display symbol for symbol-colour mode
    rank: int         # hierarchical rank (lower = stronger disjunctive)


# The groups mirror the original TropeTrainer colour scheme visible
# in the user's screenshot.
GROUPS = {
    "Sof Pasuk":      TropeGroup("Sof Pasuk",      "#00FFFF", "׃", 0),   # Cyan
    "Etnachta":        TropeGroup("Etnachta",        "#FF00FF", "֑", 1),   # Magenta
    "Segol":           TropeGroup("Segol",           "#FFFF00", "֒", 2),   # Yellow
    "Zakef":           TropeGroup("Zakef",           "#FFFF00", "֔", 2),   # Yellow (same level)
    "Zakef Gadol":     TropeGroup("Zakef Gadol",     "#FFFF00", "֕", 2),   # Yellow
    "Shalshelet":      TropeGroup("Shalshelet",      "#FFFF00", "֓", 2),   # Yellow
    "Tipeha":          TropeGroup("Tipeha",          "#FFFFFF", "֖", 3),   # White
    "Revia":           TropeGroup("Revia",           "#FFFFFF", "֗", 3),   # White
    "Tevir":           TropeGroup("Tevir",           "#FFFFFF", "֛", 3),   # White
    "Pashta":          TropeGroup("Pashta",          "#FFFFFF", "֙", 3),   # White
    "Yetiv":           TropeGroup("Yetiv",           "#FFFFFF", "֚", 3),   # White
    "Zarqa":           TropeGroup("Zarqa",           "#FFFFFF", "֘", 3),   # White
    "Geresh":          TropeGroup("Geresh",          "#FFFFFF", "֜", 3),   # White
    "Gershayim":       TropeGroup("Gershayim",       "#FFFFFF", "֞", 3),   # White
    "Pazer":           TropeGroup("Pazer",           "#FFFFFF", "֡", 3),   # White
    "Qarney Para":     TropeGroup("Qarney Para",     "#FFFFFF", "֟", 3),   # White
    "Telisha Gedola":  TropeGroup("Telisha Gedola",  "#FFFFFF", "֠", 3),   # White
    # Conjunctive accents (servants) – coloured by their master
    "Munach":          TropeGroup("Munach",          "#90EE90", "֣", 4),   # Light green
    "Mahpakh":         TropeGroup("Mahpakh",         "#90EE90", "֤", 4),   # Light green
    "Merkha":          TropeGroup("Merkha",          "#90EE90", "֥", 4),   # Light green
    "Merkha Kefula":   TropeGroup("Merkha Kefula",   "#90EE90", "֦", 4),   # Light green
    "Darga":           TropeGroup("Darga",           "#90EE90", "֧", 4),   # Light green
    "Qadma":           TropeGroup("Qadma",           "#90EE90", "֨", 4),   # Light green
    "Telisha Qetana":  TropeGroup("Telisha Qetana",  "#90EE90", "֩", 4),   # Light green
    "Yerah Ben Yomo":  TropeGroup("Yerah Ben Yomo",  "#90EE90", "֪", 4),   # Light green
    "Ole":             TropeGroup("Ole",             "#90EE90", "֫", 4),
    "Iluy":            TropeGroup("Iluy",            "#90EE90", "֬", 4),
    "Dehi":            TropeGroup("Dehi",            "#90EE90", "֭", 4),
    "Zinor":           TropeGroup("Zinor",           "#90EE90", "֮", 4),
    # Fallback
    "Unknown":         TropeGroup("Unknown",         "#D3D3D3", "?", 5),   # Light grey
}


# Map Unicode code-point → group name
_MARK_TO_GROUP: Dict[str, str] = {
    ETNACHTA:       "Etnachta",
    SEGOL_ACCENT:   "Segol",
    SHALSHELET:     "Shalshelet",
    ZAQEF_QATAN:    "Zakef",
    ZAQEF_GADOL:    "Zakef Gadol",
    TIPEHA:         "Tipeha",
    REVIA:          "Revia",
    ZARQA:          "Zarqa",
    PASHTA:         "Pashta",
    YETIV:          "Yetiv",
    TEVIR:          "Tevir",
    GERESH:         "Geresh",
    GERESH_MUQDAM:  "Geresh",
    GERSHAYIM:      "Gershayim",
    QARNEY_PARA:    "Qarney Para",
    TELISHA_GEDOLA: "Telisha Gedola",
    PAZER:          "Pazer",
    ATNAH_HAFUKH:   "Etnachta",      # Rare variant treated as Etnachta
    MUNACH:         "Munach",
    MAHPAKH:        "Mahpakh",
    MERKHA:         "Merkha",
    MERKHA_KEFULA:  "Merkha Kefula",
    DARGA:          "Darga",
    QADMA:          "Qadma",
    TELISHA_QETANA: "Telisha Qetana",
    YERAH_BEN_YOMO: "Yerah Ben Yomo",
    OLE:            "Ole",
    ILUY:           "Iluy",
    DEHI:           "Dehi",
    ZINOR:          "Zinor",
}


# ── Priority of disjunctive accents ─────────────────────────────────
# When a word carries multiple trope marks (rare but possible), the
# strongest disjunctive wins.  Lower rank = higher priority.

_DISJUNCTIVE_MARKS = {
    ETNACHTA, SEGOL_ACCENT, SHALSHELET, ZAQEF_QATAN, ZAQEF_GADOL,
    TIPEHA, REVIA, ZARQA, PASHTA, YETIV, TEVIR, GERESH,
    GERESH_MUQDAM, GERSHAYIM, QARNEY_PARA, TELISHA_GEDOLA, PAZER,
    ATNAH_HAFUKH,
}


@dataclass
class Token:
    """A single parsed word with its trope information."""
    word: str
    group_name: str
    symbol: str
    color: str
    trope_marks: List[str]       # list of trope mark names found
    verse_end: bool = False      # True if Sof Pasuq follows this word


def _extract_trope_marks(word: str) -> List[str]:
    """Return the trope mark characters present in a word."""
    marks: List[str] = []
    for ch in word:
        if ch in _MARK_TO_GROUP:
            marks.append(ch)
    return marks


def _classify_word(word: str) -> Tuple[str, str, str, List[str], bool]:
    """Determine the trope group for a single word.

    Returns (group_name, symbol, color, mark_names, is_verse_end).
    """
    # Check for Sof Pasuq
    verse_end = SOF_PASUQ in word or word.endswith(':')

    marks = _extract_trope_marks(word)
    mark_names = [_MARK_TO_GROUP.get(m, "Unknown") for m in marks]

    if not marks and verse_end:
        grp = GROUPS["Sof Pasuk"]
        return grp.name, grp.symbol, grp.color, ["Sof Pasuk"], True

    if not marks:
        # No trope marks at all – possibly a maqaf-joined prefix or
        # a word whose mark was lost.  Use Unknown.
        grp = GROUPS["Unknown"]
        return grp.name, grp.symbol, grp.color, [], verse_end

    # Find the strongest (lowest rank) disjunctive mark
    best_group_name: Optional[str] = None
    best_rank = 999

    for m in marks:
        gname = _MARK_TO_GROUP.get(m, "Unknown")
        grp = GROUPS.get(gname, GROUPS["Unknown"])
        # Prefer disjunctive over conjunctive
        if m in _DISJUNCTIVE_MARKS:
            if grp.rank < best_rank:
                best_rank = grp.rank
                best_group_name = gname
        elif best_group_name is None:
            best_group_name = gname

    if best_group_name is None:
        best_group_name = mark_names[0] if mark_names else "Unknown"

    grp = GROUPS.get(best_group_name, GROUPS["Unknown"])

    # Override with Sof Pasuk if verse end
    if verse_end and grp.rank > 0:
        sof = GROUPS["Sof Pasuk"]
        return sof.name, sof.symbol, sof.color, mark_names, True

    return grp.name, grp.symbol, grp.color, mark_names, verse_end


def tokenise(text: str) -> List[Token]:
    """Parse Hebrew text into a list of coloured tokens.

    The input ``text`` should contain Hebrew with cantillation marks
    (e.g. from Sefaria with tropes).  The parser splits on whitespace,
    identifies the dominant trope mark on each word and assigns a
    trope group determining its display colour.

    :param text: Hebrew text with cantillation marks.
    :return: List of :class:`Token` objects.
    """
    if not text:
        return []

    tokens: List[Token] = []
    # Split on whitespace.  Maqaf-joined words stay together.
    raw_words = text.split()

    for raw in raw_words:
        if not raw.strip():
            continue
        group_name, symbol, color, mark_names, verse_end = _classify_word(raw)
        tokens.append(Token(
            word=raw,
            group_name=group_name,
            symbol=symbol,
            color=color,
            trope_marks=mark_names,
            verse_end=verse_end,
        ))

    return tokens


def get_trope_group(group_name: str) -> TropeGroup:
    """Look up a trope group by name.  Returns 'Unknown' for missing names."""
    return GROUPS.get(group_name, GROUPS["Unknown"])


def get_all_group_colors() -> Dict[str, str]:
    """Return a mapping of group name → hex colour for all groups."""
    return {name: grp.color for name, grp in GROUPS.items()}
