"""
Milestone 10 – Audio-Engine für Trope-Sequenzen
===============================================

FIX V10.1:
* play() nutzt Windows-native Fallback-Kette – kein simpleaudio / kein
  Visual C++ Build Tools nötig:
  1. pydub.playback.play()   – falls simpleaudio/pyaudio vorhanden
  2. winsound.PlaySound()    – Windows-nativ (WAV im RAM, keine Deps)
  3. ffplay                  – falls ffmpeg installiert
  4. os.startfile()          – Systemmedienplayer als letzter Ausweg
"""

from __future__ import annotations

import io
import math
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Iterable, List, Optional, Union

try:
    from pydub import AudioSegment  # type: ignore
    from pydub.generators import Sine  # type: ignore
    HAVE_PYDUB = True
except Exception:
    HAVE_PYDUB = False
    AudioSegment = None  # type: ignore
    Sine = None          # type: ignore


@dataclass
class Note:
    """Repräsentation einer musikalischen Note.

    :param pitch: Pitch als MIDI-Zahl oder Note (z.B. "A4", "C#5").
    :param duration: Notenlänge relativ zu einer Viertelnote
        (1.0 = Viertelnote, 0.5 = Achtel, 2.0 = Halbe etc.).
    :param upbeat: True wenn es sich um ein Auftaktzeichen handelt.
    """
    pitch: Union[str, int]
    duration: float
    upbeat: bool = False


class AudioEngine:
    """Einfache Audio-Engine auf Basis von Sinus-Generatoren.

    Gemeinsame Schnittstelle (für ``main_window`` / ``_AudioWorker``)::

        segment = engine.synthesise(notes, tempo=120.0, volume=0.8)
        engine.play(segment)
    """

    def __init__(self) -> None:
        pass  # kein pydub-Check im Konstruktor – schlägt erst bei Aufruf fehl

    # ------------------------------------------------------------------
    # Gemeinsame Schnittstelle (V10)
    # ------------------------------------------------------------------

    def synthesise(
        self,
        notes: Iterable[Note],
        tempo: float = 120.0,
        volume: float = 0.8,
    ) -> Optional['AudioSegment']:
        """Erzeuge ein ``AudioSegment`` für die Notensequenz.

        :param notes: Iterable von ``Note``-Objekten.
        :param tempo: Tempo in BPM.
        :param volume: Lautstärke 0.0–1.0.
        :return: ``AudioSegment`` oder ``None`` wenn pydub fehlt.
        """
        seg = self.generate_audio_segment(notes, tempo)
        if seg is not None and HAVE_PYDUB:
            # Lautstärke: dBFS-Anpassung
            gain_db = 20.0 * math.log10(max(volume, 0.0001))
            seg = seg.apply_gain(gain_db)
        return seg

    def play(self, segment: Optional['AudioSegment']) -> None:
        """Spiele ein AudioSegment ab – Windows-kompatible Fallback-Kette.

        Kein simpleaudio / kein Visual C++ Build Tools nötig.

        Fallback-Reihenfolge:
        1. pydub.playback.play()  – falls simpleaudio / pyaudio installiert
        2. winsound.PlaySound()   – Windows-nativ, kein Compiler nötig
        3. ffplay (subprocess)    – falls ffmpeg im PATH
        4. os.startfile()         – Systemmedienplayer
        Alle Fehler werden still ignoriert (kein Absturz der GUI).
        """
        if not HAVE_PYDUB or segment is None:
            return

        # Strategie 1: pydub.playback (simpleaudio / pyaudio)
        try:
            from pydub.playback import play as _play  # type: ignore
            _play(segment)
            return
        except Exception:
            pass

        # Strategie 2: winsound (Windows-nativ, WAV im RAM)
        if sys.platform == 'win32':
            try:
                import winsound  # type: ignore
                buf = io.BytesIO()
                segment.export(buf, format='wav')
                winsound.PlaySound(buf.getvalue(), winsound.SND_MEMORY)
                return
            except Exception:
                pass

        # Strategie 3: ffplay (Teil von ffmpeg)
        try:
            buf = io.BytesIO()
            segment.export(buf, format='wav')
            buf.seek(0)
            proc = subprocess.Popen(
                ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.stdin.write(buf.read())
            proc.stdin.close()
            proc.wait(timeout=60)
            return
        except Exception:
            pass

        # Strategie 4: Systemmedienplayer über Tempfile
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                tmp = f.name
            segment.export(tmp, format='wav')
            if sys.platform == 'win32':
                os.startfile(tmp)   # type: ignore[attr-defined]
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', tmp])
            else:
                subprocess.Popen(['xdg-open', tmp])
        except Exception:
            pass  # Alle Strategien fehlgeschlagen – kein Absturz

    # ------------------------------------------------------------------
    # Interne Methoden (unverändert)
    # ------------------------------------------------------------------

    def pitch_to_frequency(self, pitch: Union[str, int]) -> float:
        """Konvertiere eine Pitch-Angabe in Hertz."""
        if isinstance(pitch, int) or (isinstance(pitch, str) and pitch.isdigit()):
            midi = int(pitch)
            return 440.0 * (2.0 ** ((midi - 69) / 12.0))
        if isinstance(pitch, str):
            p = pitch.strip().upper()
            note_map = {
                'C': 0,  'C#': 1, 'DB': 1,
                'D': 2,  'D#': 3, 'EB': 3,
                'E': 4,
                'F': 5,  'F#': 6, 'GB': 6,
                'G': 7,  'G#': 8, 'AB': 8,
                'A': 9,  'A#': 10, 'BB': 10,
                'B': 11,
            }
            idx = 0
            while idx < len(p) and not p[idx].isdigit():
                idx += 1
            note_name = p[:idx]
            octave_str = p[idx:] if idx < len(p) else '4'
            try:
                octave = int(octave_str)
            except ValueError:
                octave = 4
            semi = note_map.get(note_name)
            if semi is None:
                return 440.0
            midi = 12 * (octave + 1) + semi
            return 440.0 * (2.0 ** ((midi - 69) / 12.0))
        return 440.0

    def generate_audio_segment(
        self,
        notes: Iterable[Note],
        tempo: float = 120.0,
    ) -> Optional['AudioSegment']:
        """Erzeuge ein pydub.AudioSegment für eine Notensequenz."""
        if not HAVE_PYDUB:
            return None
        note_list = list(notes)
        if not note_list:
            return AudioSegment.silent(duration=0)  # type: ignore
        beat_ms = 60000.0 / tempo
        segments: List['AudioSegment'] = []
        for note in note_list:
            freq = self.pitch_to_frequency(note.pitch)
            dur_ms = max(1, int(note.duration * beat_ms))
            tone = Sine(freq).to_audio_segment(duration=dur_ms).apply_gain(-3)
            segments.append(tone)
        output = segments[0]
        for seg in segments[1:]:
            output += seg
        return output

    def save_audio_segment(
        self,
        segment: 'AudioSegment',
        filename: str,
        format: str = 'wav',
    ) -> None:
        """Speichere ein AudioSegment in eine Datei."""
        if not HAVE_PYDUB or segment is None:
            raise RuntimeError("AudioSegment ist nicht verfügbar – pydub fehlt.")
        segment.export(filename, format=format)

    def sequence_to_audio(
        self,
        token_list: Iterable,
        filename: str,
        tempo: float = 120.0,
    ) -> None:
        """Konvertiere Tokens oder Notes in eine Audiodatei."""
        combined_notes: List[Note] = []
        for item in token_list:
            if isinstance(item, Note):
                combined_notes.append(item)
            else:
                # TokenFull / Token-artige Objekte
                ns = getattr(item, 'notes', None)
                if ns:
                    combined_notes.extend(ns)
        segment = self.generate_audio_segment(combined_notes, tempo)
        if segment is None:
            raise RuntimeError("Konnte Audio nicht generieren – pydub fehlt.")
        self.save_audio_segment(segment, filename)


__all__ = ["Note", "AudioEngine"]
