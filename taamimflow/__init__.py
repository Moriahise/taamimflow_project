"""
Top‑level package for Ta'amimFlow.

This package provides the high‑level entry points for the cantillation and
audio subsystems alongside the existing GUI and configuration helpers.  It
exposes a minimal API so that callers do not have to delve into internal
submodules.  Most of the heavy lifting lives in the ``core`` and ``audio``
packages.

Example usage::

    from taamimflow import AppConfig, MainWindow
    from taamimflow import extract_tokens_with_notes
    from taamimflow import AudioEngine

    # load configuration
    cfg = AppConfig.load()
    
    # perform cantillation analysis
    tokens = extract_tokens_with_notes("בראשית ברא אלהים")

    # play the note sequence via the default audio engine
    engine = AudioEngine()
    audio_segment = engine.synthesise([note for token in tokens for note in token.notes])
    engine.play(audio_segment)

The API surface intentionally re‑exports only a handful of symbols to
keep the namespace tidy.  If you need lower‑level functionality, import
directly from the subpackages (``taamimflow.core`` or ``taamimflow.audio``).
"""

from .config import AppConfig, get_app_config  # noqa: F401
from .connectors import get_default_connector  # noqa: F401
from .gui.main_window import MainWindow  # noqa: F401

# Re‑export selected high‑level functions and classes from the new core/audio packages.
try:
    # Cantillation extraction pipeline
    from .core.cantillation import extract_tokens_with_notes, TokenFull  # type: ignore[F401]
except Exception:
    # The core package may not be installed yet; ignore import errors during partial installs.
    extract_tokens_with_notes = None  # type: ignore
    TokenFull = None  # type: ignore

try:
    # Audio synthesis engines
    from .audio.audio_engine import AudioEngine  # type: ignore[F401]
    from .audio.concat_audio import ConcatAudioEngine  # type: ignore[F401]
except Exception:
    AudioEngine = None  # type: ignore
    ConcatAudioEngine = None  # type: ignore

__all__ = [
    "AppConfig",
    "get_app_config",
    "get_default_connector",
    "MainWindow",
    "extract_tokens_with_notes",
    "TokenFull",
    "AudioEngine",
    "ConcatAudioEngine",
]