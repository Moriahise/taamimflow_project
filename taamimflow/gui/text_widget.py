"""Modern Torah text display widget.

This module defines the :class:`ModernTorahTextWidget` class used by the
Ta'amimFlow application.  It extends :class:`QTextEdit` to display
Hebrew text with optional cantillation (trope) highlighting.  Three
view modes are supported:

* ``modern`` – display the text exactly as provided, including vowels
  and trope marks.
* ``stam`` – display only the consonantal text (sometimes called
  ``STAM``) by stripping vowels and trope marks.
* ``tikkun`` – present the modern and STAM text side‑by‑side in a
  simple two column table.  For short passages this provides a
  convenient reference for learners.

Colour highlighting can also be toggled.  In ``trope_colors`` mode the
background of each word is filled based on the trope group.  In
``symbol_colors`` mode a symbol is inserted before each word and
coloured based on the symbol.  In ``no_colors`` mode the text is
rendered in plain black.

The widget expects the content to be provided via :meth:`set_text` as
an iterable of triples ``(word, trope_group, symbol)``.  A naive
tokenisation strategy is provided by the main window but can be
replaced with a proper parser at a later stage.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QBrush, QTextCharFormat
from PyQt6.QtWidgets import QTextEdit

# Default colour assignments for trope groups and symbols.  These
# values mirror those used in the example application and can be
# customised or externalised via configuration in future versions.
DEFAULT_TROPE_COLORS = {
    "Sof Pasuk": "#00FFFF",      # Cyan
    "Zakef Katon": "#FFFF00",    # Yellow
    "Etnachta": "#FF00FF",       # Magenta
    "Tevir": "#FFFFFF",          # White
    "End of Aliyah": "#0000FF",  # Blue
    "End of Book": "#808080",    # Gray
}

# Colours associated with the simple symbols used when
# ``color_mode == "symbol_colors"``.  If a symbol is not found in
# this mapping a default of white is used.
SYMBOL_COLORS = {
    "✱": "#00FFFF",  # Cyan
    "◆": "#FF00FF",  # Magenta
    "▲": "#FFFF00",  # Yellow
}


class ModernTorahTextWidget(QTextEdit):
    """Widget for displaying Hebrew cantillation with multiple modes."""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Times New Roman", 20))
        # Clone default colour tables so they can be modified per
        # instance without affecting the module constants.
        self.trope_colors = DEFAULT_TROPE_COLORS.copy()
        self.symbol_colors = SYMBOL_COLORS.copy()
        # Modes: 'modern', 'stam', 'tikkun'
        self.view_mode: str = "modern"
        # Modes: 'no_colors', 'trope_colors', 'symbol_colors'
        self.color_mode: str = "trope_colors"
        # Internal representation of the text.  Each element is a triple
        # (word, trope_group, symbol).
        self.content: List[Tuple[str, str, str]] = []

    def set_text(self, tokens: Iterable[Tuple[str, str, str]]) -> None:
        """Set the widget's content and refresh the display.

        The provided ``tokens`` iterable should produce tuples of the
        form ``(word, trope_group, symbol)``.  The widget does not
        attempt to interpret these values; it simply uses them for
        colour mapping and symbol insertion.
        """
        self.content = list(tokens)
        self.update_display()

    def set_view_mode(self, mode: str) -> None:
        """Set the view mode and refresh the display.

        ``mode`` must be one of ``"modern"``, ``"stam"`` or ``"tikkun"``.
        Unknown values are ignored.
        """
        if mode in {"modern", "stam", "tikkun"}:
            self.view_mode = mode
            self.update_display()

    def set_color_mode(self, mode: str) -> None:
        """Set the colour mode and refresh the display.

        ``mode`` must be one of ``"no_colors"``, ``"trope_colors"`` or
        ``"symbol_colors"``.  Unknown values are ignored.
        """
        if mode in {"no_colors", "trope_colors", "symbol_colors"}:
            self.color_mode = mode
            self.update_display()

    def update_display(self) -> None:
        """Redraw the content according to the current modes."""
        if not self.content:
            # Nothing to display yet: clear and return.
            self.clear()
            return
        if self.view_mode == "modern":
            self.display_modern_view()
        elif self.view_mode == "stam":
            self.display_stam_view()
        elif self.view_mode == "tikkun":
            self.display_tikkun_view()
        else:
            # Unknown mode: fallback to modern
            self.display_modern_view()

    def display_modern_view(self) -> None:
        """Modern mode displays vowels and tropes."""
        self.clear()
        cursor = self.textCursor()
        for word, trope_group, symbol in self.content:
            fmt = QTextCharFormat()
            fmt.setFont(QFont("Times New Roman", 20))
            if self.color_mode == "trope_colors":
                # Colour by trope group
                color = self.trope_colors.get(trope_group, "#FFFFFF")
                fmt.setBackground(QBrush(QColor(color)))
                fmt.setForeground(QBrush(QColor("#000000")))
                cursor.insertText(word + " ", fmt)
            elif self.color_mode == "symbol_colors":
                # Insert symbol before the word and colour by symbol
                s_color = self.symbol_colors.get(symbol, "#FFFFFF")
                fmt.setBackground(QBrush(QColor(s_color)))
                fmt.setForeground(QBrush(QColor("#000000")))
                cursor.insertText(f"{symbol} ", fmt)
                cursor.insertText(word + " ", fmt)
            else:
                # no colours: plain black
                fmt.setForeground(QBrush(QColor("#000000")))
                cursor.insertText(word + " ", fmt)

    def display_stam_view(self) -> None:
        """STAM view strips vowels and tropes, optionally colourised."""
        self.clear()
        cursor = self.textCursor()
        for word, trope_group, symbol in self.content:
            # Remove diacritics and cantillation marks by filtering
            # combining characters.  A more sophisticated
            # implementation would rely on ``taamimflow.utils.hebrew``.
            stripped = ''.join(ch for ch in word if not _is_combining(ch))
            fmt = QTextCharFormat()
            fmt.setFont(QFont("Times New Roman", 20))
            if self.color_mode == "trope_colors":
                color = self.trope_colors.get(trope_group, "#FFFFFF")
                fmt.setBackground(QBrush(QColor(color)))
                fmt.setForeground(QBrush(QColor("#000000")))
            elif self.color_mode == "symbol_colors":
                # In STAM mode symbol colours fall back to trope colours
                color = self.trope_colors.get(trope_group, "#FFFFFF")
                fmt.setBackground(QBrush(QColor(color)))
                fmt.setForeground(QBrush(QColor("#000000")))
            else:
                fmt.setForeground(QBrush(QColor("#000000")))
            cursor.insertText(stripped + " ", fmt)

    def display_tikkun_view(self) -> None:
        """Tikkun view displays two columns (modern and STAM)."""
        # Construct the modern and STAM text by joining words.
        modern_words: List[str] = []
        stam_words: List[str] = []
        for word, _trope_group, _symbol in self.content:
            modern_words.append(word)
            stam_words.append(''.join(ch for ch in word if not _is_combining(ch)))
        modern_text = ' '.join(modern_words)
        stam_text = ' '.join(stam_words)
        # Build a minimal HTML table.  Colour modes are ignored here
        # because HTML styling complicates combining the two modes.  A
        # future version could integrate colour into the HTML.
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
    """Return True if the character is a Hebrew diacritic or trope mark.

    This function checks whether the Unicode combining class of
    ``ch`` is non‑zero.  Characters with a combining class of zero
    represent base characters; all others are treated as diacritics or
    trope marks and are removed when stripping the text in STAM mode.
    """
    import unicodedata
    return unicodedata.combining(ch) != 0