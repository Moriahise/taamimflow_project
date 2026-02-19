"""
Concatenation‑basierte Audio‑Engine
===================================

Dieses Modul stellt einen erweiterten Ansatz zur Audiowiedergabe für
Cantillation‑Sequenzen bereit. Es geht über die einfache
Sinusgenerator‑Methode aus ``audio_engine.py`` hinaus und erlaubt,
melodische Segmente pro Tradition als voraufgezeichnete Dateien zu
konkatenierren. Darüber hinaus unterstützt es Crossfading zwischen
Segmenten, um einen natürlichen Klangfluss zu erzeugen.

Da die tatsächlichen Aufnahmen der Cantillation‑Melodien und die
Zuordnung von Tropen zu Audio‑Dateien nicht Teil dieses Projekts
enthalten sind, verwendet diese Engine fallback‑Generierung mittels
Sinuswellen (über ``audio_engine.AudioEngine``). Sie ist modular
aufgebaut, so dass echte Aufnahmen später einfach eingesteckt werden
können.

Beispiel:

    from milestone9_plus import extract_tokens_with_notes
    from concat_audio import ConcatAudioEngine

    tokens = extract_tokens_with_notes(text, tropedef_path)
    engine = ConcatAudioEngine({'ashkenazic_binder': '/path/to/segments'})
    segment = engine.tokens_to_audio(tokens, style='ashkenazic_binder')
    engine.save(segment, 'out.wav')

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Union

import os

try:
    from pydub import AudioSegment  # type: ignore
    HAVE_PYDUB = True
except Exception:
    AudioSegment = None  # type: ignore
    HAVE_PYDUB = False

from audio_engine import Note, AudioEngine

@dataclass
class SegmentMap:
    """Mapping einer Trope oder Note zu einem Audio‑Segment.

    Dieses Dataclass dient als Container für vorkonfigurierte
    Audiodateien, die pro Tradition geladen werden können. Keys
    repräsentieren entweder Tropen‑Gruppenamen (kanonisch) oder
    spezielle Kontext‑IDs. Die Values sind Pfade zu Audio‑Dateien,
    die von pydub geladen werden können.
    """
    mapping: Dict[str, str]


class ConcatAudioEngine:
    """Audio‑Engine mit Segment‑Concatenation und Crossfade.

    Diese Engine versucht für jede Tropen‑Gruppe eines Tokens ein
    voraufgezeichnetes Audio‑Segment aus ``segment_map`` zu laden. Wenn
    kein Segment vorhanden ist oder ``pydub`` nicht verfügbar ist,
    wird als Fallback der Sinusgenerator aus ``audio_engine.AudioEngine``
    verwendet. Alle Segmente werden hintereinander kombiniert. Eine
    optionale Crossfade‑Länge kann gesetzt werden, um Übergänge weicher
    zu gestalten.
    """

    def __init__(self, segment_maps: Dict[str, SegmentMap], crossfade_ms: int = 20) -> None:
        """Initialisiert die Engine.

        :param segment_maps: Dictionary, das pro Stil (Tradition)
            eine ``SegmentMap`` bereitstellt.
        :param crossfade_ms: Dauer der Übergänge zwischen Segmenten in ms.
        """
        self.segment_maps = segment_maps
        self.crossfade_ms = crossfade_ms
        self.sine_engine = AudioEngine()

    def _load_segment(self, path: str) -> Optional[AudioSegment]:
        if not HAVE_PYDUB:
            return None
        if not os.path.isfile(path):
            return None
        try:
            return AudioSegment.from_file(path)
        except Exception:
            return None

    def token_to_segment(self, token: Union[Note, object], style: str) -> Optional[AudioSegment]:
        """Wandle einen Note oder Token in ein AudioSegment um.

        Für ``Note`` wird immer der Sinusgenerator genutzt. Für Tokens
        (z. B. ``TokenFull``) wird versucht, ein Segment anhand der
        Gruppe zu laden. Schlägt dies fehl, werden die zugehörigen
        Noten über den Sinusgenerator erstellt.
        """
        # Direct Note: fallback on sine
        if isinstance(token, Note):
            return self.sine_engine.generate_audio_segment([token])
        # Versuche Gruppe zu extrahieren
        group = getattr(token, 'group', None)
        notes = getattr(token, 'notes', None)
        if group and style in self.segment_maps:
            seg_map = self.segment_maps[style].mapping
            file_path = seg_map.get(group)
            if file_path:
                seg = self._load_segment(file_path)
                if seg:
                    return seg
        # Fallback: generiere aus Noten
        if notes:
            seg = self.sine_engine.generate_audio_segment(notes)
            return seg
        return None

    def tokens_to_audio(self, tokens: Iterable[Union[Note, object]], style: str = '', tempo: float = 120.0) -> Optional[AudioSegment]:
        """Kombiniere eine Sequenz von Tokens zu einem AudioSegment.

        :param tokens: Sequenz von ``Note`` oder Token‑Objekten mit
            ``group`` und ``notes``.
        :param style: Name der Tradition. Muss in ``segment_maps``
            vorhanden sein.
        :param tempo: Tempo für den Fallback Sinusgenerator.
        :return: Ein zusammengefügtes ``AudioSegment`` oder ``None``,
            wenn ``pydub`` nicht verfügbar ist und keine Fallback‑Noten
            erzeugt werden können.
        """
        if not HAVE_PYDUB:
            # Fallback: generiere komplette Sequenz via AudioEngine
            # (keine Crossfades)
            combined_notes: List[Note] = []
            for tok in tokens:
                if isinstance(tok, Note):
                    combined_notes.append(tok)
                else:
                    ns = getattr(tok, 'notes', None)
                    if ns:
                        combined_notes.extend(ns)
            return self.sine_engine.generate_audio_segment(combined_notes, tempo)
        segments: List[AudioSegment] = []
        for tok in tokens:
            seg = self.token_to_segment(tok, style)
            if seg:
                segments.append(seg)
        if not segments:
            return None
        # Kombiniere mit Crossfade
        output = segments[0]
        for seg in segments[1:]:
            output = output.append(seg, crossfade=self.crossfade_ms)
        return output

    def save(self, segment: AudioSegment, filename: str, format: str = 'wav') -> None:
        """Speichere ein AudioSegment in eine Datei.

        :param segment: Audiodaten
        :param filename: Zielname
        :param format: Exportformat (wav, mp3 etc.)
        """
        if not HAVE_PYDUB:
            raise RuntimeError("pydub ist nicht verfügbar.")
        if segment is None:
            raise ValueError("segment darf nicht None sein")
        segment.export(filename, format=format)

__all__ = ["SegmentMap", "ConcatAudioEngine"]