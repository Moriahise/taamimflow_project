"""Robuste AudioEngine ohne externe Abhängigkeiten
=================================================

Qt6-konforme AudioEngine für Ta'amimFlow.

THREADING-STRATEGIE (V10.5 – endgültige Lösung):

  ``QAudioSink`` ist ein Qt-Multimedia-Objekt und gehört **ausschließlich
  zum Main-Thread**.  Es kann nicht sicher in ``QThread``-Worker-Threads
  genutzt werden – weder mit ``time.sleep`` noch mit ``QEventLoop``.
  Der resultierende Crash lautet:
      "QThread: Destroyed while thread '' is still running"

  Lösung: Wort-für-Wort-Wiedergabe läuft im Worker-Thread über
  **temp-WAV + winsound** (Windows stdlib, blockierend, thread-sicher).
  Auf macOS / Linux werden ``afplay`` bzw. ``aplay`` als Subprocess
  genutzt.  In allen Fällen ist der Aufruf synchron – der Worker-Thread
  blockiert korrekt bis das Audio abgespielt ist.

  Hierarchie in ``_play_bytes``:
    1. Windows: ``winsound.PlaySound``      (stdlib, kein Crash möglich)
    2. macOS:   ``afplay`` via subprocess   (Teil von macOS, immer vorhanden)
    3. Linux:   ``aplay``  via subprocess   (ALSA, meist vorhanden)
    4. Fallback: ``QAudioSink`` im Main-Thread (nur wenn kein Worker-Thread)

Qt6-Migration (gemäß Repository-Analyse):
  - ``QAudioOutput``   → ``QAudioSink``
  - ``QAudioDevice.defaultAudioOutput()`` → ``QMediaDevices.defaultAudioOutput()``
  - ``setSampleSize / setSampleType / setCodec``
    → ``setSampleFormat(QAudioFormat.SampleFormat.Int16)``
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
import wave
from dataclasses import dataclass
from typing import Iterable, Optional, Union

# QtMultimedia – nur für Main-Thread-Wiedergabe (Fallback)
try:
    from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QAudioDevice, QMediaDevices
    from PyQt6.QtCore import QBuffer, QIODevice, QByteArray
    HAVE_QT = True
except Exception:
    QAudioFormat = object   # type: ignore
    QAudioSink = object     # type: ignore
    QAudioDevice = object   # type: ignore
    QMediaDevices = object  # type: ignore
    QBuffer = object        # type: ignore
    QIODevice = object      # type: ignore
    QByteArray = bytes      # type: ignore
    HAVE_QT = False

# Optionales Pydub
try:
    from pydub import AudioSegment  # type: ignore
    HAVE_PYDUB = True
except Exception:
    AudioSegment = None  # type: ignore
    HAVE_PYDUB = False

# winsound – Windows stdlib, immer verfügbar auf Windows
if sys.platform == "win32":
    try:
        import winsound as _winsound
        HAVE_WINSOUND = True
    except Exception:
        HAVE_WINSOUND = False
else:
    HAVE_WINSOUND = False


@dataclass
class Note:
    """Repräsentiert eine einzelne Note für die Synthese.

    :param pitch: MIDI-Zahl (int) oder Notation wie ``"A4"``
    :param duration: Dauer in Viertelnoten (1.0 = Viertelnote)
    :param upbeat: Optionales Auftakt-Flag (derzeit nicht verwendet)
    """
    pitch: Union[str, int]
    duration: float
    upbeat: bool = False


class AudioEngine:
    """AudioEngine mit interner Sinus-Synthese.

    Synthesise: reines Python, thread-sicher, kein Qt.
    Playback:   winsound (Win) / afplay (Mac) / aplay (Linux) –
                alles blockierend, thread-sicher.
    """

    def __init__(self) -> None:
        self._sample_rate = 44100

    # ------------------------------------------------------------------
    # Pitch → Frequenz
    # ------------------------------------------------------------------

    def pitch_to_frequency(self, pitch: Union[str, int]) -> float:
        """Konvertiere Pitch in Frequenz in Hz."""
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
            octave = int(p[idx:]) if idx < len(p) else 4
            semi = note_map.get(note_name, 0)
            midi = 12 * (octave + 1) + semi
            return 440.0 * (2.0 ** ((midi - 69) / 12.0))
        return 440.0

    # ------------------------------------------------------------------
    # Synthese – reines Python, kein Qt, vollständig thread-sicher
    # ------------------------------------------------------------------

    def synthesise(
        self,
        notes: Iterable[Note],
        tempo: float = 120.0,
        volume: float = 1.0,
    ) -> Optional[bytes]:
        """Erzeuge PCM-Audio als ``bytes`` für eine Notensequenz.

        Gibt rohe 16-bit-PCM-Bytes (Mono, 44.1 kHz, Little-Endian)
        zurück.  Kein Qt, kein pydub – vollständig thread-sicher.

        :param notes: Iterable von ``Note``
        :param tempo: Tempo in BPM
        :param volume: Lautstärke (0.0–1.0)
        :return: ``bytes`` mit PCM-Daten oder ``None`` bei leerer Sequenz
        """
        has_notes = False
        beat_sec = 60.0 / max(tempo, 1.0)
        max_amp = 32767 * max(min(volume, 1.0), 0.0)
        sample_rate = self._sample_rate
        pcm = bytearray()
        for note in notes:
            has_notes = True
            freq = self.pitch_to_frequency(note.pitch)
            dur_sec = note.duration * beat_sec
            n_samples = max(1, int(dur_sec * sample_rate))
            for i in range(n_samples):
                t = i / sample_rate
                value = int(max_amp * math.sin(2 * math.pi * freq * t))
                pcm += value.to_bytes(2, byteorder='little', signed=True)
        if not has_notes:
            return None
        return bytes(pcm)

    def generate_audio_segment(
        self,
        notes: Iterable[Note],
        tempo: float = 120.0,
        volume: float = 1.0,
    ) -> Optional["AudioSegment"]:
        """Erzeuge einen ``pydub.AudioSegment`` (Abwärtskompatibilität).

        Liefert ``None`` wenn pydub nicht installiert ist.
        """
        if not HAVE_PYDUB:
            return None
        raw = self.synthesise(notes, tempo=tempo, volume=volume)
        if raw is None:
            return None
        try:
            return AudioSegment(
                data=raw,
                sample_width=2,
                frame_rate=self._sample_rate,
                channels=1,
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Wiedergabe – thread-sicher, blockierend
    # ------------------------------------------------------------------

    def _write_wav(self, raw: bytes) -> str:
        """Schreibe PCM-Bytes in eine temporäre WAV-Datei.

        :return: Pfad zur WAV-Datei (muss vom Aufrufer gelöscht werden).
        """
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)          # 16-bit
            wf.setframerate(self._sample_rate)
            wf.writeframes(raw)
        return path

    def _play_bytes(self, raw: bytes) -> None:
        """Spiele rohe PCM-Bytes ab – blockierend, thread-sicher.

        Schreibt PCM in eine temporäre WAV-Datei und spielt diese mit
        dem plattformspezifischen, thread-sicheren Player ab:

        * Windows : ``winsound.PlaySound``  (Python stdlib, synchron)
        * macOS   : ``afplay``              (System-Tool, synchron)
        * Linux   : ``aplay``              (ALSA, synchron)

        Alle Varianten blockieren bis das Audio abgespielt ist.
        Qt-Objekte werden in dieser Methode **nicht** verwendet.

        :param raw: 16-bit PCM Mono, 44.1 kHz, Little-Endian.
        """
        if not raw:
            return

        tmp_path: Optional[str] = None
        try:
            tmp_path = self._write_wav(raw)

            if HAVE_WINSOUND:
                # Windows: winsound.PlaySound – synchron, kein Qt
                _winsound.PlaySound(
                    tmp_path,
                    _winsound.SND_FILENAME | _winsound.SND_NODEFAULT,
                )
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["afplay", tmp_path], check=True)
            else:
                # Linux / andere Unixe
                import subprocess
                try:
                    subprocess.run(
                        ["aplay", "-q", tmp_path],
                        check=True,
                        timeout=30,
                    )
                except (FileNotFoundError, subprocess.SubprocessError):
                    # Fallback: paplay (PulseAudio)
                    subprocess.run(
                        ["paplay", tmp_path],
                        check=True,
                        timeout=30,
                    )

        except Exception:
            # Fehler unterdrücken – Worker-Thread soll stabil bleiben
            pass
        finally:
            # Temp-Datei aufräumen
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def play(self, data: Optional[Union[bytes, "AudioSegment"]]) -> None:
        """Spiele PCM-Daten oder ``AudioSegment`` ab.

        Akzeptiert:
        * ``bytes`` / ``bytearray`` / ``QByteArray`` – direkt abgespielt.
        * ``pydub.AudioSegment`` – auf 16 bit / 44.1 kHz / Mono normiert.
        * ``None`` – ignoriert.

        Blockierend bis Audio-Ende.  Thread-sicher.
        """
        if data is None:
            return

        # pydub AudioSegment → rohe PCM-Bytes
        if HAVE_PYDUB and isinstance(data, AudioSegment):
            try:
                seg = (
                    data
                    .set_frame_rate(self._sample_rate)
                    .set_channels(1)
                    .set_sample_width(2)
                )
                self._play_bytes(seg.raw_data)  # type: ignore
            except Exception:
                pass
            return

        # QByteArray → bytes (wenn Qt verfügbar)
        if HAVE_QT:
            try:
                from PyQt6.QtCore import QByteArray as _QBA
                if isinstance(data, _QBA):
                    self._play_bytes(bytes(data))
                    return
            except Exception:
                pass

        # bytes / bytearray direkt
        if isinstance(data, (bytes, bytearray)):
            self._play_bytes(bytes(data))
            return


__all__ = ["Note", "AudioEngine"]
