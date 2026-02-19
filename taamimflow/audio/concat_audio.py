"""
Concatenation-based Audio Engine with Enhanced Playback
======================================================

This module provides an audio engine that concatenates pre-recorded
cantillation segments with crossfades.  It closely mirrors the
implementation from the original TaamimFlow repository but has been
updated to use the new :class:`~taamimflow.audio.audio_engine.AudioEngine`
for all audio output.

**Pydub-free operation (KEY FIX):**
When pydub is not installed, all paths fall back to the underlying
:class:`~taamimflow.audio.audio_engine.AudioEngine` which synthesises
PCM via Qt-only sine waves.  ``synthesise`` returns a ``QByteArray``
in this case, and ``play`` forwards it directly to the sine engine
without touching any pydub API.  This means the engine is fully
functional with only ``PyQt6`` installed.

When pydub *is* available, the engine attempts to assemble pre-recorded
segments from ``segment_maps`` with crossfades, falling back to sine
synthesis for missing segments.
"""

from __future__ import annotations

import math
import os
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Union

from .audio_logger import configure_audio_logger

configure_audio_logger()
logger = logging.getLogger(__name__)

try:
    from pydub import AudioSegment  # type: ignore
    HAVE_PYDUB = True
except Exception:
    AudioSegment = None  # type: ignore
    HAVE_PYDUB = False

# Relative import for Note and the robust AudioEngine
from .audio_engine import Note, AudioEngine as _SineEngine

# Try to import QByteArray for isinstance checks in play()
try:
    from PyQt6.QtCore import QByteArray as _QByteArray
    _HAVE_QBYTEARRAY = True
except Exception:
    _QByteArray = None  # type: ignore
    _HAVE_QBYTEARRAY = False


@dataclass
class SegmentMap:
    """Mapping of trope groups or context IDs to audio file paths."""
    mapping: Dict[str, str]


class ConcatAudioEngine:
    """Audio engine with segment concatenation and crossfade.

    Supports two operating modes:

    **With pydub:** Stitches pre-recorded audio clips from
    ``segment_maps`` with crossfades.  Falls back to sine-wave
    synthesis for missing segments.

    **Without pydub (Qt-only):** Synthesises sine-wave PCM directly via
    the underlying ``AudioEngine``.  ``synthesise`` returns a
    ``QByteArray``; ``play`` forwards it to ``AudioEngine.play``.
    No pydub calls are made.
    """

    def __init__(
        self,
        tradition: str = "Sephardi",
        segment_maps: Optional[Dict[str, SegmentMap]] = None,
        crossfade_ms: int = 20,
    ) -> None:
        self.tradition = tradition
        self.segment_maps: Dict[str, SegmentMap] = segment_maps or {}
        self.crossfade_ms = crossfade_ms
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
    ) -> Optional[Union["AudioSegment", bytes]]:
        """Create audio for a sequence of tokens or notes.

        Returns an ``AudioSegment`` when pydub is available, or raw PCM
        bytes (``QByteArray`` / ``bytes``) when it is not.  Either type
        is accepted by :meth:`play`.

        :param notes: Iterable of ``Note`` objects or token objects with
            a ``notes`` attribute.
        :param tempo: Playback tempo in BPM.
        :param volume: Volume 0.0–1.0.
        """
        note_list = list(notes)
        logger.debug(
            "ConcatAudioEngine.synthesise: start items=%d tempo=%.2f volume=%.2f",
            len(note_list),
            tempo,
            volume,
        )

        seg = self.tokens_to_audio(note_list, style=self.tradition, tempo=tempo)

        # Apply volume only when we have a real AudioSegment
        if seg is not None and HAVE_PYDUB and isinstance(seg, AudioSegment) and volume != 1.0:
            gain_db = 20.0 * math.log10(max(volume, 0.0001))
            seg = seg.apply_gain(gain_db)

        logger.debug(
            "ConcatAudioEngine.synthesise: done type=%s",
            type(seg).__name__ if seg is not None else "None",
        )
        return seg

    def play(self, segment: Optional[Union["AudioSegment", bytes]]) -> None:
        """Play audio returned by :meth:`synthesise`.

        Accepts:
        * ``pydub.AudioSegment`` – converted to PCM and played via Qt.
        * ``QByteArray`` / ``bytes`` / ``bytearray`` – played directly.
        * ``None`` – silently ignored.

        All playback is delegated to the underlying sine engine's
        :meth:`~AudioEngine.play` method which uses ``QAudioSink``
        for non-blocking output.
        """
        if segment is None:
            logger.debug("ConcatAudioEngine.play: segment is None – skipping")
            return

        # --- Case 1: QByteArray from Qt (no-pydub synthesise path) ---
        if _HAVE_QBYTEARRAY and isinstance(segment, _QByteArray):
            logger.info("ConcatAudioEngine.play: QByteArray path (%d bytes)", len(segment))
            self._sine_engine.play(segment)
            return

        # --- Case 2: raw bytes / bytearray ---
        if isinstance(segment, (bytes, bytearray)):
            logger.info("ConcatAudioEngine.play: bytes path (%d bytes)", len(segment))
            self._sine_engine.play(bytes(segment))
            return

        # --- Case 3: pydub AudioSegment ---
        if not HAVE_PYDUB:
            logger.debug("ConcatAudioEngine.play: pydub unavailable and segment is not bytes – skipping")
            return
        try:
            seg = (
                segment
                .set_frame_rate(self._sine_engine._sample_rate)
                .set_channels(1)
                .set_sample_width(2)
            )
            pcm_bytes = seg.raw_data  # type: ignore
            logger.info("ConcatAudioEngine.play: AudioSegment path (%d bytes)", len(pcm_bytes))
            self._sine_engine.play(pcm_bytes)
        except Exception as exc:
            logger.exception("ConcatAudioEngine.play: error: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_segment(self, path: str) -> Optional["AudioSegment"]:
        """Attempt to load an audio file into an AudioSegment."""
        if not HAVE_PYDUB:
            return None
        if not os.path.isfile(path):
            logger.debug("_load_segment: file not found: %s", path)
            return None
        try:
            seg = AudioSegment.from_file(path)  # type: ignore
            logger.debug("_load_segment: loaded: %s", path)
            return seg
        except Exception as exc:
            logger.exception("_load_segment: error loading %s: %s", path, exc)
            return None

    def token_to_segment(
        self,
        token: Union[Note, object],
        style: str,
    ) -> Optional[Union["AudioSegment", bytes]]:
        """Convert a single token or Note into audio.

        Returns an ``AudioSegment`` when pydub is available, or a
        ``QByteArray`` / ``bytes`` otherwise.
        """
        if isinstance(token, Note):
            if HAVE_PYDUB:
                return self._sine_engine.generate_audio_segment([token])
            else:
                # No pydub → use synthesise which returns QByteArray
                return self._sine_engine.synthesise([token])

        group = getattr(token, 'group_name', getattr(token, 'group', None))
        notes = getattr(token, 'notes', None)

        # Try segment map first (pydub only)
        if HAVE_PYDUB and group and style in self.segment_maps:
            seg_map = self.segment_maps[style].mapping
            file_path = seg_map.get(group)
            if file_path:
                seg = self._load_segment(file_path)
                if seg:
                    return seg

        if notes:
            note_list = list(notes)
            if HAVE_PYDUB:
                return self._sine_engine.generate_audio_segment(note_list)
            else:
                return self._sine_engine.synthesise(note_list)

        return None

    def tokens_to_audio(
        self,
        tokens: Iterable,
        style: str = '',
        tempo: float = 120.0,
    ) -> Optional[Union["AudioSegment", bytes]]:
        """Combine a sequence of tokens into a single audio object.

        Without pydub, collects all ``Note`` objects and synthesises
        them in one call via :meth:`~AudioEngine.synthesise`, returning
        a ``QByteArray``.  Crossfades are skipped in this mode.

        With pydub, stitches together ``AudioSegment`` objects with
        the configured crossfade.
        """
        token_list = list(tokens)

        if not HAVE_PYDUB:
            # ── Qt-only (no pydub) path ────────────────────────────────
            combined_notes: List[Note] = []
            for tok in token_list:
                if isinstance(tok, Note):
                    combined_notes.append(tok)
                else:
                    ns = getattr(tok, 'notes', None)
                    if ns:
                        combined_notes.extend(list(ns))
            if not combined_notes:
                logger.debug("tokens_to_audio (no-pydub): no notes found in %d tokens", len(token_list))
                return None
            logger.debug(
                "tokens_to_audio (no-pydub): synthesising %d notes at %.1f BPM",
                len(combined_notes),
                tempo,
            )
            # synthesise() → QByteArray (Qt PCM)
            return self._sine_engine.synthesise(combined_notes, tempo=tempo)

        # ── pydub path ─────────────────────────────────────────────────
        segments: List["AudioSegment"] = []
        for tok in token_list:
            seg = self.token_to_segment(tok, style)
            if seg is not None and isinstance(seg, AudioSegment):
                segments.append(seg)
        if not segments:
            return None
        output = segments[0]
        for seg in segments[1:]:
            output = output.append(seg, crossfade=self.crossfade_ms)
        return output

    def save(
        self,
        segment: "AudioSegment",
        filename: str,
        format: str = 'wav',
    ) -> None:
        """Save an AudioSegment to a file (requires pydub)."""
        if not HAVE_PYDUB:
            raise RuntimeError("pydub is not available.")
        if segment is None:
            raise ValueError("segment must not be None")
        segment.export(filename, format=format)


__all__ = ["SegmentMap", "ConcatAudioEngine"]
