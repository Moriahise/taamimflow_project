"""
Decision-Tree Matcher for Cantillation Contexts
==============================================

FIX V10: Import-Pfade angepasst – relativer Import als primäre Quelle,
Fallback-Definitionen bleiben erhalten.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

try:
    from taamimflow.data.tropedef import Style, TropeDefinition, TropeContext, Note  # type: ignore
except ImportError:
    # Fallback-Definitionen (identisch mit cantillation.py)
    @dataclass
    class Note:  # type: ignore[no-redef]
        pitch: str
        duration: float
        upbeat: bool = False

    @dataclass
    class TropeContext:  # type: ignore[no-redef]
        conditions: Dict[str, str]
        notes: List[Note]

    @dataclass
    class TropeDefinition:  # type: ignore[no-redef]
        name: str
        contexts: List[TropeContext]

    @dataclass
    class Style:  # type: ignore[no-redef]
        name: str
        type: str
        encoding: str
        tropes: Dict[str, TropeDefinition] | None = None

    def load_trope_definitions(_: str) -> List[Style]:  # type: ignore
        raise RuntimeError("load_trope_definitions() not available")


def _canon(s: str) -> str:
    """Normalize group names to uppercase with underscores."""
    s = unicodedata.normalize("NFD", s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return s.replace(' ', '_').replace('-', '_').upper()


class DecisionTreeMatcher:
    """Prototyp eines Decision-Tree-Matchers.

    Baut für jede Tropen-Definition einen Baum auf, dessen Knoten
    Bedingungen repräsentieren. Beim Lookup werden die konkreten
    Bedingungen nacheinander durchlaufen; ohne exakten Match wird auf
    den ``default``-Eintrag zurückgegriffen.
    """

    def __init__(self, style: Style) -> None:
        self.trees: Dict[str, dict] = {}
        for name, trope_def in (style.tropes or {}).items():
            self.trees[name] = self._build_tree(trope_def)

    def _build_tree(self, trope_def: TropeDefinition) -> dict:
        tree: dict = {"default": None}
        sorted_ctx = sorted(
            trope_def.contexts,
            key=lambda c: len(c.conditions) if c.conditions else 0,
            reverse=True,
        )
        for ctx in sorted_ctx:
            if not ctx.conditions:
                tree["default"] = ctx.notes
                continue
            node = tree
            conds = dict(ctx.conditions)
            keys = []
            if 'AFTER' in conds:
                keys.append(('after', _canon(conds.pop('AFTER'))))
            if 'BEFORE' in conds:
                keys.append(('before', _canon(conds.pop('BEFORE'))))
            for flag in ('END_OF_VERSE', 'END_OF_CHAPTER', 'START_OF_CHAPTER',
                         'END_OF_ALIYAH', 'START_OF_ALIYAH'):
                if flag in conds:
                    keys.append((flag.lower(), True))
                    conds.pop(flag)
            if 'ATTRIB' in conds:
                keys.append(('attrib', conds.pop('ATTRIB')))
            for (k, v) in keys:
                node = node.setdefault(k, {})
                node = node.setdefault(v, {})
            node['notes'] = ctx.notes
        return tree

    def match(
        self,
        trope_name: str,
        prev: Optional[str],
        next_: Optional[str],
        flags: Dict[str, bool],
        attributes: Iterable[str],
    ) -> Tuple[Optional[List[Note]], str]:
        """Finde passende Noten und gebe einen Debug-String zurück."""
        tree = self.trees.get(trope_name)
        if not tree:
            return None, "kein Baum"
        best_notes: Optional[List[Note]] = tree.get('default')
        best_debug = "Default"

        def recurse(node: dict, path_debug: List[str]) -> None:
            nonlocal best_notes, best_debug
            if 'notes' in node:
                best_notes = node['notes']
                best_debug = "; ".join(path_debug) if path_debug else "Matched"
            if prev:
                after_node = node.get('after', {}).get(prev)
                if after_node:
                    recurse(after_node, path_debug + [f"AFTER={prev}"])
            if next_:
                before_node = node.get('before', {}).get(next_)
                if before_node:
                    recurse(before_node, path_debug + [f"BEFORE={next_}"])
            for flag_key, flag_var in [
                ('end_of_verse', 'VERSE_END'),
                ('end_of_chapter', 'CHAPTER_END'),
                ('start_of_chapter', 'CHAPTER_START'),
                ('end_of_aliyah', 'ALIYAH_END'),
                ('start_of_aliyah', 'ALIYAH_START'),
            ]:
                if node.get(flag_key) and flags.get(flag_var):
                    recurse(node[flag_key].get(True, {}), path_debug + [flag_key.upper()])
            attrib_node = node.get('attrib')
            if attrib_node:
                for attr in attributes:
                    if attr in attrib_node:
                        recurse(attrib_node[attr], path_debug + [f"ATTRIB={attr}"])

        recurse(tree, [])
        return best_notes, best_debug
