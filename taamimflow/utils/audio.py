"""
Modernised Audio Utility Module
===============================

This module provides a high‑level audio interface for TaamimFlow’s
simplified GUI.  The previous implementation was a skeletal placeholder
that merely slept for the duration of the requested notes and raised a
``NotImplementedError`` when asked to play a file.  As a result, the
application appeared to freeze and produced no sound on playback.  To
address these issues the new ``AudioEngine`` delegates synthesis and
playback to the robust engine in :mod:`taamimflow.audio.audio_engine`.

Key features:

* **Real sound generation** using sine‑wave synthesis via pydub.  Each
  note in the provided sequence is converted into a :class:`~taamimflow.audio.audio_engine.Note` and
  synthesised into an :class:`pydub.AudioSegment` with correct tempo.
* **Non‑blocking playback** courtesy of the underlying engine.  While
  this class itself does not manage threads, the calling GUI should
  invoke playback on a worker thread as already implemented in the
  full ``main_window``.  The internal engine uses multiple
  fallbacks (pydub, winsound, pygame, ffplay, system media player) to
  maximise compatibility.
* **File playback** using pydub when available, with graceful fallback
  to launching the file via the operating system’s default media
  handler if pydub cannot decode the file.

With these improvements the simplified GUI can now produce audible
feedback without blocking the user interface, provided the user has
installed at least one of the supported audio backends (``simpleaudio``,
``pygame``, ``ffplay``, etc.).

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

# Import the robust sine‑wave engine and Note class from the core audio module.
from ..audio.audio_engine import AudioEngine as _SineEngine, Note


class AudioEngine:
    """High‑level audio engine for simplified GUIs.

    This class wraps the core :class:`~taamimflow.audio.audio_engine.AudioEngine` to
    provide convenient methods for playing sequences of notes or
    pre‑recorded audio files.  It performs no initialisation of audio
    devices itself; all heavy lifting is delegated to the underlying
    engine.  The calling code is responsible for invoking playback on
    a background thread if necessary to avoid blocking the GUI.
    """

    def __init__(self) -> None:
        # Underlying engine used for synthesis and playback
        self._engine = _SineEngine()

    def initialise(self) -> None:
        """Perform any deferred setup required for playback.

        The underlying engine performs no initialisation, so this
        method exists for API compatibility and does nothing.
        """
        # No explicit initialisation required; kept for backward compatibility.
        pass

    def play_notes(self, notes: Iterable[Tuple[str, float]], tempo: float = 120.0, volume: float = 0.8) -> None:
        """Synthesize and play a sequence of notes.

        :param notes: Iterable of tuples ``(pitch, duration)``.  Pitch can
            be a MIDI number or note name (e.g. "C4"), duration is in
            beats relative to a quarter note.  Durations are interpreted
            according to the given tempo.
        :param tempo: Tempo in beats per minute.  Defaults to 120 BPM.
        :param volume: Volume level from 0.0 to 1.0.  Defaults to 0.8.

        The sequence is converted into :class:`Note` instances and
        synthesised via the underlying engine.  Playback is delegated
        to that engine’s :meth:`play` method which handles multiple
        fallbacks.  Errors during synthesis or playback are suppressed
        to prevent UI freezes.
        """
        # Convert input tuples into Note objects
        note_objs: List[Note] = []
        for pitch, duration in notes:
            note_objs.append(Note(pitch, duration))
        try:
            seg = self._engine.synthesise(note_objs, tempo=tempo, volume=volume)
            # ``play`` will silently return if seg is None or audio backend is missing
            self._engine.play(seg)
        except Exception:
            # If anything goes wrong (e.g. invalid pitch, missing pydub), we
            # simply return without raising.  The GUI should remain responsive.
            return

    def play_audio_file(self, path: str) -> None:
        """Play a pre‑recorded audio file.

        :param path: Filesystem path to the audio file.  Supported formats
            depend on pydub’s decoders (typically WAV, MP3, etc.).

        Attempts to load the file via pydub and play it using the
        underlying engine.  If pydub is not available or the file
        cannot be decoded, the method falls back to launching the
        operating system’s default media player.  All exceptions are
        suppressed.
        """
        try:
            if HAVE_PYDUB:
                # Try to decode with pydub
                seg = AudioSegment.from_file(path)  # type: ignore
                self._engine.play(seg)
                return
        except Exception:
            # Fall back to OS handler below
            pass
        # Fallback: open the file with the system default application
        try:
            if sys.platform == 'win32':
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception:
            # Last resort: do nothing on failure
            return