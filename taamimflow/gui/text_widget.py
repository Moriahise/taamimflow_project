"""Modern Torah Text Widget.

This module defines :class:`ModernTorahTextWidget`, a custom
``QTextEdit`` subclass tailored to displaying Hebrew texts with
cantillation marks.  The widget supports three view modes (modern,
STAM and tikkun) and three color modes (no color, trope colors and
symbol colors).  It exposes a simple API to set the text along with
trope groups and symbols so that the display can be regenerated
appropriately.

For brevity, the default implementation uses a list of tuples of the
form ``(word, trope_group, symbol)`` to store the content.  A full
implementation might instead accept a rich structure with verse
boundaries, morphological annotations and other metadata.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QBrush, QTextCharFormat
from PyQt6.QtWidgets import QTextEdit


# Default color assignments for trope groups and symbols.  These may
# later be externalised into the configuration.
DEFAULT_TROPE_COLORS = {
    "Sof Pasuk": "#00FFFF",      # Cyan
    "Zakef Katon": "#FFFF00",    # Yellow
    "Etnachta": "#FF00FF",       # Magenta
    "Tevir": "#FFFFFF",          # White
    "End of Aliyah": "#0000FF",  # Blue
    "End of Book": "#808080",    # Gray
}

SYMBOL_COLORS = {
    "✱": "#00FFFF",  # Cyan
    "◆": "#FF00FF",  # Magenta
    "▲": "#FFFF00",  # Yellow
}


class ModernTorahTextWidget(QTextEdit):
    """Widget for displaying Hebrew cantillation with multiple modes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Times New Roman", 20))
        self.trope_colors = DEFAULT_TROPE_COLORS.copy()
        self.symbol_colors = SYMBOL_COLORS.copy()
        # Modes: 'modern', 'stam', 'tikkun'
        self.view_mode = "modern"
        # Modes: 'no_colors', 'trope_colors', 'symbol_colors'
        self.color_mode = "trope_colors"
        # Internal representation of the text: list of (word, trope_group, symbol)
        self.content: List[Tuple[str, str, str]] = []

    def set_text(self, tokens: Iterable[Tuple[str, str, str]]) -> None:
        """Set the widget's content.

        Each token should be a triple containing the Hebrew word, the
        name of the trope group (e.g. ``"Zakef Katon"``) and a symbol
        that represents that group (e.g. ``"▲"``).  The widget does not
        attempt to interpret these values; it simply uses them for
        colour mapping and symbol insertion.

        :param tokens: Iterable of triples representing the text.
        """
        self.content = list(tokens)
        self.update_display()

    def set_view_mode(self, mode: str) -> None:
        """Set the view mode and refresh the display."""
        self.view_mode = mode
        self.update_display()

    def set_color_mode(self, mode: str) -> None:
        """Set the color mode and refresh the display."""
        self.color_mode = mode
        self.update_display()

    def update_display(self) -> None:
        """Redraw the content according to the current modes."""
        if self.view_mode == "modern":
            self.display_modern_view()
        elif self.view_mode == "stam":
            self.display_stam_view()
        elif self.view_mode == "tikkun":
            self.display_tikkun_view()
        else:
            # unknown mode: fallback to modern
            self.display_modern_view()

    def display_modern_view(self) -> None:
        """Modern mode displays vowels and tropes."""
        self.clear()
        cursor = self.textCursor()
        for word, trope_group, symbol in self.content:
            fmt = QTextCharFormat()
            fmt.setFont(QFont("Times New Roman", 20))
            if self.color_mode == "trope_colors":
                color = self.trope_colors.get(trope_group, "#FFFFFF")
                fmt.setBackground(QBrush(QColor(color)))
                fmt.setForeground(QBrush(QColor("#000000")))
                cursor.insertText(word + " ", fmt)
            elif self.color_mode == "symbol_colors":
                # Insert symbol before the word and color by symbol
                s_color = self.symbol_colors.get(symbol, "#FFFFFF")
                fmt.setBackground(QBrush(QColor(s_color)))
                fmt.setForeground(QBrush(QColor("#000000")))
                cursor.insertText(f"{symbol} ", fmt)
                cursor.insertText(word + " ", fmt)
            else:
                # no colors: plain black
                fmt.setForeground(QBrush(QColor("#000000")))
                cursor.insertText(word + " ", fmt)

    def display_stam_view(self) -> None:
        """STAM view strips vowels and tropes, optionally colourised."""
        self.clear()
        cursor = self.textCursor()
        for word, trope_group, _symbol in self.content:
            # Strip vowels and trope marks from the word.  In a real
            # implementation, we would use a utility function from
            # ``taamimflow.utils.hebrew``.  Here we naively remove
            # combining characters by filtering unicode categories.
            stripped = ''.join(ch for ch in word if not _is_combining(ch))
            fmt = QTextCharFormat()
            fmt.setFont(QFont("Times New Roman", 20))
            if self.color_mode == "trope_colors":
                color = self.trope_colors.get(trope_group, "#FFFFFF")
                fmt.setBackground(QBrush(QColor(color)))
                fmt.setForeground(QBrush(QColor("#000000")))
            elif self.color_mode == "symbol_colors":
                # In STAM mode symbol colors fall back to trope colors
                color = self.trope_colors.get(trope_group, "#FFFFFF")
                fmt.setBackground(QBrush(QColor(color)))
                fmt.setForeground(QBrush(QColor("#000000")))
            else:
                fmt.setForeground(QBrush(QColor("#000000")))
            cursor.insertText(stripped + " ", fmt)

    def display_tikkun_view(self) -> None:
        """Tikkun view displays two columns (modern and STAM)."""
        # Construct a minimal two‑column HTML table.  This method
        # demonstrates how one might display both the vocalised and
        # unvocalised text side by side.  For large passages the
        # performance of setHtml may become an issue; consider
        # alternative approaches for large texts.
        modern_words: List[str] = []
        stam_words: List[str] = []
        for word, trope_group, symbol in self.content:
            modern_words.append(word)
            stam_words.append(''.join(ch for ch in word if not _is_combining(ch)))
        modern_text = ' '.join(modern_words)
        stam_text = ' '.join(stam_words)
        html = f"""
            <table width='100%' border='1' style='border-collapse: collapse;'>
                <tr>
                    <td width='50%' style='padding: 10px; text-align: right; font-size: 18pt;'>
                        <b>Modern:</b><br>{modern_text}
                    </td>
                    <td width='50%' style='padding: 10px; text-align: right; font-size: 18pt;'>
                        <b>STAM:</b><br>{stam_text}
                    </td>
                </tr>
            </table>
        """
        self.setHtml(html)


def _is_combining(ch: str) -> bool:
    """Return True if the character is a Hebrew diacritic or trope mark."""
    import unicodedata
    return unicodedata.combining(ch) != 0