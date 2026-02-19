"""
Robuste AudioEngine ohne externe Abhängigkeiten
=================================================

Diese AudioEngine implementiert die grundlegende Synthese und Wiedergabe
für Ta'amimFlow, ohne sich auf externe Player wie pydub.playback,
winsound oder ffmpeg zu verlassen.  Sie nutzt ausschließlich
QtMultimedia, um rohe PCM‑Daten abzuspielen.  Damit wird eine
nicht‑blockierende Wiedergabe ermöglicht, die im GUI‑Kontext von
PyQt6 sicher funktioniert.

Die Engine bietet drei Hauptfunktionen:

* ``synthesise`` generiert aus einer Folge von ``Note``‑Objekten
  einen ``QByteArray`` mit 16‑bit‑PCM‑Samples (Mono, 44.1 kHz).
* ``play`` spielt entweder einen ``QByteArray``, ein ``bytes``
  Objekt oder einen ``pydub.AudioSegment`` ab.  Letzteres wird zur
  Laufzeit konvertiert.
* ``generate_audio_segment`` wandelt eine Notensequenz in einen
  ``pydub.AudioSegment`` um.  Dies dient primär der Kompatibilität zu
  Modulen wie ``ConcatAudioEngine``, die weiterhin Pydub zur
  Bearbeitung (z.B. Crossfades) nutzen.  Fehlt ``pydub``, liefert
  diese Methode ``None``.

Die Klasse ``Note`` ist identisch mit der Definition im ursprünglichen
Projekt: ``pitch`` kann als MIDI‑Zahl (int) oder als Notenbezeichner
``"A4"`` usw. übergeben werden, ``duration`` ist als Anzahl
Viertelnoten definiert.  Ein optionales ``upbeat``‑Flag wird zur
Vollständigkeit mitgeführt, ohne die Synthese zu beeinflussen.

Diese Implementierung geht davon aus, dass ein Qt‑Kontext vorhanden
ist (d.h. ``PyQt6`` ist installiert).  Wenn ``PyQt6`` nicht
verfügbar ist, ist keine Audioausgabe möglich.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Union

# QtMultimedia für Audioausgabe
try:
    from PyQt6.QtMultimedia import QAudioFormat, QAudioOutput, QAudioDevice
    from PyQt6.QtCore import QBuffer, QIODevice, QByteArray
    HAVE_QT = True
except Exception:
    # Dummy Klassen für Typing, wenn Qt fehlt
    QAudioFormat = object  # type: ignore
    QAudioOutput = object  # type: ignore
    QAudioDevice = object  # type: ignore
    QBuffer = object  # type: ignore
    QIODevice = object  # type: ignore
    QByteArray = bytes  # type: ignore
    HAVE_QT = False

# Optionales Pydub für die Erzeugung von AudioSegment
try:
    from pydub import AudioSegment  # type: ignore
    HAVE_PYDUB = True
except Exception:
    AudioSegment = None  # type: ignore
    HAVE_PYDUB = False


@dataclass
class Note:
    """Repräsentiert eine einzelne Note für die Synthese.

    :param pitch: MIDI‑Zahl (int) oder Notation wie ``"A4"``
    :param duration: Dauer in Viertelnoten (1.0 = Viertelnote)
    :param upbeat: Optionales Auftakt‑Flag (derzeit nicht verwendet)
    """

    pitch: Union[str, int]
    duration: float
    upbeat: bool = False


class AudioEngine:
    """AudioEngine mit interner Sinus‑Synthese und Qt‑Wiedergabe.

    Diese Engine erzeugt Roh‑PCM‑Daten (16 bit, Mono, 44.1 kHz) aus
    Notensequenzen und spielt diese mit ``QAudioOutput`` ab.  Es gibt
    keine Abhängigkeiten zu externen Playern oder Blocking‑Calls wie
    ``time.sleep``.  Bei fehlendem Qt (``HAVE_QT = False``) können
    zwar PCM‑Bytes erzeugt werden, aber keine Wiedergabe erfolgen.
    """

    def __init__(self) -> None:
        # Standardformat definieren (Mono, 44.1 kHz, 16 bit)
        self._sample_rate = 44100
        if HAVE_QT:
            fmt = QAudioFormat()
            fmt.setChannelCount(1)
            fmt.setSampleRate(self._sample_rate)
            fmt.setSampleSize(16)
            fmt.setSampleType(QAudioFormat.SampleType.SignedInt)
            fmt.setCodec("audio/pcm")
            # Standard‑Ausgabegerät wählen
            device = QAudioDevice.defaultAudioOutput()
            self._audio_out: QAudioOutput = QAudioOutput(device, fmt)  # type: ignore
            self._buffer: Optional[QBuffer] = None
            self._format = fmt
        else:
            self._audio_out = None  # type: ignore
            self._buffer = None
            self._format = None  # type: ignore

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    def pitch_to_frequency(self, pitch: Union[str, int]) -> float:
        """Konvertiere Pitch in eine Frequenz in Hz.

        Akzeptiert MIDI‑Zahlen (int oder String) oder Notenbezeichner
        wie "A4", "C#5".  Bei unbekannten Formaten wird 440 Hz
        (Kammerton A) verwendet.
        """
        # MIDI‑Zahl direkt
        if isinstance(pitch, int) or (isinstance(pitch, str) and pitch.isdigit()):
            midi = int(pitch)
            return 440.0 * (2.0 ** ((midi - 69) / 12.0))
        # Notation wie A4, C#3 etc.
        if isinstance(pitch, str):
            p = pitch.strip().upper()
            note_map = {
                'C': 0, 'C#': 1, 'DB': 1,
                'D': 2, 'D#': 3, 'EB': 3,
                'E': 4,
                'F': 5, 'F#': 6, 'GB': 6,
                'G': 7, 'G#': 8, 'AB': 8,
                'A': 9, 'A#': 10, 'BB': 10,
                'B': 11,
            }
            # Trenne Note und Oktave
            idx = 0
            while idx < len(p) and not p[idx].isdigit():
                idx += 1
            note = p[:idx]
            octave = int(p[idx:]) if idx < len(p) else 4
            semi = note_map.get(note, 0)
            midi = 12 * (octave + 1) + semi
            return 440.0 * (2.0 ** ((midi - 69) / 12.0))
        # Fallback
        return 440.0

    # ------------------------------------------------------------------
    # Synthese
    # ------------------------------------------------------------------
    def synthesise(
        self,
        notes: Iterable[Note],
        tempo: float = 120.0,
        volume: float = 1.0,
    ) -> Optional[QByteArray]:
        """Erzeuge PCM‑Audio als ``QByteArray`` für eine Notensequenz.

        :param notes: Iterable von ``Note``
        :param tempo: Tempo in BPM (1.0 Viertelnote = 60/tempo Sekunden)
        :param volume: Lautstärke (0.0–1.0)
        :return: Rohbytes als ``QByteArray`` oder ``None`` wenn keine
          Noten angegeben wurden.
        """
        # Keine Noten → nichts zu tun
        has_notes = False
        # Dauer einer Viertelnote
        beat_sec = 60.0 / tempo
        max_amp = 32767 * max(min(volume, 1.0), 0.0)
        sample_rate = self._sample_rate
        pcm = bytearray()
        for note in notes:
            has_notes = True
            freq = self.pitch_to_frequency(note.pitch)
            dur_sec = note.duration * beat_sec
            n_samples = max(1, int(dur_sec * sample_rate))
            # Synthese einfacher Sinus (keine Hüllkurve)
            for i in range(n_samples):
                t = i / sample_rate
                value = int(max_amp * math.sin(2 * math.pi * freq * t))
                pcm += value.to_bytes(2, byteorder='little', signed=True)
        if not has_notes:
            return None
        # Rückgabe als QByteArray
        return QByteArray(pcm) if HAVE_QT else QByteArray(bytes(pcm))  # type: ignore

    def generate_audio_segment(
        self,
        notes: Iterable[Note],
        tempo: float = 120.0,
        volume: float = 1.0,
    ) -> Optional['AudioSegment']:
        """Erzeuge einen ``pydub.AudioSegment`` aus Noten.

        Diese Methode dient ausschließlich der Abwärtskompatibilität für
        Module wie ``ConcatAudioEngine``, die weiterhin auf ``pydub``
        angewiesen sein können (z.B. um Crossfades auszuführen).
        Ist ``pydub`` nicht vorhanden, liefert sie ``None``.
        """
        if not HAVE_PYDUB:
            return None
        qba = self.synthesise(notes, tempo=tempo, volume=volume)
        if qba is None:
            return None
        # ``bytes(qba)`` erzeugt einen immutable bytes‑Container aus
        # QByteArray.  pydub benötigt zudem Parameter: sample_width,
        # frame_rate, channels.
        data_bytes = bytes(qba)
        try:
            return AudioSegment(
                data=data_bytes,
                sample_width=2,
                frame_rate=self._sample_rate,
                channels=1,
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Wiedergabe
    # ------------------------------------------------------------------
    def _play_bytes(self, raw: bytes) -> None:
        """Spiele rohe PCM‑Bytes via ``QAudioOutput`` ab (nicht‑blockierend)."""
        if not HAVE_QT or not raw:
            return
        # Erzeuge ByteArray aus Rohbytes
        data = QByteArray(raw)
        # Speichere Buffer auf Instanz, damit er im Speicher bleibt
        self._buffer = QBuffer()
        self._buffer.setData(data)
        # Öffnen im ReadOnly‑Modus
        self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)  # type: ignore
        # Abspielen starten
        self._audio_out.start(self._buffer)

    def play(self, data: Optional[Union[QByteArray, bytes, 'AudioSegment']]) -> None:
        """Spiele PCM‑Daten oder ``AudioSegment`` ab.

        Diese Methode akzeptiert unterschiedliche Datentypen:

        * ``QByteArray`` oder ``bytes``: Diese werden direkt an
          ``QAudioOutput`` übergeben.
        * ``pydub.AudioSegment``: Das Segment wird auf das Format
          (16 bit, 44.1 kHz, Mono) normiert und dann abgespielt.

        Bei fehlendem Qt oder ungültigen Daten geschieht nichts.  Die
        Wiedergabe läuft nicht‑blockierend.
        """
        if data is None:
            return
        # AudioSegment → PCM wandeln
        if HAVE_PYDUB and isinstance(data, AudioSegment):
            try:
                seg = data.set_frame_rate(self._sample_rate).set_channels(1).set_sample_width(2)
                pcm = seg.raw_data  # type: ignore
                self._play_bytes(pcm)
            except Exception:
                return
            return
        # QByteArray → bytes
        if HAVE_QT and isinstance(data, QByteArray):  # type: ignore
            self._play_bytes(bytes(data))
            return
        # bytes oder bytearray direkt
        if isinstance(data, (bytes, bytearray)):
            self._play_bytes(bytes(data))
            return
        # Andere Typen ignorieren
        return

__all__ = ["Note", "AudioEngine"]