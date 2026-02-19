"""
Modernised Audio Utility Module
===============================

High-level audio interface for Ta'amimFlow's simplified GUI.
Delegates synthesis and playback to the robust Qt6-compatible engine in
:mod:`taamimflow.audio.audio_engine`.  No pydub or external media
players are required for note playback – only ``PyQt6``.

Key features:

* **Real sound generation** via sine-wave synthesis.
* **Non-blocking playback** via ``QAudioSink`` (Qt6).
* **File playback** via pydub when available; OS default handler otherwise.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Iterable, Tuple, List

try:
    from pydub import AudioSegment  # type: ignore
    HAVE_PYDUB = True
except Exception:
    HAVE_PYDUB = False
    AudioSegment = None  # type: ignore

# Import the Qt6-compatible sine-wave engine and Note class.
from ..audio.audio_engine import AudioEngine as _SineEngine, Note


class AudioEngine:
    """High-level audio engine for simplified GUIs.

    Wraps :class:`~taamimflow.audio.audio_engine.AudioEngine` to provide
    convenient methods for playing note sequences or pre-recorded files.
    Synthesis and playback work without pydub; only ``PyQt6`` is required.
    """

    def __init__(self) -> None:
        self._engine = _SineEngine()

    def initialise(self) -> None:
        """Deferred setup – kept for API compatibility, does nothing."""
        pass

    def play_notes(
        self,
        notes: Iterable[Tuple[str, float]],
        tempo: float = 120.0,
        volume: float = 0.8,
    ) -> None:
        """Synthesise and play a sequence of notes.

        :param notes: Iterable of ``(pitch, duration)`` tuples.  Pitch can
            be a MIDI number or note name (e.g. "C4"); duration is in
            quarter-note beats relative to *tempo*.
        :param tempo: Tempo in BPM.  Defaults to 120 BPM.
        :param volume: Volume 0.0–1.0.  Defaults to 0.8.

        Converts input tuples into :class:`Note` instances and synthesises
        via the underlying engine.  Errors are suppressed to keep the UI
        responsive.
        """
        note_objs: List[Note] = []
        for pitch, duration in notes:
            note_objs.append(Note(pitch, duration))
        try:
            pcm = self._engine.synthesise(note_objs, tempo=tempo, volume=volume)
            # play() accepts QByteArray, bytes, or AudioSegment – all handled
            self._engine.play(pcm)
        except Exception:
            return

    def play_audio_file(self, path: str) -> None:
        """Play a pre-recorded audio file.

        Attempts to load via pydub and play through the underlying engine.
        Falls back to the OS default media player if pydub is unavailable
        or the file cannot be decoded.
        """
        try:
            if HAVE_PYDUB:
                seg = AudioSegment.from_file(path)  # type: ignore
                self._engine.play(seg)
                return
        except Exception:
            pass
        # Fallback: open with system default application
        try:
            if sys.platform == 'win32':
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception:
            return
