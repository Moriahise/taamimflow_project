"""Ta'amimFlow audio package.

Exports the audio engine classes so that the GUI can import from
``taamimflow.audio`` without knowing internal module names.

Both engines implement the common interface::

    engine.synthesise(notes, tempo=120.0, volume=0.8) -> AudioSegment | None
    engine.play(segment) -> None

Example::

    from taamimflow.audio import AudioEngine, ConcatAudioEngine
"""

from .audio_engine import AudioEngine, Note

try:
    from .concat_audio import ConcatAudioEngine
    _HAS_CONCAT = True
except ImportError:
    ConcatAudioEngine = None  # type: ignore[assignment,misc]
    _HAS_CONCAT = False

__all__ = [
    "AudioEngine",
    "Note",
    "ConcatAudioEngine",
]
