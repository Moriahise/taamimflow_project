"""
Parser for ``tropedef.xml`` files.

The Trope definition file stores musical patterns (melodies) for each
cantillation mark (trope).  Each trope may have multiple contexts
depending on what follows or precedes it (for example, a *Munach*
before a *Zarka* might be sung differently than a default *Munach*).

This parser produces a nested data structure that can be used to
generate audio, notation or user interfaces.  Only the elements
relevant for note sequences are extracted; lesson notes and other
metadata are preserved but not fully parsed here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Note:
    pitch: str
    duration: float
    upbeat: bool = False


@dataclass
class TropeContext:
    """Represents the melodic pattern of a trope in a given context."""
    conditions: Dict[str, str]
    notes: List[Note]


@dataclass
class TropeDefinition:
    name: str
    contexts: List[TropeContext] = field(default_factory=list)


@dataclass
class Style:
    """Represents a complete set of trope definitions for a tradition/style."""
    name: str
    type: str
    encoding: str
    pitchbend: Optional[str] = None
    key: Optional[str] = None
    parameters: Dict[str, str] = field(default_factory=dict)
    tropes: Dict[str, TropeDefinition] = field(default_factory=dict)


def parse_note_element(elem: ET.Element) -> Note:
    """Create a ``Note`` from an XML ``NOTE`` element."""
    pitch = elem.attrib.get("PITCH", "")
    duration_str = elem.attrib.get("DURATION", "0")
    try:
        duration = float(duration_str)
    except ValueError:
        duration = 0.0
    upbeat = elem.attrib.get("UPBEAT", "False").lower() == "true"
    return Note(pitch=pitch, duration=duration, upbeat=upbeat)


def parse_context_element(elem: ET.Element) -> TropeContext:
    """Parse a ``CONTEXT`` element into a ``TropeContext`` instance."""
    conditions = {k: v for k, v in elem.attrib.items()}
    notes_container = elem.find("NOTES")
    notes: List[Note] = []
    if notes_container is not None:
        for note_elem in notes_container.findall("NOTE"):
            notes.append(parse_note_element(note_elem))
    return TropeContext(conditions=conditions, notes=notes)


def parse_trope_element(elem: ET.Element) -> TropeDefinition:
    """Parse a ``TROPE`` element into a ``TropeDefinition`` instance."""
    name = elem.attrib.get("NAME", "")
    trope_def = TropeDefinition(name=name)
    for context_elem in elem.findall("CONTEXT"):
        trope_def.contexts.append(parse_context_element(context_elem))
    return trope_def


def parse_style_element(elem: ET.Element) -> Style:
    """Parse a ``TROPEDEF`` element into a ``Style`` instance."""
    name = elem.attrib.get("NAME", "Unnamed Style")
    style_type = elem.attrib.get("TYPE", "Unknown")
    encoding = elem.attrib.get("ENCODING", "")
    pitchbend = elem.attrib.get("PITCHBEND")
    key = elem.attrib.get("KEY")
    parameters: Dict[str, str] = {}

    # Additional optional attributes can be included here

    style = Style(
        name=name,
        type=style_type,
        encoding=encoding,
        pitchbend=pitchbend,
        key=key,
        parameters=parameters,
    )

    for trope_elem in elem.findall("TROPE"):
        trope_def = parse_trope_element(trope_elem)
        style.tropes[trope_def.name] = trope_def
    return style


def load_trope_definitions(xml_path: str | Path) -> List[Style]:
    """Parse a ``tropedef.xml`` file into a list of ``Style`` objects.

    :param xml_path: Path to the XML file.
    :return: A list of styles defined in the file.
    """
    path = Path(xml_path)
    tree = ET.parse(path)
    root = tree.getroot()
    styles: List[Style] = []
    for trope_def_elem in root.findall("TROPEDEF"):
        styles.append(parse_style_element(trope_def_elem))
    return styles