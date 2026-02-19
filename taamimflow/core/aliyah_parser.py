"""
Aliyah‑Parser für Torah‑Lesungen
================================

Dieses Modul enthält eine einfache Parser‑Klasse, die die Einteilung
der Toralesung in Aliyot (Abschnitte) aus einer XML‑Datei
(`sedrot.xml`) liest. Die Datei legt pro Buch und pro Abschnitt
fest, welche Verse zu einer Aliyah gehören. Diese Informationen
können genutzt werden, um Tokens mit ``ALIYAH_START`` und
``ALIYAH_END`` zu versehen oder um die nächste Aliyah zu bestimmen.

Hinweis: Das tatsächliche XML‑Schema von ``sedrot.xml`` kann je nach
Projekt abweichen. Diese Implementierung unterstützt ein sehr
einfaches Schema zur Demonstration. Sollte das Format anders sein,
ist diese Klasse entsprechend anzupassen.

Beispielhaft könnte ``sedrot.xml`` wie folgt aussehen:

    <SEDROT>
      <BOOK name="Genesis">
        <ALIYAH number="1" start="1:1" end="2:3"/>
        <ALIYAH number="2" start="2:4" end="3:5"/>
        …
      </BOOK>
    </SEDROT>

"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

@dataclass
class Aliyah:
    book: str
    number: int
    start: Tuple[int, int]  # (Kapitel, Vers)
    end: Tuple[int, int]


class AliyahParser:
    """Parser für Aliyah‑Definitionen aus ``sedrot.xml``.

    Diese Klasse lädt die XML‑Datei bei Instanziierung und stellt
    Methoden zur Verfügung, um für ein gegebenes Buch/Referenz zu
    ermitteln, in welcher Aliyah sich ein Vers befindet.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.books: Dict[str, List[Aliyah]] = {}
        self._load(path)

    def _parse_ref(self, ref: str) -> Tuple[int, int]:
        # Format "Kapitel:Vers" (z. B. "2:3")
        parts = ref.split(':')
        if len(parts) != 2:
            raise ValueError(f"Invalid reference: {ref}")
        return int(parts[0]), int(parts[1])

    def _load(self, path: str) -> None:
        tree = ET.parse(path)
        root = tree.getroot()
        for book_el in root.findall('BOOK'):
            name = book_el.get('name') or ''
            aliyot: List[Aliyah] = []
            for aliyah_el in book_el.findall('ALIYAH'):
                num_str = aliyah_el.get('number', '0')
                try:
                    num = int(num_str)
                except ValueError:
                    num = 0
                start_ref = aliyah_el.get('start', '')
                end_ref = aliyah_el.get('end', '')
                if not start_ref or not end_ref:
                    continue
                start = self._parse_ref(start_ref)
                end = self._parse_ref(end_ref)
                aliyot.append(Aliyah(book=name, number=num, start=start, end=end))
            self.books[name] = aliyot

    def find_aliyah(self, book: str, chapter: int, verse: int) -> Optional[Aliyah]:
        """Finde die Aliyah für einen gegebenen Kapitel‑/Vers‑Index.

        :param book: Name des Buches
        :param chapter: Kapitelnummer
        :param verse: Versnummer
        :return: Ein ``Aliyah``‑Objekt oder ``None``, wenn nicht gefunden.
        """
        aliyot = self.books.get(book)
        if not aliyot:
            return None
        for ali in aliyot:
            # Vergleiche (Kapitel, Vers) lexikografisch
            if (chapter, verse) < ali.start:
                continue
            if (chapter, verse) > ali.end:
                continue
            return ali
        return None

__all__ = ["Aliyah", "AliyahParser"]