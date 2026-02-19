"""
Timing-Map-Generator für Karaoke-Highlighting
============================================

FIX V10: Relativer Import ``from .audio_engine import Note`` statt
``from audio_engine import Note`` (Fix P6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

# Fix P6: Relativer Import innerhalb des audio-Packages
try:
    from .audio_engine import Note  # type: ignore
except ImportError:
    try:
        from taamimflow.audio.audio_engine import Note  # type: ignore
    except ImportError:
        @dataclass
        class Note:  # type: ignore[no-redef]
            pitch: str
            duration: float
            upbeat: bool = False


def compute_timing(
    tokens: Iterable[object],
    tempo: float = 120.0,
) -> List[Tuple[float, float]]:
    """Berechne Start-/Endzeiten für jede Token-Notensequenz.

    :param tokens: Iterable von Token-Objekten mit ``notes`` (Liste von
        ``Note``). Token ohne Noten werden als stumme 0.1-Sekunden-
        Segmente behandelt.
    :param tempo: Tempo in BPM.
    :return: Liste von ``(start_sec, end_sec)`` Paaren in Sekunden.
    """
    timings: List[Tuple[float, float]] = []
    current_time = 0.0
    beat_sec = 60.0 / tempo

    for tok in tokens:
        notes = getattr(tok, 'notes', None)
        if not notes:
            length = 0.1  # stummes Token
        else:
            length = sum(note.duration * beat_sec for note in notes)
        start = current_time
        end = current_time + length
        timings.append((start, end))
        current_time = end

    return timings


__all__ = ["compute_timing"]
