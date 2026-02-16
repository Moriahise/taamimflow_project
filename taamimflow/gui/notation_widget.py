"""Musical notation widget for cantillation trope display.

This module provides :class:`NotationWidget`, a custom QWidget that
draws standard Western musical notation for cantillation trope melodies.
It replicates the bottom panel of the original TropeTrainer application
which shows:

* The trope name (e.g. ``MERCHA.``) on the left
* A treble-clef staff with the melodic pattern for that trope
* Transliterated Hebrew syllables beneath each note (e.g. ``pah kahd``)

The widget uses :class:`QPainter` to render every graphical element
(staff lines, treble clef, note heads, stems, beams and text) so that
no external image assets or music fonts are required.

Usage::

    widget = NotationWidget()
    widget.set_trope("Merkha", ["pah", "kahd"])
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QFontMetrics,
    QLinearGradient,
)
from PyQt6.QtWidgets import QWidget


# ── Note data structure ─────────────────────────────────────────────

@dataclass
class NoteInfo:
    """A single note in a trope melody."""
    pitch: str       # e.g. "E4", "D4", "C4"
    duration: float  # 1.0 = quarter, 0.5 = eighth, 2.0 = half


# ── Trope melody definitions ───────────────────────────────────────
# Each trope is mapped to a list of notes.  These are simplified
# melodic contours based on standard Ashkenazi Torah reading
# patterns.  The pitches are approximate and intended for visual
# display only.

TROPE_MELODIES: Dict[str, List[NoteInfo]] = {
    # ── Disjunctive (major stops) ──
    "Sof Pasuk": [
        NoteInfo("D4", 0.5), NoteInfo("E4", 0.5),
        NoteInfo("D4", 0.5), NoteInfo("C4", 1.0),
    ],
    "Etnachta": [
        NoteInfo("D4", 0.5), NoteInfo("E4", 0.5),
        NoteInfo("D4", 0.5), NoteInfo("C4", 1.0),
    ],
    "Segol": [
        NoteInfo("G4", 0.5), NoteInfo("F4", 0.5),
        NoteInfo("E4", 0.5), NoteInfo("D4", 1.0),
    ],
    "Shalshelet": [
        NoteInfo("E4", 0.5), NoteInfo("F4", 0.5), NoteInfo("E4", 0.5),
        NoteInfo("F4", 0.5), NoteInfo("E4", 0.5), NoteInfo("F4", 0.5),
        NoteInfo("E4", 0.5), NoteInfo("D4", 1.0),
    ],
    "Zakef": [
        NoteInfo("F4", 0.5), NoteInfo("E4", 0.5), NoteInfo("D4", 1.0),
    ],
    "Zakef Gadol": [
        NoteInfo("G4", 0.5), NoteInfo("F4", 0.5), NoteInfo("E4", 1.0),
    ],
    "Tipeha": [
        NoteInfo("E4", 0.5), NoteInfo("D4", 0.5), NoteInfo("C4", 1.0),
    ],
    "Revia": [
        NoteInfo("G4", 0.5), NoteInfo("F4", 1.0),
    ],
    "Tevir": [
        NoteInfo("E4", 0.5), NoteInfo("F4", 0.5), NoteInfo("E4", 1.0),
    ],
    "Pashta": [
        NoteInfo("F4", 0.5), NoteInfo("G4", 0.5), NoteInfo("F4", 1.0),
    ],
    "Yetiv": [
        NoteInfo("F4", 0.5), NoteInfo("E4", 1.0),
    ],
    "Zarqa": [
        NoteInfo("E4", 0.5), NoteInfo("F4", 0.5), NoteInfo("G4", 0.5),
        NoteInfo("F4", 1.0),
    ],
    "Geresh": [
        NoteInfo("G4", 0.5), NoteInfo("A4", 0.5), NoteInfo("G4", 1.0),
    ],
    "Gershayim": [
        NoteInfo("G4", 0.5), NoteInfo("A4", 0.5),
        NoteInfo("G4", 0.5), NoteInfo("A4", 0.5), NoteInfo("G4", 1.0),
    ],
    "Pazer": [
        NoteInfo("G4", 0.5), NoteInfo("A4", 0.5), NoteInfo("B4", 0.5),
        NoteInfo("A4", 0.5), NoteInfo("G4", 1.0),
    ],
    "Qarney Para": [
        NoteInfo("A4", 0.5), NoteInfo("B4", 0.5),
        NoteInfo("A4", 0.5), NoteInfo("G4", 1.0),
    ],
    "Telisha Gedola": [
        NoteInfo("G4", 0.5), NoteInfo("A4", 0.5), NoteInfo("G4", 1.0),
    ],
    # ── Conjunctive (connectors) ──
    "Merkha": [
        NoteInfo("E4", 0.5), NoteInfo("D4", 0.5), NoteInfo("C4", 1.0),
    ],
    "Munach": [
        NoteInfo("E4", 0.5), NoteInfo("D4", 1.0),
    ],
    "Mahpakh": [
        NoteInfo("D4", 0.5), NoteInfo("E4", 0.5), NoteInfo("D4", 1.0),
    ],
    "Merkha Kefula": [
        NoteInfo("E4", 0.5), NoteInfo("D4", 0.5),
        NoteInfo("E4", 0.5), NoteInfo("D4", 1.0),
    ],
    "Darga": [
        NoteInfo("E4", 0.5), NoteInfo("F4", 0.5),
        NoteInfo("E4", 0.5), NoteInfo("D4", 1.0),
    ],
    "Qadma": [
        NoteInfo("E4", 0.5), NoteInfo("F4", 1.0),
    ],
    "Telisha Qetana": [
        NoteInfo("F4", 0.5), NoteInfo("E4", 1.0),
    ],
    "Yerah Ben Yomo": [
        NoteInfo("D4", 0.5), NoteInfo("E4", 0.5),
        NoteInfo("D4", 0.5), NoteInfo("C4", 1.0),
    ],
    "Ole": [
        NoteInfo("D4", 0.5), NoteInfo("E4", 0.5), NoteInfo("F4", 1.0),
    ],
    "Iluy": [
        NoteInfo("E4", 0.5), NoteInfo("F4", 1.0),
    ],
    "Dehi": [
        NoteInfo("E4", 1.0),
    ],
    "Zinor": [
        NoteInfo("E4", 0.5), NoteInfo("F4", 0.5), NoteInfo("G4", 1.0),
    ],
    "Unknown": [
        NoteInfo("E4", 1.0),
    ],
}


# ── Pitch → staff position ──────────────────────────────────────────
# Position 0 = top staff line (F5), each half-step on the staff is +0.5
# Lines are at positions: 0, 1, 2, 3, 4 (i.e. integers)
# Spaces are at positions: 0.5, 1.5, 2.5, 3.5

PITCH_POSITIONS: Dict[str, float] = {
    "C6":  -3.5,
    "B5":  -3.0,
    "A5":  -2.5,
    "G5":  -2.0,
    "F5":  -1.5,
    "E5":  -1.0,
    "D5":  -0.5,
    "C5":   0.0,  # one above top line
    "B4":   0.5,  # top line
    "A4":   1.0,
    "G4":   1.5,  # second line
    "F4":   2.0,
    "E4":   2.5,  # third line (middle)
    "D4":   3.0,
    "C4":   3.5,  # fourth line
    "B3":   4.0,
    "A3":   4.5,  # bottom line
    "G3":   5.0,
    "F3":   5.5,  # one below bottom line
    "E3":   6.0,
}


class NotationWidget(QWidget):
    """Custom widget that draws musical staff notation for trope melodies.

    The widget renders a treble clef, staff lines, note heads with
    stems/beams, and transliterated syllable text beneath the notes.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.setMaximumHeight(120)
        # Light background matching original TropeTrainer
        self.setStyleSheet("background-color: #E8E8E0; border: 1px solid #999;")
        # Current display state
        self._trope_name: str = ""
        self._syllables: List[str] = []
        self._notes: List[NoteInfo] = []

    def set_trope(self, trope_name: str, syllables: List[str]) -> None:
        """Set the trope to display and trigger a repaint.

        :param trope_name: Name of the trope (e.g. ``"Merkha"``).
        :param syllables: Transliterated syllables to show beneath notes.
        """
        self._trope_name = trope_name
        self._syllables = syllables
        self._notes = TROPE_MELODIES.get(trope_name, TROPE_MELODIES["Unknown"])
        self.update()

    def clear(self) -> None:
        """Clear the notation display."""
        self._trope_name = ""
        self._syllables = []
        self._notes = []
        self.update()

    # ── Painting ────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        """Draw the full musical notation."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor("#E8E8E0"))

        if not self._trope_name:
            # Draw placeholder text
            painter.setPen(QColor("#888"))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                             "Click a word to see its trope notation")
            painter.end()
            return

        # Layout constants
        left_margin = 10
        staff_left = 120     # Where the staff starts (after trope name)
        staff_right = w - 20
        staff_width = staff_right - staff_left
        top_margin = 15
        line_gap = 10        # Gap between staff lines
        staff_height = line_gap * 4  # 5 lines, 4 gaps
        staff_top = top_margin + 10
        staff_bottom = staff_top + staff_height

        # ── Draw trope name ──
        painter.setPen(QColor("#000"))
        name_font = QFont("Arial", 11, QFont.Weight.Bold)
        painter.setFont(name_font)
        # Uppercase with period, matching original
        display_name = self._trope_name.upper() + "."
        name_rect = QRectF(left_margin, staff_top, staff_left - left_margin - 10, staff_height)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         display_name)

        # ── Draw staff lines ──
        staff_pen = QPen(QColor("#000"), 1.0)
        painter.setPen(staff_pen)
        for i in range(5):
            y = staff_top + i * line_gap
            painter.drawLine(QPointF(staff_left, y), QPointF(staff_right, y))

        # ── Draw treble clef ──
        self._draw_treble_clef(painter, staff_left + 5, staff_top, line_gap)

        # ── Draw notes ──
        if not self._notes:
            painter.end()
            return

        clef_width = 30
        note_area_left = staff_left + clef_width + 10
        note_area_width = staff_right - note_area_left - 10
        n_notes = len(self._notes)

        if n_notes == 0:
            painter.end()
            return

        note_spacing = min(note_area_width / max(n_notes, 1), 55)
        # Center the notes
        total_notes_width = n_notes * note_spacing
        start_x = note_area_left + (note_area_width - total_notes_width) / 2

        # Distribute syllables across notes
        syllables = list(self._syllables)
        note_syllables = self._distribute_syllables(syllables, n_notes)

        # Find groups of eighth notes for beaming
        note_positions: List[Tuple[float, float, NoteInfo]] = []
        for i, note in enumerate(self._notes):
            x = start_x + i * note_spacing + note_spacing / 2
            pos = PITCH_POSITIONS.get(note.pitch, 2.5)
            y = staff_top + pos * line_gap
            note_positions.append((x, y, note))

        # Draw beams for eighth note groups, then individual notes
        self._draw_notes_and_beams(painter, note_positions, staff_top,
                                   line_gap, staff_bottom)

        # ── Draw syllable text beneath the staff ──
        syl_font = QFont("Arial", 9)
        painter.setFont(syl_font)
        painter.setPen(QColor("#000"))
        text_y = staff_bottom + 18

        for i, (x, y, note) in enumerate(note_positions):
            syl = note_syllables[i] if i < len(note_syllables) else ""
            if syl:
                fm = QFontMetrics(syl_font)
                tw = fm.horizontalAdvance(syl)
                painter.drawText(QPointF(x - tw / 2, text_y), syl)

        painter.end()

    # ── Drawing helpers ─────────────────────────────────────────────

    def _draw_treble_clef(self, painter: QPainter, x: float, staff_top: float,
                          gap: float) -> None:
        """Draw a simplified treble clef symbol using QPainterPath."""
        painter.save()
        clef_pen = QPen(QColor("#000"), 1.8)
        painter.setPen(clef_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # The treble clef is centered on the G line (second from bottom = staff_top + 3*gap)
        g_line_y = staff_top + 3 * gap
        cx = x + 10  # center x

        path = QPainterPath()

        # Draw the main S-curve of the treble clef
        # Start from bottom, curve up
        bottom_y = staff_top + 5 * gap  # below staff
        top_y = staff_top - 1.5 * gap   # above staff

        # Lower curl (below staff)
        path.moveTo(cx + 3, bottom_y + 2)
        path.cubicTo(
            cx - 8, bottom_y,
            cx - 6, bottom_y - gap * 1.5,
            cx, bottom_y - gap * 1.5,
        )

        # Rise up through the staff
        path.cubicTo(
            cx + 6, bottom_y - gap * 2,
            cx + 8, staff_top + gap * 2,
            cx + 5, staff_top + gap,
        )

        # Top curl
        path.cubicTo(
            cx + 2, staff_top - gap * 0.3,
            cx - 8, staff_top + gap * 0.2,
            cx - 6, staff_top + gap * 1.5,
        )

        # Curve back down through G line
        path.cubicTo(
            cx - 4, staff_top + gap * 2.5,
            cx + 2, staff_top + gap * 3.2,
            cx + 1, staff_top + gap * 3.8,
        )

        # Down to the tail
        path.cubicTo(
            cx, staff_top + gap * 4.5,
            cx - 3, staff_top + gap * 5,
            cx - 2, staff_top + gap * 5.5,
        )

        painter.drawPath(path)

        # Draw the small dot at the bottom of the clef
        painter.setBrush(QBrush(QColor("#000")))
        painter.drawEllipse(QPointF(cx - 1, bottom_y + 3), 1.5, 1.5)

        # Vertical line through the clef
        painter.setPen(QPen(QColor("#000"), 1.5))
        painter.drawLine(QPointF(cx + 2, top_y + gap * 0.3),
                         QPointF(cx, bottom_y + 4))

        painter.restore()

    def _draw_notes_and_beams(
        self,
        painter: QPainter,
        positions: List[Tuple[float, float, NoteInfo]],
        staff_top: float,
        line_gap: float,
        staff_bottom: float,
    ) -> None:
        """Draw note heads, stems, flags and beams."""

        note_head_rx = 4.5  # horizontal radius
        note_head_ry = 3.5  # vertical radius
        stem_len = line_gap * 3

        # Group consecutive eighth notes for beaming
        groups: List[List[int]] = []
        current_group: List[int] = []

        for i, (x, y, note) in enumerate(positions):
            if note.duration <= 0.5:
                current_group.append(i)
            else:
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append([i])
        if current_group:
            groups.append(current_group)

        for group in groups:
            if len(group) == 1:
                idx = group[0]
                x, y, note = positions[idx]
                self._draw_single_note(painter, x, y, note, note_head_rx,
                                       note_head_ry, stem_len, staff_top, line_gap)
            else:
                # Beamed group of eighth notes
                self._draw_beamed_group(painter, [positions[i] for i in group],
                                        note_head_rx, note_head_ry, stem_len,
                                        staff_top, line_gap)

        # Draw ledger lines where needed
        for x, y, note in positions:
            pos = PITCH_POSITIONS.get(note.pitch, 2.5)
            self._draw_ledger_lines(painter, x, pos, staff_top, line_gap,
                                    note_head_rx)

    def _draw_single_note(
        self, painter: QPainter,
        x: float, y: float, note: NoteInfo,
        rx: float, ry: float, stem_len: float,
        staff_top: float, line_gap: float,
    ) -> None:
        """Draw a single note (quarter, half, or whole) with stem and flag."""
        painter.save()

        # Determine stem direction (up if below middle line, down if above)
        middle_y = staff_top + 2 * line_gap
        stem_up = y > middle_y

        # Note head
        painter.setPen(QPen(QColor("#000"), 1.2))
        if note.duration >= 2.0:
            # Half note: open head
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#000"), 1.8))
        else:
            # Quarter or eighth: filled head
            painter.setBrush(QBrush(QColor("#000")))

        # Draw slightly tilted ellipse
        painter.save()
        painter.translate(x, y)
        painter.rotate(-15)  # slight tilt like real note heads
        painter.drawEllipse(QPointF(0, 0), rx, ry)
        painter.restore()

        # Stem
        if note.duration < 4.0:  # not a whole note
            painter.setPen(QPen(QColor("#000"), 1.2))
            if stem_up:
                stem_x = x + rx - 1
                painter.drawLine(QPointF(stem_x, y), QPointF(stem_x, y - stem_len))
                # Flag for eighth note (only if not beamed)
                if note.duration <= 0.5:
                    self._draw_flag(painter, stem_x, y - stem_len, going_up=True)
            else:
                stem_x = x - rx + 1
                painter.drawLine(QPointF(stem_x, y), QPointF(stem_x, y + stem_len))
                if note.duration <= 0.5:
                    self._draw_flag(painter, stem_x, y + stem_len, going_up=False)

        painter.restore()

    def _draw_flag(self, painter: QPainter, x: float, y: float,
                   going_up: bool) -> None:
        """Draw an eighth note flag."""
        painter.save()
        painter.setPen(QPen(QColor("#000"), 1.5))
        path = QPainterPath()
        if going_up:
            path.moveTo(x, y)
            path.cubicTo(x + 8, y + 5, x + 6, y + 12, x + 2, y + 18)
        else:
            path.moveTo(x, y)
            path.cubicTo(x - 8, y - 5, x - 6, y - 12, x - 2, y - 18)
        painter.drawPath(path)
        painter.restore()

    def _draw_beamed_group(
        self, painter: QPainter,
        group_positions: List[Tuple[float, float, NoteInfo]],
        rx: float, ry: float, stem_len: float,
        staff_top: float, line_gap: float,
    ) -> None:
        """Draw a group of beamed eighth notes."""
        painter.save()

        middle_y = staff_top + 2 * line_gap
        # Determine overall stem direction based on average position
        avg_y = sum(y for _, y, _ in group_positions) / len(group_positions)
        stem_up = avg_y > middle_y

        # Draw note heads
        stem_tops: List[Tuple[float, float]] = []
        for x, y, note in group_positions:
            painter.setPen(QPen(QColor("#000"), 1.2))
            painter.setBrush(QBrush(QColor("#000")))
            painter.save()
            painter.translate(x, y)
            painter.rotate(-15)
            painter.drawEllipse(QPointF(0, 0), rx, ry)
            painter.restore()

            # Stem endpoint
            if stem_up:
                stem_x = x + rx - 1
                stem_end_y = y - stem_len
                stem_tops.append((stem_x, stem_end_y))
                painter.setPen(QPen(QColor("#000"), 1.2))
                painter.drawLine(QPointF(stem_x, y), QPointF(stem_x, stem_end_y))
            else:
                stem_x = x - rx + 1
                stem_end_y = y + stem_len
                stem_tops.append((stem_x, stem_end_y))
                painter.setPen(QPen(QColor("#000"), 1.2))
                painter.drawLine(QPointF(stem_x, y), QPointF(stem_x, stem_end_y))

        # Draw beam(s) connecting the stems
        if len(stem_tops) >= 2:
            beam_pen = QPen(QColor("#000"), 3.0)
            painter.setPen(beam_pen)
            # Main beam
            first_x, first_y = stem_tops[0]
            last_x, last_y = stem_tops[-1]
            painter.drawLine(QPointF(first_x, first_y), QPointF(last_x, last_y))

        painter.restore()

    def _draw_ledger_lines(
        self, painter: QPainter,
        x: float, pos: float,
        staff_top: float, line_gap: float,
        rx: float,
    ) -> None:
        """Draw ledger lines for notes above or below the staff."""
        painter.save()
        painter.setPen(QPen(QColor("#000"), 1.0))
        ledger_half_width = rx + 4

        # Above staff: positions < 0
        if pos < 0:
            line_pos = 0  # top line is position 0 ... wait
            # Actually in our mapping, the top line is at position 0.5 (B4)
            # Staff lines are at positions: 0.5, 1.5, 2.5, 3.5, 4.5
            # So above staff = pos < 0.5
            p = 0.0  # first position above top line
            while p >= pos:
                if p < 0.5 and (p * 2) % 2 == 0:  # on a line position
                    y = staff_top + p * line_gap
                    painter.drawLine(QPointF(x - ledger_half_width, y),
                                     QPointF(x + ledger_half_width, y))
                p -= 1.0

        # Below staff: positions > 4.5
        if pos > 4.5:
            p = 5.0
            while p <= pos:
                y = staff_top + p * line_gap
                painter.drawLine(QPointF(x - ledger_half_width, y),
                                 QPointF(x + ledger_half_width, y))
                p += 1.0

        painter.restore()

    def _distribute_syllables(
        self, syllables: List[str], n_notes: int
    ) -> List[str]:
        """Distribute syllables across notes.

        If there are fewer syllables than notes, the last syllable is
        held.  If more syllables than notes, later syllables are
        merged.
        """
        if not syllables:
            return [""] * n_notes

        if len(syllables) == n_notes:
            return syllables

        if len(syllables) < n_notes:
            # Pad: distribute syllables to later notes (melody extends the syllable)
            result = [""] * n_notes
            # Place syllables at roughly even intervals, last notes get held syllable
            if len(syllables) == 1:
                result[0] = syllables[0]
            else:
                step = max(1, n_notes // len(syllables))
                for i, syl in enumerate(syllables):
                    idx = min(i * step, n_notes - 1)
                    result[idx] = syl
            return result

        # More syllables than notes: merge extras into last note positions
        result = syllables[:n_notes - 1]
        remaining = " ".join(syllables[n_notes - 1:])
        result.append(remaining)
        return result


class TropeNotationPanel(QWidget):
    """Complete bottom panel combining trope name and notation.

    This composite widget arranges the :class:`NotationWidget`
    alongside a verse translation label to match the original
    TropeTrainer layout.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PyQt6.QtWidgets import QVBoxLayout, QLabel
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Translation / verse label (top)
        self.verse_label = QLabel("")
        self.verse_label.setStyleSheet(
            "background-color: #E8E8E0; padding: 4px; border: 1px solid #999;"
            " font-size: 12px; color: #333;"
        )
        self.verse_label.setWordWrap(True)
        self.verse_label.setMinimumHeight(24)
        layout.addWidget(self.verse_label)

        # Musical notation widget (bottom)
        self.notation = NotationWidget()
        layout.addWidget(self.notation)

        self.setLayout(layout)

    def set_verse_text(self, text: str) -> None:
        """Set the verse translation text."""
        self.verse_label.setText(text)

    def set_trope(self, trope_name: str, syllables: List[str]) -> None:
        """Set the trope and syllables for the notation widget."""
        self.notation.set_trope(trope_name, syllables)

    def clear(self) -> None:
        """Clear both panels."""
        self.verse_label.setText("")
        self.notation.clear()
