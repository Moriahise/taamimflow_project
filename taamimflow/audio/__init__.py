"""
Audio synthesis engines for Ta'amimFlow.

This subpackage provides classes for converting cantillation note
sequences into playable audio.  Multiple engines are available:

* :class:`AudioEngine` – a minimal sinusoid generator that creates
  artificial tones for each note.  Suitable for early prototyping.

* :class:`ConcatAudioEngine` – a professional concatenative engine that
  stitches together pre‑recorded samples of cantillation motifs.  It
  supports crossfading, per‑tradition samples and tempo scaling.

Additional helper functions and data structures live in
``tradition_profiles`` and ``utils``.  The top‑level API expects
engines to implement a common interface::

    engine = AudioEngine()  # or ConcatAudioEngine(tradition="Ashkenazi")
    segment = engine.synthesise(notes, tempo=120, volume=0.8)
    engine.play(segment)

Note that the audio subsystem relies on external dependencies such as
``pydub`` and ``ffmpeg``.  See the installation guide for details.
"""

from .audio_engine import AudioEngine  # noqa: F401
from .concat_audio import ConcatAudioEngine  # noqa: F401

# Optionally expose tradition metadata if available.
try:
    from .tradition_profiles import get_tradition_profiles  # type: ignore[F401]
except Exception:
    get_tradition_profiles = None  # type: ignore

__all__ = [
    "AudioEngine",
    "ConcatAudioEngine",
    "get_tradition_profiles",
]