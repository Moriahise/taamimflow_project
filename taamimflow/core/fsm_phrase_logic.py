"""
Finite‑State Phrase Logic for Trope Sequencing
=============================================

Dieses Modul definiert eine einfache Finite‑State‑Machine (FSM), die
zusätzliche Kontext‑Flags und Phrasenattribute für eine Sequenz von
hebräischen Tokens berechnet. Sie dient als Erweiterung der
Cantillation‑Extraktion aus ``milestone9_plus.py`` und arbeitet als
Vorverarbeitungsstufe für den Decision‑Tree‑Matcher aus
``decision_tree.py``. Das Ziel ist es, komplexere logische
Zusammenhänge (Kapitel‑, Abschnitts‑ und Aliya‑Grenzen oder andere
semantische Phrasen) zu erkennen und über mehrere Tokens hinweg
fortzuführen.

Hinweis: Diese FSM ist ein generischer Rahmen. Es gibt
verschiedene Traditionen und Texte mit individuellen Markern für
Kapitel‑/Alijah‑Grenzen oder spezielle Phrasen. Der hier implementierte
Statuswechsel basiert auf einfachen Heuristiken und kann bei Bedarf
durch eine Konfigurationsdatei oder benutzerdefinierte Regeln ersetzt
werden.

Beispielverwendung:

    from milestone9_plus import TokenFull
    from fsm_phrase_logic import PhraseFSM
    
    tokens: List[TokenFull] = ...  # mit notes und Flags
    fsm = PhraseFSM()
    enhanced = fsm.annotate(tokens)
    # jedes Token in ``enhanced`` enthält zusätzliche flags wie
    # ``ALIYAH_START`` oder ``ALIYAH_END``, falls erkannt

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Dict, Optional

try:
    # Verwende TokenFull aus milestone9_plus, wenn verfügbar
    from milestone9_plus import TokenFull  # type: ignore
except ImportError:
    # Fallback‑Definition zur Typkompatibilität
    @dataclass
    class TokenFull:
        text: str
        group: Optional[str] = None
        symbol: Optional[str] = None
        color: Optional[str] = None
        marks: List[str] = field(default_factory=list)
        verse_end: bool = False
        chapter_end: bool = False
        # flags and notes (for audio)
        flags: Dict[str, bool] = field(default_factory=dict)
        notes: Optional[List[object]] = None

class PhraseFSM:
    """FSM zur Bestimmung von Kapitel‑, Aliyah‑ und Phrasen‑Flags.

    Die Maschine speichert interne Zustände wie Kapitelnummer,
    Aliyah‑Index und kann so definieren, wann ein Abschnitt beginnt
    oder endet. Für Phrasenattribute (z. B. ``ATTRIB``‑Labels aus
    ``tropedef.xml``) können zusätzliche Regeln registriert werden.

    Momentan implementiert die FSM die folgenden Heuristiken:

    * ``VERSE_END``: Am Ende eines Verses (``verse_end=True``) wird
      ``FLAGS['VERSE_END']`` gesetzt.
    * ``CHAPTER_END``: Wenn ein Token mit ``chapter_end=True`` markiert
      ist, wird ``FLAGS['CHAPTER_END']`` gesetzt und der
      ``chapter_counter`` erhöht.
    * ``ALIYAH_START``/``ALIYAH_END``: Aliyah‑Abschnitte werden anhand
      einer festen Anzahl von Versen pro Aliyah markiert (default: 7).

    Die FSM erzeugt pro Token ein neues ``TokenFull``‑Objekt, dessen
    ``flags``‑Dictionary um weitere Flags ergänzt ist. Die
    ursprünglichen Werte (``verse_end``, ``chapter_end``) bleiben
    erhalten, damit bestehende Logik nicht gebrochen wird.
    """

    def __init__(self, verses_per_aliyah: int = 7) -> None:
        self.chapter_counter = 1
        self.verse_counter = 0
        self.verses_per_aliyah = verses_per_aliyah
        self.aliya_counter = 1

    def annotate(self, tokens: Iterable[TokenFull]) -> List[TokenFull]:
        """Füge Kontext‑Flags für Kapitel‑, Aliyah‑ und Versgrenzen hinzu.

        :param tokens: Sequenz von ``TokenFull``.
        :return: Liste neuer ``TokenFull`` mit erweiterten Flags.
        """
        enhanced: List[TokenFull] = []
        for tok in tokens:
            # Kopiere Token, damit wir es nicht mutieren
            new_tok = TokenFull(
                text=tok.text,
                group=tok.group,
                symbol=tok.symbol,
                color=tok.color,
                marks=list(tok.marks),
                verse_end=tok.verse_end,
                chapter_end=tok.chapter_end,
                flags=dict(getattr(tok, 'flags', {})),
                notes=tok.notes
            )
            # Setze Versende
            if new_tok.verse_end:
                new_tok.flags['VERSE_END'] = True
                self.verse_counter += 1
            else:
                new_tok.flags['VERSE_END'] = False
            # Kapitelende
            if new_tok.chapter_end:
                new_tok.flags['CHAPTER_END'] = True
                self.chapter_counter += 1
                self.verse_counter = 0  # neues Kapitel
            else:
                new_tok.flags['CHAPTER_END'] = False
            # Aliyah‑Logik: starte/ende Aliyah nach bestimmten Versen
            if self.verse_counter == 1 and not new_tok.flags.get('CHAPTER_END'):
                # Start einer Aliyah
                new_tok.flags['ALIYAH_START'] = True
                if self.aliya_counter > 1:
                    # Vorheriges Token war Aliyah-Ende
                    # Markiere das vorherige Token entsprechend
                    if enhanced:
                        prev = enhanced[-1]
                        prev.flags['ALIYAH_END'] = True
                self.aliya_counter += 1
            else:
                new_tok.flags['ALIYAH_START'] = False
            # Wenn Aliyah Ende erreicht (nach verses_per_aliyah Versen)
            if self.verse_counter == self.verses_per_aliyah:
                new_tok.flags['ALIYAH_END'] = True
                self.verse_counter = 0
            else:
                # Wenn nicht explizit gesetzt, False
                new_tok.flags.setdefault('ALIYAH_END', False)
            enhanced.append(new_tok)
        return enhanced

__all__ = ["PhraseFSM"]