"""Audio utility functions for Ta'amimFlow.

This module contains helper functions for the audio package such as
loading audio samples, scaling volume, and audio format utilities.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

try:
    from pydub import AudioSegment  # type: ignore
    HAVE_PYDUB = True
except Exception:
    AudioSegment = None  # type: ignore
    HAVE_PYDUB = False


def db_from_linear(volume: float) -> float:
    """Convert a linear volume factor (0.0–1.0) to dBFS gain.

    :param volume: Linear factor where 1.0 = unity gain.
    :return: Gain in dB (negative for volumes < 1.0).
    """
    return 20.0 * math.log10(max(volume, 0.0001))


def apply_volume(segment: 'AudioSegment', volume: float) -> 'AudioSegment':
    """Apply a linear volume factor to an AudioSegment.

    :param segment: Source AudioSegment.
    :param volume: Linear factor (0.0–1.0).
    :return: New AudioSegment with adjusted volume.
    """
    if not HAVE_PYDUB or segment is None:
        return segment
    gain = db_from_linear(volume)
    return segment.apply_gain(gain)


def load_audio_file(path: str | Path) -> Optional['AudioSegment']:
    """Load an audio file via pydub.

    :param path: Path to the audio file (WAV, MP3, etc.).
    :return: AudioSegment or None if pydub is unavailable or file not found.
    """
    if not HAVE_PYDUB:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return AudioSegment.from_file(str(p))  # type: ignore
    except Exception:
        return None


__all__ = ["db_from_linear", "apply_volume", "load_audio_file"]
