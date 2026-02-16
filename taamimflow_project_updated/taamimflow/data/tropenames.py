"""
Parser for ``tropenames.xml``.

The tropenames file maps internal trope identifiers to human‑readable
names across different naming traditions (Ashkenazic, Sephardic,
academic, etc.).  The XML uses uppercase declarations and occasionally
includes invalid Unicode sequences in the ``HEB_CHAR_VALUE`` fields,
which prevents a straightforward ElementTree parse.  This parser
performs a line‑based extraction using regular expressions.  Only the
name and value fields are extracted, as these are the most relevant
for display.  Additional fields can be added as required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class Tradition:
    """Represents a naming tradition and its trope names."""
    name: str
    names: Dict[str, str] = field(default_factory=dict)


def load_trope_names(xml_path: str | Path) -> List[Tradition]:
    """Extract trope names from the given file.

    :param xml_path: Path to the tropenames XML file.
    :return: A list of traditions with their respective name mappings.
    """
    path = Path(xml_path)
    traditions: List[Tradition] = []
    current_trad: Tradition | None = None
    tradition_regex = re.compile(r'<TRADITION\s+NAME="([^"]+)"', re.IGNORECASE)
    chr_regex = re.compile(r'<CHR\s+NAME="([^"]+)"\s+VALUE="([^"]+)"', re.IGNORECASE)
    with open(path, "r", encoding="latin-1", errors="ignore") as f:
        for line in f:
            trad_match = tradition_regex.search(line)
            if trad_match:
                # Start a new tradition
                if current_trad:
                    traditions.append(current_trad)
                current_trad = Tradition(name=trad_match.group(1))
                continue
            chr_match = chr_regex.search(line)
            if chr_match and current_trad:
                name, value = chr_match.groups()
                current_trad.names[name] = value
    # Append the last tradition if present
    if current_trad:
        traditions.append(current_trad)
    return traditions