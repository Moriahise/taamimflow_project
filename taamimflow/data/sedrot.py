"""Reading schedule (Sedrot) parser.

This module provides simple structures and a parser for ``sedrot.xml``
bundled with the legacy TropeTrainer distribution.  The file encodes
the weekly Torah portions (parshiot), holiday readings and associated
Maftir/Haftarah selections.  Each reading is represented by one or
more ``option`` elements describing how the portion should be read for
different cycles (annual, triennial) or special occasions.

The parser deliberately avoids imposing interpretation on the encoded
verse ranges.  Verse strings (e.g. ``"GEN1:1-2:3"``) are preserved as
given, leaving it to higher layers or connectors to resolve them into
actual text.  Similarly, ``Haftarah`` elements (spelled as separate
tags in the XML) are normalised into the same Option structure for
consistency.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SedraOption:
    """Represents a single reading option within a parasha.

    ``type``
        The type of the reading (``"Torah"``, ``"Haftarah"``, ``"Maftir"``, etc.).

    ``name``
        A descriptive name such as "Shabbas", "Weekday" or a holiday.

    ``cycle``
        An optional integer representing the triennial cycle.  The
        special value ``0`` denotes the annual cycle (i.e. read the
        full portion), ``1``–``3`` denote the respective years of a
        triennial cycle and ``4`` is often used for weekday readings.

    ``wrapped``
        Whether the aliyot in this option wrap around the end of a
        book.  This information is present in the XML but has no
        semantic effect in the current implementation; it is retained
        for completeness.

    ``special``
        Some options are marked as special for a particular event
        (e.g. "Shabbas Rosh Chodesh").  This field stores the text of
        the ``SPECIAL`` attribute when present.

    ``aliyot``
        A mapping from aliyah name (``"KOHEN"``, ``"LEVI"`` etc.) to
        verse ranges.  For Haftarah and Maftir options, the keys may
        include ``"MAFTIR"``, ``"R1"``, ``"R2"``, etc.
    """

    type: str
    name: str
    cycle: Optional[int] = None
    wrapped: Optional[bool] = None
    special: Optional[str] = None
    aliyot: Dict[str, str] = field(default_factory=dict)


@dataclass
class Sedra:
    """A weekly Torah portion (parasha) with its various options."""

    name: str
    options: List[SedraOption]


def load_sedrot(xml_path: Path) -> List[Sedra]:
    """Load sedrot readings from the given XML file.

    :param xml_path: Path to ``sedrot.xml`` or another file with the
        same schema.
    :return: A list of :class:`Sedra` objects representing each
        portion.
    """

    tree = ET.parse(xml_path)
    root = tree.getroot()
    sedrot: List[Sedra] = []
    for reading_elem in root.findall("READING"):
        name = reading_elem.attrib.get("NAME", "")
        options: List[SedraOption] = []
        # Options may be stored under both OPTION and HAFTARAH tags
        for opt_elem in reading_elem:
            if opt_elem.tag not in {"OPTION", "HAFTARAH"}:
                continue
            opt_type = opt_elem.attrib.get("TYPE", opt_elem.tag)
            opt_name = opt_elem.attrib.get("NAME", "")
            # The CYCLE attribute might be absent or not convertible
            cycle_str = opt_elem.attrib.get("CYCLE")
            cycle = int(cycle_str) if cycle_str is not None and cycle_str.isdigit() else None
            wrapped_str = opt_elem.attrib.get("WRAPPED")
            wrapped = None
            if wrapped_str is not None:
                wrapped = wrapped_str.lower() == "true"
            special = opt_elem.attrib.get("SPECIAL")
            aliyot: Dict[str, str] = {}
            for key, value in opt_elem.attrib.items():
                if key.upper() in {"TYPE", "NAME", "CYCLE", "WRAPPED", "SPECIAL"}:
                    continue
                aliyot[key.upper()] = value
            option = SedraOption(
                type=opt_type,
                name=opt_name,
                cycle=cycle,
                wrapped=wrapped,
                special=special,
                aliyot=aliyot,
            )
            options.append(option)
        sedrot.append(Sedra(name=name, options=options))
    return sedrot