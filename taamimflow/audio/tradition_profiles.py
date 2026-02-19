"""Metadata definitions for cantillation traditions.

This module defines a dictionary mapping tradition names to directories of audio
sample files.  It can be extended to include metadata such as pitch offsets,
default tempo, or instrument names.  The concatenation engine uses this
information to locate the correct audio clips for each trope.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

@dataclass(frozen=True)
class TraditionProfile:
    """Information about a single cantillation tradition.

    Attributes:
        name: Human‑readable name, e.g. "Ashkenazi – Binder".
        sample_dir: Path to the directory containing audio samples
            (e.g. WAV or MP3 files) for this tradition.
        description: Optional description of the tradition.
    """
    name: str
    sample_dir: Path
    description: Optional[str] = None

# Example: define a few built‑in profiles.  In production, these paths
# should point to directories in your project's assets/audio folder.
BUILTIN_TRADITIONS: Dict[str, TraditionProfile] = {
    "Ashkenazi": TraditionProfile(
        name="Ashkenazi",
        sample_dir=Path("assets/audio/ashkenazi"),
        description="Classic Ashkenazi cantillation as taught in central Europe.",
    ),
    "Sephardi": TraditionProfile(
        name="Sephardi",
        sample_dir=Path("assets/audio/sephardi"),
        description="Sephardi cantillation with middle eastern ornamentation.",
    ),
    "Yemenite": TraditionProfile(
        name="Yemenite",
        sample_dir=Path("assets/audio/yemenite"),
        description="Yemenite tradition with unique melodic patterns.",
    ),
}


def get_tradition(name: str) -> TraditionProfile:
    """Return the TraditionProfile for the given name or raise KeyError."""
    return BUILTIN_TRADITIONS[name]
