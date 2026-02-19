"""
Milestone 10 – Audio‑Engine für Trope‑Sequenzen
===============================================

Diese Komponente stellt eine minimal funktionsfähige Audio‑Engine
bereit, um die aus den Tropendefinitionen gewonnenen
Notensequenzen hörbar zu machen. Der Fokus liegt auf einer
softwarebasierten Synthese, die ohne externe Abhängigkeiten wie
FluidSynth auskommt. Stattdessen wird, wenn verfügbar, das
``pydub``‑Paket genutzt, um einfache Sinus‑Wellen zu erzeugen und
zu einem Audiostream zu kombinieren. Sollte ``pydub`` nicht
installiert sein, liefert die Engine keine Audiodaten.

Die Pitch‑Angabe der Noten kann entweder als MIDI‑Zahl (0–127) oder
als String in der Form "A4", "C#5" etc. vorliegen. Die
Dauern werden als Faktor relativer Viertelnoten interpretiert; bei
einem Tempo von 120 BPM entspricht eine Einheit 0,5 Sekunden.

Beispiel:

    from audio_engine import AudioEngine
    notes = [Note(pitch="C4", duration=1.0), Note(pitch="D4", duration=0.5)]
    engine = AudioEngine()
    segment = engine.generate_audio_segment(notes, tempo=100)
    engine.save_audio_segment(segment, "trope.wav")

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Union

import math

try:
    from pydub import AudioSegment  # type: ignore
    from pydub.generators import Sine  # type: ignore
    HAVE_PYDUB = True
except Exception:
    HAVE_PYDUB = False
    AudioSegment = None  # type: ignore
    Sine = None  # type: ignore


@dataclass
class Note:
    """Repräsentation einer musikalischen Note.

    :param pitch: Pitch als MIDI‑Zahl oder Note (z.B. "A4", "C#5").
    :param duration: Notenlänge relativ zu einer Viertelnote (1.0 = Viertelnote,
                      0.5 = Achtel, 2.0 = Halbe etc.).
    :param upbeat: Optional: True, wenn es sich um ein Auftaktzeichen handelt.
    """
    pitch: Union[str, int]
    duration: float
    upbeat: bool = False


class AudioEngine:
    """Einfache Audio‑Engine auf Basis von Sinus‑Generatoren.

    Diese Engine ist nicht für den produktiven Einsatz gedacht, erfüllt aber
    die MVP‑Anforderung, Notensequenzen als Audiodaten auszugeben. Sie
    ist unabhängig von der restlichen Anwendung und erzeugt
    AudioSegment‑Objekte (wenn ``pydub`` installiert ist).
    """
    def __init__(self) -> None:
        if not HAVE_PYDUB:
            # Warnung: In diesem Minimal‑Setup können wir keine Audiodaten erzeugen
            pass

    def pitch_to_frequency(self, pitch: Union[str, int]) -> float:
        """Konvertiere eine Pitch‑Angabe in Hertz.

        Unterstützt wird entweder eine MIDI‑Zahl (int) oder eine
        Notenbezeichnung wie "C4", "G#3". Unbekannte Formate führen
        zu einer Standardfrequenz von 440 Hz.
        """
        # MIDI‑Notation
        if isinstance(pitch, int) or (isinstance(pitch, str) and pitch.isdigit()):
            midi = int(pitch)
            return 440.0 * (2.0 ** ((midi - 69) / 12.0))
        if isinstance(pitch, str):
            p = pitch.strip().upper()
            # Ermittle Note und Oktave
            note_map = {
                'C': 0, 'C#': 1, 'DB': 1,
                'D': 2, 'D#': 3, 'EB': 3,
                'E': 4,
                'F': 5, 'F#': 6, 'GB': 6,
                'G': 7, 'G#': 8, 'AB': 8,
                'A': 9, 'A#': 10, 'BB': 10,
                'B': 11,
            }
            # Extrahiere Oktave (letzte Ziffern) und Notenname
            idx = 0
            while idx < len(p) and not p[idx].isdigit():
                idx += 1
            note_name = p[:idx]
            octave_str = p[idx:] if idx < len(p) else '4'
            try:
                octave = int(octave_str)
            except ValueError:
                octave = 4
            semi = note_map.get(note_name, None)
            if semi is None:
                return 440.0
            midi = 12 * (octave + 1) + semi
            return 440.0 * (2.0 ** ((midi - 69) / 12.0))
        return 440.0

    def generate_audio_segment(self, notes: Iterable[Note], tempo: float = 120.0) -> Optional['AudioSegment']:
        """Erzeuge ein pydub.AudioSegment für eine Sequenz von Noten.

        :param notes: Iterable von ``Note``‑Objekten.
        :param tempo: Tempo in BPM; bestimmt die Länge einer Viertelnote.
        :return: Ein kombiniertes AudioSegment oder ``None``, falls ``pydub``
            nicht verfügbar ist.
        """
        if not HAVE_PYDUB:
            return None
        if not notes:
            return AudioSegment.silent(duration=0)  # type: ignore
        beat_ms = 60000.0 / tempo  # Dauer einer Viertelnote in Millisekunden
        segments: List['AudioSegment'] = []
        for note in notes:
            freq = self.pitch_to_frequency(note.pitch)
            dur_ms = int(note.duration * beat_ms)
            dur_ms = max(1, dur_ms)  # min 1 ms
            tone = Sine(freq).to_audio_segment(duration=dur_ms).apply_gain(-3)
            segments.append(tone)
        # Füge Noten hintereinander (kein zusätzlicher Silence)
        output = segments[0]
        for seg in segments[1:]:
            output += seg
        return output

    def save_audio_segment(self, segment: 'AudioSegment', filename: str, format: str = 'wav') -> None:
        """Speichere ein AudioSegment in eine Datei.

        :param segment: Das zu speichernde Segment.
        :param filename: Zielpfad inkl. Endung (z.B. .wav).
        :param format: Exportformat (wav, mp3, etc.).
        """
        if not HAVE_PYDUB or segment is None:
            raise RuntimeError("AudioSegment ist nicht verfügbar – pydub fehlt.")
        segment.export(filename, format=format)

    def sequence_to_audio(self, token_list: Iterable[Union[Note, 'TokenFull']], filename: str, tempo: float = 120.0) -> None:
        """Konvertiere eine Liste von Notes oder TokenFull in eine Audiodatei.

        Wenn ``TokenFull`` übergeben werden, wird die ``notes``‑Liste pro Token
        verwendet und alle Noten der Reihe nach abgespielt. Leere Noten
        (None) werden übersprungen.
        """
        # Lazy import, um zirkuläre Abhängigkeiten zu vermeiden
        from milestone9_plus import TokenFull as _TokenFull  # type: ignore
        combined_notes: List[Note] = []
        for item in token_list:
            if isinstance(item, _TokenFull):
                if item.notes:
                    combined_notes.extend(item.notes)
            elif isinstance(item, Note):
                combined_notes.append(item)
        segment = self.generate_audio_segment(combined_notes, tempo)
        if segment is None:
            raise RuntimeError("Konnte Audio nicht generieren – pydub fehlt.")
        self.save_audio_segment(segment, filename)


__all__ = ["Note", "AudioEngine"]