"""
Decision‑Tree Matcher for Cantillation Contexts
==============================================

Dieses Modul implementiert einen leistungsfähigeren Kontext‑Matcher für
Tropen anhand der ``tropedef.xml``. Anstatt jede Kontextdefinition
linear zu prüfen, wird beim Laden der XML ein Decision‑Tree (oder
präziser: ein verschachteltes Mapping) aufgebaut. Das ermöglicht
konstante Lookup‑Zeit unabhängig von der Anzahl der Kontextdefinitionen
pro Tropen.  Die Schlüssel für den Baum umfassen die vorherige
Tropengruppe (``prev``), die nächste Gruppe (``next``), Flags wie
``VERSE_END``/``CHAPTER_END``/``ALIYAH_END`` und beliebige
Attribut‑Labels.

Der Decision‑Tree ist wie folgt aufgebaut:

* Für jede Tropen‑Definition wird eine Wurzelknoten mit einem
  ``default``‑Eintrag angelegt, der die Noten ohne Bedingungen
  enthält.
* Kontextbedingungen wie ``AFTER``, ``BEFORE``, ``END_OF_VERSE``,
  ``END_OF_CHAPTER``, ``START_OF_ALIYAH``, ``ATTRIB`` werden als
  nested keys abgebildet. Beispielsweise wird der Kontext
  ``AFTER=REVIA`` → ``END_OF_VERSE`` → ``notes`` in der Struktur
  ``tree['after'][canon('REVIA')]['end_of_verse']=notes`` gespeichert.
  Mehrere Bedingungen werden geschachtelt.
* Beim Lookup traversiert der Matcher die Baumstruktur anhand der
  konkreten Kontextwerte. Wenn kein exakter Match existiert, fällt
  er auf den nächst höheren Default zurück.

Diese Implementierung ist nur ein erster Prototyp zur Demonstration
der Idee. Sie unterstützt die gleichen Bedingungen wie der einfache
Matcher in ``milestone9_plus.py``, erweitert um Kapitel‑ und
Alijah‑Flags.  Weitere Bedingungen können problemlos ergänzt werden.

"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Iterable

try:
    from taamimflow.data.tropedef import Style, TropeDefinition, TropeContext, Note  # type: ignore
except ImportError:
    @dataclass
    class Note:
        pitch: str
        duration: float
        upbeat: bool = False

    @dataclass
    class TropeContext:
        conditions: Dict[str, str]
        notes: List[Note]

    @dataclass
    class TropeDefinition:
        name: str
        contexts: List[TropeContext]

    @dataclass
    class Style:
        name: str
        type: str
        encoding: str
        tropes: Dict[str, TropeDefinition]

    def load_trope_definitions(_: str) -> List[Style]:  # type: ignore
        raise RuntimeError("load_trope_definitions() not available")


def _canon(s: str) -> str:
    """Normalize group names to uppercase with underscores."""
    s = unicodedata.normalize("NFD", s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return s.replace(' ', '_').replace('-', '_').upper()


class DecisionTreeMatcher:
    """Prototyp eines Decision‑Tree‑Matchers.

    Dieser Matcher baut für jede Tropen‑Definition einen Baum auf,
    dessen Knoten Bedingungen repräsentieren. Beim Lookup werden die
    konkreten Bedingungen (vorheriger/nächster Trop, Flags, Attribute)
    nacheinander durchlaufen; wenn auf einer Ebene kein Match
    gefunden wird, wird auf den ``default``‑Eintrag zurückgegriffen.
    """

    def __init__(self, style: Style) -> None:
        self.trees: Dict[str, dict] = {}
        for name, trope_def in (style.tropes or {}).items():
            tree = self._build_tree(trope_def)
            self.trees[name] = tree

    def _build_tree(self, trope_def: TropeDefinition) -> dict:
        tree: dict = {"default": None}
        # Sortiere Kontexte nach Zahl der Bedingungen (mehr = spezifischer)
        sorted_ctx = sorted(trope_def.contexts, key=lambda c: len(c.conditions) if c.conditions else 0, reverse=True)
        for ctx in sorted_ctx:
            if not ctx.conditions:
                tree["default"] = ctx.notes
                continue
            node = tree
            # Definiere Reihenfolge der Schlüssel: AFTER → BEFORE → END flags → START flags → ATTRIB
            conds = dict(ctx.conditions)
            # unify keys
            keys = []
            # AFTER
            if 'AFTER' in conds:
                keys.append(('after', _canon(conds.pop('AFTER'))))
            # BEFORE
            if 'BEFORE' in conds:
                keys.append(('before', _canon(conds.pop('BEFORE'))))
            # Flags
            for flag in ('END_OF_VERSE', 'END_OF_CHAPTER', 'START_OF_CHAPTER', 'END_OF_ALIYAH', 'START_OF_ALIYAH'):
                if flag in conds:
                    keys.append((flag.lower(), True))
                    conds.pop(flag)
            # ATTRIB
            if 'ATTRIB' in conds:
                keys.append(('attrib', conds.pop('ATTRIB')))
            # Unbekannte Bedingungen – ignorieren
            # Baue Verschachtelung
            for (k, v) in keys:
                node = node.setdefault(k, {})
                node = node.setdefault(v, {})
            # Speichere Noten in "notes"
            node['notes'] = ctx.notes
        return tree

    def match(self, trope_name: str, prev: Optional[str], next_: Optional[str], flags: Dict[str, bool], attributes: Iterable[str]) -> Tuple[Optional[List[Note]], str]:
        """Finde passende Noten und gebe einen Debug‑String zurück.

        :param trope_name: Kanonisierter Name der aktuellen Tropengruppe.
        :param prev: Kanonisierter Name der vorherigen Tropengruppe oder None.
        :param next_: Kanonisierter Name der nächsten Tropengruppe oder None.
        :param flags: Dict mit ``VERSE_END``/``CHAPTER_END`` etc.
        :param attributes: Iterable von Attribut‑Labels.
        :return: (Noten oder None, Debug‑Beschreibung)
        """
        tree = self.trees.get(trope_name)
        if not tree:
            return None, "kein Baum"
        best_notes: Optional[List[Note]] = tree.get('default')
        best_debug = "Default"
        debug_path: List[str] = []
        # Depth‑first search: Wir testen in folgender Reihenfolge
        # AFter → BEFORE → flags → ATTRIB
        def recurse(node: dict, path_debug: List[str]):
            nonlocal best_notes, best_debug
            # Prüfe notes
            if 'notes' in node:
                best_notes = node['notes']
                best_debug = "; ".join(path_debug) if path_debug else "Matched"
            # AFTER
            if prev:
                after_node = node.get('after', {}).get(prev)
                if after_node:
                    recurse(after_node, path_debug + [f"AFTER={prev}"])
            if next_:
                before_node = node.get('before', {}).get(next_)
                if before_node:
                    recurse(before_node, path_debug + [f"BEFORE={next_}"])
            # Flags
            for flag_key, flag_var in [('end_of_verse', 'VERSE_END'), ('end_of_chapter', 'CHAPTER_END'),
                                       ('start_of_chapter', 'CHAPTER_START'), ('end_of_aliyah', 'ALIYAH_END'),
                                       ('start_of_aliyah', 'ALIYAH_START')]:
                if node.get(flag_key) and flags.get(flag_var):
                    recurse(node[flag_key].get(True, {}), path_debug + [flag_key.upper()])
            # ATTRIB
            attrib_node = node.get('attrib')
            if attrib_node:
                for attr in attributes:
                    if attr in attrib_node:
                        recurse(attrib_node[attr], path_debug + [f"ATTRIB={attr}"])
        recurse(tree, debug_path)
        return best_notes, best_debug
