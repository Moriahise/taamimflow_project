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

    # ── Methoden für main_window/_WordByWordWorker ────────────────────────────

    def synthesise(
        self,
        notes: Iterable[Note],
        tempo: float = 120.0,
        volume: float = 1.0,
    ) -> Optional['AudioSegment']:
        """Erzeuge AudioSegment für die gegebenen Noten.

        Alias/Erweiterung von :meth:`generate_audio_segment`, der zusätzlich
        die Lautstärke (0–1) berücksichtigt.  Wird von
        ``_WordByWordWorker`` und ``_AudioWorker`` in main_window aufgerufen.

        :param notes: Iterable von :class:`Note`-Objekten.
        :param tempo:  Tempo in BPM (Standard: 120).
        :param volume: Lautstärke 0.0–1.0 (0 = Stille, 1 = Volle Lautstärke).
        :return:       pydub.AudioSegment oder ``None`` wenn pydub fehlt.
        """
        if not HAVE_PYDUB:
            return None
        seg = self.generate_audio_segment(list(notes), tempo)
        if seg is None:
            return None
        # Lautstärke in dB umrechnen: 0 dB = vol 1.0, -∞ = vol 0
        if volume <= 0:
            gain_db = -60.0
        elif volume < 1.0:
            import math as _math
            gain_db = 20.0 * _math.log10(volume)
        else:
            gain_db = 0.0
        return seg.apply_gain(gain_db)

    def play(self, segment: Optional['AudioSegment']) -> None:
        """Spiele ein AudioSegment ab.  Blockierend (läuft im Worker-Thread).

        Wiedergabe-Kette (Windows):
          1. pydub.playback.play()     – wenn simpleaudio/pyaudio installiert
          2. winsound.PlaySound()      – immer auf Windows verfügbar (kein Dep.)
          3. ffplay-Subprocess         – wenn ffmpeg im PATH
          4. os.startfile()            – letzter Ausweg (System-Mediaplayer)

        Auf Nicht-Windows-Systemen: pydub.playback → ffplay.
        """
        if segment is None or not HAVE_PYDUB:
            return

        import sys
        import io
        import os
        import tempfile

        # ── 1. pydub.playback (simpleaudio / pyaudio) ─────────────────────
        try:
            from pydub.playback import play as _pydub_play
            _pydub_play(segment)
            return
        except Exception:
            pass

        # WAV-Bytes einmal erzeugen (für Fallbacks 2–4)
        buf = io.BytesIO()
        segment.export(buf, format="wav")
        wav_bytes = buf.getvalue()

        # ── 2. winsound (Windows, built-in, kein simpleaudio nötig) ──────
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
                return
            except Exception:
                pass

        # ── 3. ffplay Subprocess (plattformübergreifend mit ffmpeg) ──────
        try:
            import subprocess
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(wav_bytes)
                tmp_path = tmp.name
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
                check=True,
                timeout=30,
            )
            os.unlink(tmp_path)
            return
        except Exception:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # ── 4. os.startfile() / xdg-open (letzter Ausweg) ────────────────
        try:
            import time
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(wav_bytes)
                tmp_path = tmp.name
            if sys.platform == "win32":
                os.startfile(tmp_path)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", tmp_path])
            # Kurz warten damit das Wort-Timing ungefähr stimmt
            time.sleep(len(segment) / 1000.0)
        except Exception:
            pass

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


__all__ = ["Note", "AudioEngine", "HAVE_PYDUB"]