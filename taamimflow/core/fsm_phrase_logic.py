"""
Finite-State Phrase Logic for Trope Sequencing
=============================================

FIX V10: Import von ``milestone9_plus`` durch korrekten relativen
Import aus ``taamimflow.core.cantillation`` ersetzt (Fix P5).
Fallback-Definition von ``TokenFull`` verwendet ``word`` statt ``text``
damit sie mit dem echten ``TokenFull`` aus ``cantillation.py`` kompatibel ist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Dict, Optional

# Fix P5: Relativer Import statt milestone9_plus
try:
    from .cantillation import TokenFull  # type: ignore
except ImportError:
    try:
        # Absoluter Import als Fallback
        from taamimflow.core.cantillation import TokenFull  # type: ignore
    except ImportError:
        # Lokale Fallback-Definition – nutzt 'word' wie das echte TokenFull
        @dataclass
        class TokenFull:  # type: ignore[no-redef]
            word: str
            group_name: str = "Unknown"
            symbol: str = "?"
            color: str = "#D3D3D3"
            trope_groups: List[str] = field(default_factory=list)
            verse_end: bool = False
            notes: Optional[List[object]] = None
            flags: Dict[str, bool] = field(default_factory=dict)
            chapter_start: bool = False
            chapter_end: bool = False
            aliyah_start: bool = False
            aliyah_end: bool = False
            attributes: List[str] = field(default_factory=list)
            debug_info: Optional[str] = None


class PhraseFSM:
    """FSM zur Bestimmung von Kapitel-, Aliyah- und Phrasen-Flags.

    Berechnet zusätzliche Kontext-Flags für eine Sequenz von Tokens.
    Diese dienen als Vorverarbeitungsstufe für den Decision-Tree-Matcher.

    Heuristiken:
    * ``VERSE_END`` – am Ende eines Verses (``verse_end=True``)
    * ``CHAPTER_END`` – wenn Token mit ``chapter_end=True`` markiert ist
    * ``ALIYAH_START`` / ``ALIYAH_END`` – nach ``verses_per_aliyah`` Versen
    """

    def __init__(self, verses_per_aliyah: int = 7) -> None:
        self.chapter_counter = 1
        self.verse_counter = 0
        self.verses_per_aliyah = verses_per_aliyah
        self.aliya_counter = 1

    def annotate(self, tokens: Iterable[TokenFull]) -> List[TokenFull]:
        """Füge Kontext-Flags für Kapitel-, Aliyah- und Versgrenzen hinzu.

        :param tokens: Sequenz von ``TokenFull``.
        :return: Liste neuer ``TokenFull`` mit erweiterten Flags.
        """
        enhanced: List[TokenFull] = []
        for tok in tokens:
            # Kopiere relevante Attribute in ein neues Token-Dict
            # (kompatibel mit echtem und Fallback-TokenFull)
            new_flags = dict(getattr(tok, 'flags', {}))

            # Versende
            if tok.verse_end:
                new_flags['VERSE_END'] = True
                self.verse_counter += 1
            else:
                new_flags['VERSE_END'] = False

            # Kapitelende
            if getattr(tok, 'chapter_end', False):
                new_flags['CHAPTER_END'] = True
                self.chapter_counter += 1
                self.verse_counter = 0
            else:
                new_flags['CHAPTER_END'] = False

            # Aliyah-Logik
            if self.verse_counter == 1 and not new_flags.get('CHAPTER_END'):
                new_flags['ALIYAH_START'] = True
                if self.aliya_counter > 1 and enhanced:
                    prev_flags = getattr(enhanced[-1], 'flags', {})
                    prev_flags['ALIYAH_END'] = True
                self.aliya_counter += 1
            else:
                new_flags['ALIYAH_START'] = False

            if self.verse_counter == self.verses_per_aliyah:
                new_flags['ALIYAH_END'] = True
                self.verse_counter = 0
            else:
                new_flags.setdefault('ALIYAH_END', False)

            # Schreibe Flags zurück auf das Token (in-place, kein neues Objekt nötig)
            if hasattr(tok, 'flags'):
                tok.flags = new_flags
            enhanced.append(tok)
        return enhanced


__all__ = ["PhraseFSM"]
