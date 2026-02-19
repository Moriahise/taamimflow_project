"""
Timing‑Map‑Generator für Karaoke‑Highlighting
============================================

Dieses Modul enthält Hilfsfunktionen, um aus einer Sequenz von
Tokens mit Noten und einem vorgegebenen Tempo eine zeitliche Karte
zu berechnen. Diese Karte ordnet jedem Token eine Start‑ und
Endzeit in Sekunden zu, so dass eine Karaoke‑ oder Highlighting‑UI
die aktuelle Position im Text hervorheben kann.

Die zeitliche Länge eines Tokens ergibt sich aus der Summe der
Dauern seiner Noten multipliziert mit der Dauer einer Viertelnote.
Auftaktnoten (``upbeat=True``) werden zum Zeitpunkt des Tokens
hinzuaddiert, verlängern aber nicht dessen Kernzeit. Diese
Heuristik kann je nach musikalischer Tradition angepasst werden.

Beispiel:

    from milestone9_plus import extract_tokens_with_notes
    from timing_map import compute_timing

    tokens = extract_tokens_with_notes(...)
    timings = compute_timing(tokens, tempo=120)
    # timings ist eine Liste von (start, end) Paaren in Sekunden

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

try:
    from audio_engine import Note  # type: ignore
except ImportError:
    @dataclass
    class Note:
        pitch: int
        duration: float
        upbeat: bool = False

def compute_timing(tokens: Iterable[object], tempo: float = 120.0) -> List[Tuple[float, float]]:
    """Berechne Start‑/Endzeiten für jede Token‑Notensequenz.

    :param tokens: Iterable von Token‑Objekten mit ``notes`` (Liste von
        ``Note``). Token ohne Noten werden als stumme, sehr kurze
        Segmente behandelt.
    :param tempo: Tempo in BPM.
    :return: Liste von (start_sec, end_sec) in Sekunden.
    """
    timings: List[Tuple[float, float]] = []
    current_time = 0.0
    beat_sec = 60.0 / tempo  # Sekunde pro Viertelnote
    for tok in tokens:
        notes = getattr(tok, 'notes', None)
        if not notes:
            # Stilles Token: minimale Länge
            length = 0.1
        else:
            total_dur = 0.0
            for note in notes:
                total_dur += note.duration * beat_sec
            length = total_dur
        start = current_time
        end = current_time + length
        timings.append((start, end))
        current_time = end
    return timings

__all__ = ["compute_timing"]