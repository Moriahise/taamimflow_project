"""Training modules parser.

The legacy training system in TropeTrainer v7 defines a collection of
lesson and flashcard modules stored in an XML file (``training.xml``).
Each module groups several ``option`` entries that refer to RTF and
plain text files containing the teaching material.  This parser
represents each module and option as simple Python data structures.  It
does not attempt to interpret or render the RTF files; rather, it
exposes the metadata so that an application can load the appropriate
content from disk or remote storage at runtime.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TrainingOption:
    """Represents a single lesson, flashcard or test in a training module.

    ``type``
        Category of the training (e.g. ``"Torah"``, ``"Haftarah"``,
        ``"HiHoliday"``, etc.).

    ``tutorial``
        The kind of exercise: ``"LESSON"``, ``"FLASHCARD"`` or
        ``"TEST"`` (other values may exist).

    ``name``
        Human readable title of the option.

    ``display``
        Some options are marked with ``DISPLAY="FALSE"`` to hide them
        from the user interface until prerequisites are met.  This
        boolean reflects that flag.  The default is ``True`` if the
        attribute is absent.

    ``twoline``
        Whether the flashcard should display two lines of text.  Values
        are derived from the ``TWOLINE`` attribute which may be
        ``"TRUE"`` or ``"FALSE"``.  When the attribute is omitted, it
        defaults to ``False``.

    ``lessonwindow``
        Suggested height of the lesson window in pixels.  The value is
        stored as an integer or ``None`` if not present.

    ``wrapped``
        Whether the text should wrap within the lesson window.  This
        corresponds to the ``WRAPPED`` attribute (``"TRUE"`` or
        ``"FALSE"``).  When omitted, it defaults to ``False``.

    ``file_refs``
        Mapping of file identifiers (e.g. ``L1``, ``R1``) to file names
        specified in the XML.  These correspond to RTF and TXT files.
    """

    type: str
    tutorial: str
    name: str
    display: bool = True
    twoline: bool = False
    lessonwindow: Optional[int] = None
    wrapped: bool = False
    file_refs: Dict[str, str] = field(default_factory=dict)


@dataclass
class TrainingModule:
    """A group of related training options."""

    name: str
    options: List[TrainingOption]


def load_training(xml_path: Path) -> List[TrainingModule]:
    """Parse training modules from an XML definition.

    :param xml_path: Path to ``training.xml`` or similar file.
    :return: A list of :class:`TrainingModule` instances.
    """

    tree = ET.parse(xml_path)
    root = tree.getroot()
    modules: List[TrainingModule] = []
    for module_elem in root.findall("TRAINING"):
        module_name = module_elem.attrib.get("NAME", "")
        options: List[TrainingOption] = []
        for opt_elem in module_elem.findall("OPTION"):
            opt_type = opt_elem.attrib.get("TYPE", "")
            tutorial = opt_elem.attrib.get("TUTORIAL", "")
            name = opt_elem.attrib.get("NAME", "")
            display_attr = opt_elem.attrib.get("DISPLAY")
            display = False if display_attr and display_attr.upper() == "FALSE" else True
            twoline_attr = opt_elem.attrib.get("TWOLINE")
            twoline = True if twoline_attr and twoline_attr.upper() == "TRUE" else False
            lessonwindow_attr = opt_elem.attrib.get("LESSONWINDOW")
            lessonwindow = None
            if lessonwindow_attr and lessonwindow_attr.isdigit():
                lessonwindow = int(lessonwindow_attr)
            wrapped_attr = opt_elem.attrib.get("WRAPPED")
            wrapped = True if wrapped_attr and wrapped_attr.upper() == "TRUE" else False
            # Collect file references (L1, L2, R1, etc.)
            file_refs: Dict[str, str] = {}
            for key, value in opt_elem.attrib.items():
                if key.upper() in {"TYPE", "TUTORIAL", "NAME", "DISPLAY", "TWOLINE", "LESSONWINDOW", "WRAPPED"}:
                    continue
                file_refs[key.upper()] = value
            option = TrainingOption(
                type=opt_type,
                tutorial=tutorial,
                name=name,
                display=display,
                twoline=twoline,
                lessonwindow=lessonwindow,
                wrapped=wrapped,
                file_refs=file_refs,
            )
            options.append(option)
        modules.append(TrainingModule(name=module_name, options=options))
    return modules