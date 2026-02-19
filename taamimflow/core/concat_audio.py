"""
Concatenation-basierte Audio-Engine
===================================

FIX V10:
* Relativer Import: ``from .audio_engine import Note, AudioEngine``
* ``ConcatAudioEngine.__init__`` akzeptiert jetzt ``tradition`` als ersten
  Parameter – kompatibel mit dem Aufruf in ``main_window._get_audio_engine``.
* ``synthesise(notes, tempo, volume)`` und ``play(segment)`` Methoden
  hinzugefügt – gemeinsame Schnittstelle mit ``AudioEngine``.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Union

try:
    from pydub import AudioSegment  # type: ignore
    HAVE_PYDUB = True
except Exception:
    AudioSegment = None  # type: ignore
    HAVE_PYDUB = False

# Relativer Import (Fix P4)
from .audio_engine import Note, AudioEngine


@dataclass
class SegmentMap:
    """Mapping einer Trope oder Note zu einem Audio-Segment.

    Keys repräsentieren entweder Tropen-Gruppenamen (kanonisch) oder
    spezielle Kontext-IDs. Values sind Pfade zu Audio-Dateien.
    """
    mapping: Dict[str, str]


class ConcatAudioEngine:
    """Audio-Engine mit Segment-Concatenation und Crossfade.

    Gemeinsame Schnittstelle (für ``main_window`` / ``_AudioWorker``)::

        segment = engine.synthesise(notes, tempo=120.0, volume=0.8)
        engine.play(segment)

    FIX V10: Der Konstruktor akzeptiert jetzt ``tradition`` als ersten
    Parameter.  ``segment_maps`` ist optional (default: leeres Dict).
    """

    def __init__(
        self,
        tradition: str = "Sephardi",
        segment_maps: Optional[Dict[str, SegmentMap]] = None,
        crossfade_ms: int = 20,
    ) -> None:
        """Initialisiert die Engine.

        :param tradition: Name der Tradition (z.B. "Sephardi", "Ashkenazi").
            Wird als Default-Stil für ``synthesise`` verwendet.
        :param segment_maps: Optional – Dictionary, das pro Stil eine
            ``SegmentMap`` mit Pfaden zu voraufgezeichneten Segmenten
            bereitstellt.  Wenn leer oder ein Segment nicht gefunden
            wird, fällt die Engine auf den Sinus-Generator zurück.
        :param crossfade_ms: Dauer der Übergänge zwischen Segmenten in ms.
        """
        self.tradition = tradition
        self.segment_maps: Dict[str, SegmentMap] = segment_maps or {}
        self.crossfade_ms = crossfade_ms
        self._sine_engine = AudioEngine()

    # ------------------------------------------------------------------
    # Gemeinsame Schnittstelle (V10)
    # ------------------------------------------------------------------

    def synthesise(
        self,
        notes: Iterable,
        tempo: float = 120.0,
        volume: float = 0.8,
    ) -> Optional['AudioSegment']:
        """Erzeuge ein ``AudioSegment`` für die Notensequenz.

        Versucht zuerst voraufgezeichnete Segmente zu verwenden.
        Fällt auf Sinus-Generator zurück wenn keine Segmente verfügbar.

        :param notes: Iterable von ``Note``-Objekten oder Token-artigen
            Objekten (mit ``notes`` und ``group`` Attributen).
        :param tempo: Tempo in BPM.
        :param volume: Lautstärke 0.0–1.0.
        :return: ``AudioSegment`` oder ``None`` wenn pydub fehlt.
        """
        seg = self.tokens_to_audio(notes, style=self.tradition, tempo=tempo)
        if seg is not None and HAVE_PYDUB and volume != 1.0:
            gain_db = 20.0 * math.log10(max(volume, 0.0001))
            seg = seg.apply_gain(gain_db)
        return seg

    def play(self, segment: Optional['AudioSegment']) -> None:
        """Spiele ein ``AudioSegment`` sofort ab.

        Benötigt ``pydub.playback`` und ein Playback-Backend.
        Fehler werden still ignoriert (kein Absturz der GUI).
        """
        if not HAVE_PYDUB or segment is None:
            return
        try:
            from pydub.playback import play as _play  # type: ignore
            _play(segment)
        except Exception:
            pass  # Playback-Backend fehlt – kein Absturz

    # ------------------------------------------------------------------
    # Interne Methoden (unverändert, relativer Import gefixt)
    # ------------------------------------------------------------------

    def _load_segment(self, path: str) -> Optional['AudioSegment']:
        if not HAVE_PYDUB:
            return None
        if not os.path.isfile(path):
            return None
        try:
            return AudioSegment.from_file(path)  # type: ignore
        except Exception:
            return None

    def token_to_segment(
        self,
        token: Union[Note, object],
        style: str,
    ) -> Optional['AudioSegment']:
        """Wandle einen Note oder Token in ein AudioSegment um."""
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
        """Kombiniere eine Sequenz von Tokens zu einem AudioSegment."""
        if not HAVE_PYDUB:
            # Fallback: generiere komplette Sequenz via AudioEngine
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
            output = output.append(seg, crossfade=self.crossfade_ms)
        return output

    def save(
        self,
        segment: 'AudioSegment',
        filename: str,
        format: str = 'wav',
    ) -> None:
        """Speichere ein AudioSegment in eine Datei."""
        if not HAVE_PYDUB:
            raise RuntimeError("pydub ist nicht verfügbar.")
        if segment is None:
            raise ValueError("segment darf nicht None sein")
        segment.export(filename, format=format)


__all__ = ["SegmentMap", "ConcatAudioEngine"]
