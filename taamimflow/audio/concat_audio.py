"""
Concatenation‑based Audio Engine with Enhanced Playback
======================================================

This module provides an audio engine that concatenates pre‑recorded
cantillation segments with crossfades.  It closely mirrors the
implementation from the original TaamimFlow repository but has been
updated to use the new :class:`~taamimflow.audio.audio_engine.AudioEngine`
for all audio output.  In earlier versions
``ConcatAudioEngine.play`` relied on ``pydub.playback.play()`` and a
chain of external back‑end players (winsound, ffplay, system media
players), which often failed silently or blocked the GUI when audio
back‑ends were not installed.  The current version converts any
:class:`pydub.AudioSegment` into raw PCM bytes and passes them to
the underlying sine engine’s :meth:`play` method.  Playback is
therefore non‑blocking and depends only on QtMultimedia (no external
players or libraries required).

The synthesise functionality remains unchanged and still attempts to
assemble segments from the provided ``segment_maps`` using pydub
when available.  When no pre‑recorded segment is available for a
given trope group, it falls back to synthesising sine waves via
the internal AudioEngine.

"""

from __future__ import annotations

import math
import os
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Union

from .audio_logger import configure_audio_logger

# Ensure file logging is active as early as possible.
configure_audio_logger()
logger = logging.getLogger(__name__)

try:
    # Pydub wird optional verwendet, um voraufgezeichnete Segmente zu laden
    from pydub import AudioSegment  # type: ignore
    HAVE_PYDUB = True
except Exception:
    AudioSegment = None  # type: ignore
    HAVE_PYDUB = False

# Relative import for Note and the robust AudioEngine
from .audio_engine import Note, AudioEngine as _SineEngine


@dataclass
class SegmentMap:
    """Mapping of trope groups or context IDs to audio file paths."""
    mapping: Dict[str, str]


class ConcatAudioEngine:
    """Audio engine with segment concatenation and crossfade.

    This engine supports a common interface used by the GUI: call
    :meth:`synthesise` to obtain an :class:`pydub.AudioSegment` for a
    sequence of tokens or notes, then call :meth:`play` to play the
    segment.  It first attempts to use pre‑recorded audio clips
    provided via ``segment_maps`` keyed by cantillation tradition (e.g.
    "Sephardi", "Ashkenazi").  When a segment cannot be loaded, the
    engine falls back to a sine‑wave synthesis using the underlying
    :class:`~taamimflow.audio.audio_engine.AudioEngine`.
    """

    def __init__(
        self,
        tradition: str = "Sephardi",
        segment_maps: Optional[Dict[str, SegmentMap]] = None,
        crossfade_ms: int = 20,
    ) -> None:
        """Initialise the concatenation engine.

        :param tradition: Default tradition used when synthesising audio
            if no tradition is explicitly passed.  Defaults to
            "Sephardi".
        :param segment_maps: Optional mapping of tradition names to
            :class:`SegmentMap` instances.  If empty or a segment is
            missing, the engine falls back to sine synthesis.
        :param crossfade_ms: Duration of crossfades between segments in
            milliseconds.  Default is 20ms.
        """
        self.tradition = tradition
        self.segment_maps: Dict[str, SegmentMap] = segment_maps or {}
        self.crossfade_ms = crossfade_ms
        # Use a robust sine engine for synthesis and playback
        self._sine_engine = _SineEngine()
        logger.info(
            "ConcatAudioEngine Startup: tradition=%s crossfade_ms=%d pydub=%s",
            self.tradition,
            self.crossfade_ms,
            HAVE_PYDUB,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def synthesise(
        self,
        notes: Iterable,
        tempo: float = 120.0,
        volume: float = 0.8,
    ) -> Optional['AudioSegment']:
        """Create an AudioSegment for a sequence of tokens or notes.

        Attempts to stitch together pre‑recorded segments based on
        tropes and group names defined in ``segment_maps``.  If no
        segments are available or pydub is missing, falls back to
        synthesising sine waves for each note.  An optional volume
        adjustment (0.0–1.0) is applied if pydub is available.
        """
        note_list = list(notes)
        logger.debug(
            "ConcatAudioEngine.synthesise: start items=%d tempo=%.2f volume=%.2f",
            len(note_list),
            tempo,
            volume,
        )
        seg = self.tokens_to_audio(note_list, style=self.tradition, tempo=tempo)
        if seg is not None and HAVE_PYDUB and volume != 1.0:
            gain_db = 20.0 * math.log10(max(volume, 0.0001))
            seg = seg.apply_gain(gain_db)
        logger.debug(
            "ConcatAudioEngine.synthesise: done segment=%s",
            "yes" if seg is not None else "no",
        )
        return seg

    def play(self, segment: Optional['AudioSegment']) -> None:
        """Play an AudioSegment using the underlying sine engine.

        Statt ``pydub.playback.play()`` zu nutzen (das externe Backends
        und ffmpeg erfordert), wird das Segment in das interne
        PCM‑Format der SineEngine konvertiert und über ``AudioEngine.play``
        abgespielt.  Wenn ``segment`` ``None`` oder pydub nicht
        verfügbar ist, passiert nichts.
        """
        if not HAVE_PYDUB or segment is None:
            logger.debug(
                "ConcatAudioEngine.play: skip – pydub=%s segment=%s",
                HAVE_PYDUB,
                "None" if segment is None else "yes",
            )
            return
        try:
            # Auf Ziel‑Format normieren: 16 bit, 44.1 kHz, Mono
            seg = segment.set_frame_rate(self._sine_engine._sample_rate).set_channels(1).set_sample_width(2)
            pcm_bytes = seg.raw_data  # type: ignore
            logger.info("ConcatAudioEngine.play: playing %d bytes", len(pcm_bytes))
            # ByteArray oder bytes an play() übergeben
            self._sine_engine.play(pcm_bytes)
        except Exception as exc:
            # Fehler unterdrücken, um GUI nicht zu blockieren
            logger.exception("ConcatAudioEngine.play: error: %s", exc)
            return

    # ------------------------------------------------------------------
    # Internal helper methods
    # ------------------------------------------------------------------
    def _load_segment(self, path: str) -> Optional['AudioSegment']:
        """Attempt to load an audio file into an AudioSegment."""
        if not HAVE_PYDUB:
            logger.debug("_load_segment: pydub nicht verfügbar")
            return None
        if not os.path.isfile(path):
            logger.debug("_load_segment: Datei nicht gefunden: %s", path)
            return None
        try:
            seg = AudioSegment.from_file(path)  # type: ignore
            logger.debug("_load_segment: geladen: %s", path)
            return seg
        except Exception as exc:
            logger.exception("_load_segment: Fehler beim Laden %s: %s", path, exc)
            return None

    def token_to_segment(
        self,
        token: Union[Note, object],
        style: str,
    ) -> Optional['AudioSegment']:
        """Convert a single token or Note into an AudioSegment."""
        if isinstance(token, Note):
            return self._sine_engine.generate_audio_segment([token])
        group = getattr(token, 'group_name', getattr(token, 'group', None))
        notes = getattr(token, 'notes', None)
        if group and style in self.segment_maps:
            seg_map = self.segment_maps[style].mapping
            file_path = seg_map.get(group)
            if file_path:
                seg = self._load_segment(file_path)
                if seg:
                    return seg
        if notes:
            return self._sine_engine.generate_audio_segment(notes)
        return None

    def tokens_to_audio(
        self,
        tokens: Iterable,
        style: str = '',
        tempo: float = 120.0,
    ) -> Optional['AudioSegment']:
        """Combine a sequence of tokens into a single AudioSegment."""
        if not HAVE_PYDUB:
            # Fallback: synthesise the entire sequence using the sine engine
            combined_notes: List[Note] = []
            for tok in tokens:
                if isinstance(tok, Note):
                    combined_notes.append(tok)
                else:
                    ns = getattr(tok, 'notes', None)
                    if ns:
                        combined_notes.extend(ns)
            return self._sine_engine.generate_audio_segment(combined_notes, tempo)
        segments: List['AudioSegment'] = []
        for tok in tokens:
            seg = self.token_to_segment(tok, style)
            if seg:
                segments.append(seg)
        if not segments:
            return None
        output = segments[0]
        for seg in segments[1:]:
            # Use pydub’s append with crossfade
            output = output.append(seg, crossfade=self.crossfade_ms)
        return output

    def save(
        self,
        segment: 'AudioSegment',
        filename: str,
        format: str = 'wav',
    ) -> None:
        """Save an AudioSegment to a file."""
        if not HAVE_PYDUB:
            raise RuntimeError("pydub is not available.")
        if segment is None:
            raise ValueError("segment must not be None")
        segment.export(filename, format=format)


__all__ = ["SegmentMap", "ConcatAudioEngine"]