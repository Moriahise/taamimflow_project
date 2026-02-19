"""
Milestone 9.1 – Erweiterte Tropen‑Extraktion und Kontext‑Analyse
===============================================================

Dieses Modul baut auf dem MVP aus Milestone 9 auf und erweitert die
Funktionalität in mehreren Punkten:

* **Morphologische Segmentierung:** Verwendung eines optionalen
  hebräischen Tokenizers (z.B. ``hebrew_tokenizer``) zur korrekten
  Aufteilung von Wörtern und Morphemen. Wenn das Paket nicht
  installiert ist, wird auf die einfache Wortteilung nach
  Leerzeichen zurückgegriffen.
* **Kontext‑Flags:** Jedes Token enthält nun zusätzliche
  Kontextinformationen wie Kapitel‑ und Alijah‑Grenzen sowie
  benutzerdefinierte Attribut‑Labels. Diese Flags können bei der
  Melodieauswahl berücksichtigt werden.
* **Debug‑Ausgabe:** Für jedes Token wird eine Erklärung erzeugt,
  die beschreibt, welche Kontextdefinition aus der XML gegriffen hat
  und warum. Dies erleichtert das Nachvollziehen der
  Entscheidungslogik.

Der Code ist so gestaltet, dass bestehende Schnittstellen (z.B. für
die UI) nicht brechen: Die ursprünglichen Felder aus Milestone 9
werden beibehalten, während neue Felder optional sind. Das Modul
funktioniert sowohl eigenständig als auch eingebunden in das
``taamimflow``‑Projekt.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

try:
    # Re‑use definitions from the original project if available
    from taamimflow.data.tropedef import Style, TropeDefinition, TropeContext, Note, load_trope_definitions  # type: ignore
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
        pitchbend: Optional[str] = None
        key: Optional[str] = None
        parameters: Dict[str, str] | None = None
        tropes: Dict[str, TropeDefinition] | None = None

    def load_trope_definitions(_: str | Path) -> List[Style]:  # type: ignore
        raise NotImplementedError(
            "load_trope_definitions() konnte nicht importiert werden. "
            "Installiere das taamimflow‑Projekt oder importiere diese Funktion selbst."
        )

# ---------------------------------------------------------------------------
# Trope‑Gruppen und Mapping (wie in milestone9.py)

@dataclass(frozen=True)
class TropeGroup:
    name: str
    color: str
    symbol: str
    rank: int

GROUPS: Dict[str, TropeGroup] = {
    "Sof Pasuk":      TropeGroup("Sof Pasuk",      "#00FFFF", "׃", 0),  # Cyan
    "Etnachta":        TropeGroup("Etnachta",        "#FF00FF", "֑", 1),  # Magenta
    "Segol":           TropeGroup("Segol",           "#FFFF00", "֒", 2),  # Yellow
    "Zakef":           TropeGroup("Zakef",           "#FFFF00", "֔", 2),  # Yellow
    "Zakef Gadol":     TropeGroup("Zakef Gadol",     "#FFFF00", "֕", 2),  # Yellow
    "Shalshelet":      TropeGroup("Shalshelet",      "#FFFF00", "֓", 2),  # Yellow
    "Tipeha":          TropeGroup("Tipeha",          "#FFFFFF", "֖", 3),  # White
    "Revia":           TropeGroup("Revia",           "#FFFFFF", "֗", 3),  # White
    "Tevir":           TropeGroup("Tevir",           "#FFFFFF", "֛", 3),  # White
    "Pashta":          TropeGroup("Pashta",          "#FFFFFF", "֙", 3),  # White
    "Yetiv":           TropeGroup("Yetiv",           "#FFFFFF", "֚", 3),  # White
    "Zarqa":           TropeGroup("Zarqa",           "#FFFFFF", "֘", 3),  # White
    "Geresh":          TropeGroup("Geresh",          "#FFFFFF", "֜", 3),  # White
    "Gershayim":       TropeGroup("Gershayim",       "#FFFFFF", "֞", 3),  # White
    "Pazer":           TropeGroup("Pazer",           "#FFFFFF", "֡", 3),  # White
    "Qarney Para":     TropeGroup("Qarney Para",     "#FFFFFF", "֟", 3),  # White
    "Telisha Gedola":  TropeGroup("Telisha Gedola",  "#FFFFFF", "֠", 3),  # White
    # Konjunktive – hellgrün
    "Munach":          TropeGroup("Munach",          "#90EE90", "֣", 4),  # Light green
    "Mahpakh":         TropeGroup("Mahpakh",         "#90EE90", "֤", 4),  # Light green
    "Merkha":          TropeGroup("Merkha",          "#90EE90", "֥", 4),  # Light green
    "Merkha Kefula":   TropeGroup("Merkha Kefula",   "#90EE90", "֦", 4),  # Light green
    "Darga":           TropeGroup("Darga",           "#90EE90", "֧", 4),  # Light green
    "Qadma":           TropeGroup("Qadma",           "#90EE90", "֨", 4),  # Light green
    "Telisha Qetana":  TropeGroup("Telisha Qetana",  "#90EE90", "֩", 4),  # Light green
    "Yerah Ben Yomo":  TropeGroup("Yerah Ben Yomo",  "#90EE90", "֪", 4),  # Light green
    "Ole":             TropeGroup("Ole",             "#90EE90", "֫", 4),
    "Iluy":            TropeGroup("Iluy",            "#90EE90", "֬", 4),
    "Dehi":            TropeGroup("Dehi",            "#90EE90", "֭", 4),
    "Zinor":           TropeGroup("Zinor",           "#90EE90", "֮", 4),
    "Unknown":         TropeGroup("Unknown",         "#D3D3D3", "?", 5),   # Light grey
}

_MARK_TO_GROUP: Dict[str, str] = {
    '\u0591': "Etnachta",
    '\u0592': "Segol",
    '\u0593': "Shalshelet",
    '\u0594': "Zakef",
    '\u0595': "Zakef Gadol",
    '\u0596': "Tipeha",
    '\u0597': "Revia",
    '\u0598': "Zarqa",
    '\u0599': "Pashta",
    '\u059A': "Yetiv",
    '\u059B': "Tevir",
    '\u059C': "Geresh",
    '\u059D': "Geresh",
    '\u059E': "Gershayim",
    '\u059F': "Qarney Para",
    '\u05A0': "Telisha Gedola",
    '\u05A1': "Pazer",
    '\u05A2': "Etnachta",
    '\u05A3': "Munach",
    '\u05A4': "Mahpakh",
    '\u05A5': "Merkha",
    '\u05A6': "Merkha Kefula",
    '\u05A7': "Darga",
    '\u05A8': "Qadma",
    '\u05A9': "Telisha Qetana",
    '\u05AA': "Yerah Ben Yomo",
    '\u05AB': "Ole",
    '\u05AC': "Iluy",
    '\u05AD': "Dehi",
    '\u05AE': "Zinor",
}

_DISJUNCTIVE_MARKS = {
    '\u0591', '\u0592', '\u0593', '\u0594', '\u0595', '\u0596', '\u0597',
    '\u0598', '\u0599', '\u059A', '\u059B', '\u059C', '\u059D', '\u059E',
    '\u059F', '\u05A0', '\u05A1', '\u05A2',
}


@dataclass
class Token:
    """Basisklasse für ein Wort mit Tropen‑Metadaten."""
    word: str
    group_name: str
    symbol: str
    color: str
    trope_groups: List[str]
    verse_end: bool = False


@dataclass
class TokenWithNotes(Token):
    """Token mit einer zugeordneten Notenfolge."""
    notes: List[Note] | None = None


@dataclass
class TokenFull(TokenWithNotes):
    """Erweiterter Token für Milestone 9.1.

    Neben den Basisinformationen enthält dieser Typ zusätzliche
    Kontextflags (Kapitelanfang/‑ende, Alijahanfang/‑ende), frei
    definierbare Attribute sowie eine Debug‑Beschreibung darüber, wie
    die Noten ausgewählt wurden.
    """
    attributes: List[str] = field(default_factory=list)
    chapter_start: bool = False
    chapter_end: bool = False
    aliyah_start: bool = False
    aliyah_end: bool = False
    debug_info: Optional[str] = None


def normalise_hebrew(text: str) -> str:
    """Normalisiere die Eingabe auf Unicode‑NFD."""
    return unicodedata.normalize("NFD", text) if text else text


def _extract_marks(word: str) -> List[str]:
    """Extrahiere alle Cantillation‑Marken aus einem Wort."""
    return [ch for ch in word if ch in _MARK_TO_GROUP]


def _determine_group(marks: List[str], verse_end: bool) -> Tuple[str, str, str, List[str]]:
    """Wie in milestone9.py: Wähle die passende Hauptgruppe."""
    mark_names = [_MARK_TO_GROUP.get(m, "Unknown") for m in marks]
    if not marks and verse_end:
        grp = GROUPS["Sof Pasuk"]
        return grp.name, grp.symbol, grp.color, ["Sof Pasuk"]
    if not marks:
        grp = GROUPS["Unknown"]
        return grp.name, grp.symbol, grp.color, []
    best_name: Optional[str] = None
    best_rank = 999
    for m in marks:
        gname = _MARK_TO_GROUP.get(m, "Unknown")
        group = GROUPS.get(gname, GROUPS["Unknown"])
        if m in _DISJUNCTIVE_MARKS and group.rank < best_rank:
            best_rank = group.rank
            best_name = gname
        elif best_name is None:
            best_name = gname
    if best_name is None:
        best_name = mark_names[0] if mark_names else "Unknown"
    group = GROUPS.get(best_name, GROUPS["Unknown"])
    if verse_end and group.rank > 0:
        sof = GROUPS["Sof Pasuk"]
        return sof.name, sof.symbol, sof.color, mark_names
    return group.name, group.symbol, group.color, mark_names


def _load_hebrew_tokenizer():
    """Lade einen optionalen hebräischen Tokenizer.

    Wir versuchen zuerst, das Paket ``hebrew_tokenizer`` zu importieren.
    Falls es nicht installiert ist, wird ``None`` zurückgegeben.
    """
    try:
        from hebrew_tokenizer import tokenize as ht_tokenize  # type: ignore
    except ImportError:
        return None
    return ht_tokenize


def segment_text(text: str) -> List[str]:
    """Segmentiere hebräischen Text in Wörter/Morpheme.

    Diese Funktion nutzt, falls verfügbar, den ``hebrew_tokenizer`` zur
    linguistischen Segmentierung. Der Rückgabewert ist eine Liste von
    Tokens (Strings). Falls der Tokenizer nicht verfügbar ist, wird
    einfach nach Leerzeichen gesplittet.
    """
    if not text:
        return []
    tokenizer = _load_hebrew_tokenizer()
    if tokenizer is None:
        return text.split()
    # Tokenizer kann entweder einen String oder eine Sequenz zurückgeben.
    try:
        tokens = tokenizer(text)
    except Exception:
        # Fallback: Standard Splitting
        return text.split()
    # ``hebrew_tokenizer`` liefert üblicherweise eine Liste von Wörtern
    if isinstance(tokens, str):
        return tokens.split()
    # Wenn Tokenobjekte zurückgegeben werden (z.B. dicts mit 'text'), extrahieren
    try:
        return [tok["text"] if isinstance(tok, dict) and "text" in tok else str(tok) for tok in tokens]  # type: ignore
    except Exception:
        return [str(tok) for tok in tokens]


def _detect_context_flags(lines: List[str]) -> Tuple[List[bool], List[bool], List[bool], List[bool]]:
    """Detektiere Kapitel‑/Alijah‑Grenzen basierend auf Zeilenumbrüchen.

    Wir betrachten die Eingabe als Sequenz von Zeilen. Ein Kapitel‑ oder
    Alijah‑Ende wird angenommen, wenn eine leere Zeile oder eine Zeile
    mit nur Leerzeichen folgt. Der Beginn eines neuen Kapitels/Alijahs
    wird dann beim nächsten Token gesetzt. Diese heuristische Erkennung
    kann durch externe Metadaten ersetzt werden.

    :param lines: Liste von Strings (Tokens), wie von ``segment_text``
    :return: Vier Listen gleicher Länge: chapter_start, chapter_end,
             aliyah_start, aliyah_end. Alle Werte sind bools.
    """
    n = len(lines)
    chap_start = [False] * n
    chap_end = [False] * n
    ali_start = [False] * n
    ali_end = [False] * n
    if n == 0:
        return chap_start, chap_end, ali_start, ali_end
    # Wir interpretieren doppelte Leerzeichen ("" Einträge) als Abschnittsmarker
    prev_blank = True
    for i, tok in enumerate(lines):
        blank = not tok.strip()
        if prev_blank and not blank:
            # Abschnitt beginnt
            chap_start[i] = True
            ali_start[i] = True
        if blank and not prev_blank:
            # Abschnitt endet
            chap_end[i - 1] = True
            ali_end[i - 1] = True
        prev_blank = blank
    # Letztes Token beenden, falls kein abschließender Blank folgt
    if not prev_blank:
        chap_end[-1] = True
        ali_end[-1] = True
    return chap_start, chap_end, ali_start, ali_end


def tokenize(text: str, attributes: Optional[List[str]] = None) -> List[TokenFull]:
    """Zerlege hebräischen Text in TokenFull‑Objekte.

    :param text: Der Eingabetext in Unicode.
    :param attributes: Optionale Liste von Attributen, die jedem Token
        zugeordnet werden (z.B. besondere Phrase‑Labels). Wird weniger
        oder mehr als Tokens übergeben, werden Werte wiederholt oder
        abgeschnitten.
    :return: Liste von ``TokenFull`` mit Tropen‑Metadaten und Kontextflags.
    """
    tokens: List[TokenFull] = []
    if not text:
        return tokens
    normalised = normalise_hebrew(text)
    words = segment_text(normalised)
    # Heuristische Kontextbestimmung anhand leerer Strings
    chap_start, chap_end, ali_start, ali_end = _detect_context_flags(words)
    # Normiere Attribute list
    attr_list: List[str] = []
    if attributes:
        if len(attributes) >= len(words):
            attr_list = attributes[: len(words)]
        else:
            # Wiederhole das letzte Attribut für restliche Tokens
            attr_list = attributes + [attributes[-1]] * (len(words) - len(attributes))
    else:
        attr_list = [""] * len(words)
    for i, raw in enumerate(words):
        if not raw.strip():
            continue
        verse_end = (':') in raw or '\u05C3' in raw
        marks = _extract_marks(raw)
        group_name, symbol, color, mark_names = _determine_group(marks, verse_end)
        tokens.append(
            TokenFull(
                word=raw,
                group_name=group_name,
                symbol=symbol,
                color=color,
                trope_groups=mark_names,
                verse_end=verse_end,
                attributes=[attr_list[i]] if attr_list[i] else [],
                chapter_start=chap_start[i],
                chapter_end=chap_end[i],
                aliyah_start=ali_start[i],
                aliyah_end=ali_end[i],
            )
        )
    return tokens


def _canonise_group_name(name: str) -> str:
    """Kanonische Schreibweise wie in milestone9.py."""
    canon = unicodedata.normalize("NFD", name)
    canon = ''.join(ch for ch in canon if not unicodedata.combining(ch))
    canon = canon.replace(' ', '_').replace('-', '_')
    return canon.upper()


class ContextMatcher:
    """Erweitertes Kontextmatching mit zusätzlichen Flags und Debug.

    Wie im MVP werden ``Style``‑Definitionen geladen und anhand
    vorheriger/nächster Tropen die passende Notenfolge bestimmt. Neu
    hinzugekommen ist die Berücksichtigung von Kapitel‑/Alijah‑Grenzen
    sowie Attribut‑Labels in den XML‑Bedingungen. Außerdem erzeugt
    ``match_context`` eine Debug‑Beschreibung.
    """
    def __init__(self, xml_path: str | Path, style_name: Optional[str] = None) -> None:
        styles = load_trope_definitions(xml_path)
        if not styles:
            raise ValueError(f"Keine Tropendefinitionen in {xml_path} gefunden")
        self.styles: Dict[str, Style] = {s.name: s for s in styles}
        self.style_name = style_name or styles[0].name
        if self.style_name not in self.styles:
            raise ValueError(f"Stil '{self.style_name}' nicht in XML gefunden. Verfügbar: {list(self.styles)}")
        self._cache: Dict[Tuple[str, Optional[str], Optional[str], bool, bool, bool, Tuple[str, ...]], Tuple[List[Note] | None, str]] = {}

    def set_style(self, name: str) -> None:
        if name not in self.styles:
            raise ValueError(f"Unbekannter Stil '{name}'")
        self.style_name = name
        self._cache.clear()

    def _match_context(self, trope_def: TropeDefinition, prev_name: Optional[str], next_name: Optional[str], flags: Dict[str, bool], attributes: Tuple[str, ...]) -> Tuple[List[Note] | None, str]:
        """Durchsuche die Kontextdefinitionen und gebe Noten sowie Debug‑Info zurück.

        :param trope_def: Definition des aktuellen Tropen.
        :param prev_name: Kanonisierter Name der vorherigen Gruppe.
        :param next_name: Kanonisierter Name der nächsten Gruppe.
        :param flags: Dictionary mit Kontextflags: 'VERSE_END', 'CHAPTER_START', 'CHAPTER_END',
                      'ALIYAH_START', 'ALIYAH_END'.
        :param attributes: Tupel aller Attribute dieses Tokens.
        :return: (Notenliste oder None, Debug‑String)
        """
        default_notes: Optional[List[Note]] = None
        debug_default: str = ""
        # Iterate through contexts in order of appearance
        for ctx in trope_def.contexts:
            if not ctx.conditions:
                default_notes = ctx.notes
                debug_default = "Default ohne Bedingungen"
                continue
            match = True
            debug_parts: List[str] = []
            for key, val in ctx.conditions.items():
                if key == 'AFTER':
                    debug_parts.append(f"AFTER={val}")
                    if next_name != val:
                        match = False
                        debug_parts.append("≠")
                        break
                elif key == 'BEFORE':
                    debug_parts.append(f"BEFORE={val}")
                    if prev_name != val:
                        match = False
                        debug_parts.append("≠")
                        break
                elif key == 'TROPE_GROUP':
                    debug_parts.append(f"TROPE_GROUP={val}")
                    if _canonise_group_name(trope_def.name) != val.upper():
                        match = False
                        debug_parts.append("≠")
                        break
                elif key == 'END_OF_VERSE':
                    debug_parts.append("END_OF_VERSE")
                    if not flags.get('VERSE_END'):
                        match = False
                        debug_parts.append("≠")
                        break
                elif key == 'END_OF_CHAPTER':
                    debug_parts.append("END_OF_CHAPTER")
                    if not flags.get('CHAPTER_END'):
                        match = False
                        debug_parts.append("≠")
                        break
                elif key == 'START_OF_CHAPTER':
                    debug_parts.append("START_OF_CHAPTER")
                    if not flags.get('CHAPTER_START'):
                        match = False
                        debug_parts.append("≠")
                        break
                elif key == 'END_OF_ALIYAH':
                    debug_parts.append("END_OF_ALIYAH")
                    if not flags.get('ALIYAH_END'):
                        match = False
                        debug_parts.append("≠")
                        break
                elif key == 'START_OF_ALIYAH':
                    debug_parts.append("START_OF_ALIYAH")
                    if not flags.get('ALIYAH_START'):
                        match = False
                        debug_parts.append("≠")
                        break
                elif key == 'ATTRIB':
                    debug_parts.append(f"ATTRIB={val}")
                    if val not in attributes:
                        match = False
                        debug_parts.append("≠")
                        break
                elif key == 'DEFAULT':
                    debug_default = f"Explizites DEFAULT"
                    default_notes = ctx.notes
                else:
                    # Unbekannte Bedingungen ignorieren
                    debug_parts.append(f"IGNORIERE {key}")
            if match:
                debug_str = ", ".join(debug_parts) if debug_parts else "Kontext mit Bedingungen"
                return ctx.notes, debug_str
        return default_notes, debug_default

    def get_notes_and_debug(self, token: TokenFull, prev_token: Optional[TokenFull], next_token: Optional[TokenFull]) -> Tuple[List[Note] | None, str]:
        """Hole Noten und Debug‑Text für ein Token.

        Kontextflags aus dem Token werden berücksichtigt. Der Cache‑Key
        basiert auf Tropengruppe, vorheriger/nächster Gruppe, verse_end,
        Kapitel‑ und Alijah‑Flags sowie den Attributen.
        """
        prev_name = _canonise_group_name(prev_token.group_name) if prev_token else None
        next_name = _canonise_group_name(next_token.group_name) if next_token else None
        flags = {
            'VERSE_END': token.verse_end,
            'CHAPTER_START': token.chapter_start,
            'CHAPTER_END': token.chapter_end,
            'ALIYAH_START': token.aliyah_start,
            'ALIYAH_END': token.aliyah_end,
        }
        attr_tuple = tuple(token.attributes)
        key = (
            _canonise_group_name(token.group_name),
            prev_name,
            next_name,
            flags['VERSE_END'],
            flags['CHAPTER_START'] or flags['CHAPTER_END'],
            flags['ALIYAH_START'] or flags['ALIYAH_END'],
            attr_tuple,
        )
        if key in self._cache:
            return self._cache[key]
        style = self.styles[self.style_name]
        trope_key = _canonise_group_name(token.group_name)
        trope_def = style.tropes.get(trope_key) if style.tropes else None
        if trope_def is None:
            for name, td in (style.tropes or {}).items():
                if name.replace('_', '') == trope_key.replace('_', ''):
                    trope_def = td
                    break
        if trope_def is None:
            self._cache[key] = (None, "Keine Tropendefinition gefunden")
            return self._cache[key]
        notes, dbg = self._match_context(trope_def, prev_name, next_name, flags, attr_tuple)
        self._cache[key] = (notes, dbg)
        return notes, dbg

    def annotate_tokens(self, tokens: List[TokenFull]) -> List[TokenFull]:
        """Annotiere Tokens mit Noten und Debug‑Text."""
        annotated: List[TokenFull] = []
        for i, token in enumerate(tokens):
            prev_token = tokens[i - 1] if i > 0 else None
            next_token = tokens[i + 1] if i + 1 < len(tokens) else None
            notes, dbg = self.get_notes_and_debug(token, prev_token, next_token)
            token.notes = notes
            token.debug_info = dbg
            annotated.append(token)
        return annotated


def extract_tokens_with_notes(
    text: str,
    xml_path: str | Path,
    style_name: Optional[str] = None,
    attributes: Optional[List[str]] = None,
) -> List[TokenFull]:
    """End‑to‑End‑Funktion für Milestone 9.1.

    Diese Funktion kombiniert Tokenisierung, Kontextmatching und Debug‑Ausgabe.

    :param text: Hebräischer Text mit Cantillation‑Marken.
    :param xml_path: Pfad zur tropedef.xml
    :param style_name: Optional: Name des Stils (Tradition)
    :param attributes: Optional: Liste von Attributen pro Token.
    :return: Liste mit annotierten ``TokenFull``
    """
    tokens = tokenize(text, attributes)
    matcher = ContextMatcher(xml_path, style_name)
    return matcher.annotate_tokens(tokens)


__all__ = [
    "Token",
    "TokenWithNotes",
    "TokenFull",
    "extract_tokens_with_notes",
    "tokenize",
    "normalise_hebrew",
    "segment_text",
    "ContextMatcher",
    "TropeGroup",
    "GROUPS",
]