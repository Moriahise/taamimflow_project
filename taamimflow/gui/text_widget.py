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
  simple two column table.

Colour highlighting can also be toggled.  In ``trope_colors`` mode the
background of each word is filled based on the trope group.  In
``symbol_colors`` mode a symbol is inserted before each word and
coloured based on the symbol.  In ``no_colors`` mode the text is
rendered in plain black on white.

The widget emits a ``word_clicked`` signal when the user clicks on a
word, carrying the word text, its trope group name and the list of
trope marks.  The main window can connect to this signal to update the
musical notation and translation panels.
"""

from __future__ import annotations

import unicodedata
from typing import Iterable, List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import (
    QColor,
    QFont,
    QBrush,
    QTextCharFormat,
    QTextCursor,
    QMouseEvent,
    QPalette,
)
from PyQt6.QtWidgets import QTextEdit

from ..utils.trope_parser import (
    Token,
    GROUPS,
    get_all_group_colors,
    get_trope_group,
)


# ── Colour tables ───────────────────────────────────────────────────

# Build the default trope colour map from the parser module so that
# both the parser and the widget stay in sync.
DEFAULT_TROPE_COLORS = get_all_group_colors()

# Symbol colours for symbol-colour mode.
SYMBOL_COLORS = {
    "✱": "#00FFFF",
    "◆": "#FF00FF",
    "▲": "#FFFF00",
}


class ModernTorahTextWidget(QTextEdit):
    """Widget for displaying Hebrew cantillation with multiple modes.

    Signals
    -------
    word_clicked(str, str, list)
        Emitted when the user clicks on a word.  Arguments are:
        ``word`` (the raw Hebrew word), ``group_name`` (trope group)
        and ``trope_marks`` (list of mark names on that word).
    """

    word_clicked = pyqtSignal(str, str, list)

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Times New Roman", 22))
        # Dark background like original TropeTrainer
        self.setStyleSheet(
            "QTextEdit { background-color: #1a1a2e; color: white; "
            "border: 2px solid #8B008B; padding: 8px; }"
        )
        self.trope_colors = DEFAULT_TROPE_COLORS.copy()
        self.symbol_colors = SYMBOL_COLORS.copy()
        # Modes
        self.view_mode: str = "modern"
        self.color_mode: str = "trope_colors"
        # Content as Token objects from trope_parser
        self.tokens: List[Token] = []
        # Legacy content as tuples (kept for backward compat)
        self.content: List[Tuple[str, str, str]] = []
        # Track which character positions map to which token index
        self._char_to_token: List[int] = []
        # Currently selected token index
        self._selected_index: int = -1

    # ── Public API ──────────────────────────────────────────────────

    def set_tokens(self, tokens: List[Token]) -> None:
        """Set the widget content from parsed Token objects.

        This is the preferred method.  It preserves full trope
        information for click handling.
        """
        self.tokens = list(tokens)
        # Also populate legacy tuple list for backward compat
        self.content = [
            (t.word, t.group_name, t.symbol) for t in self.tokens
        ]
        self._selected_index = -1
        self.update_display()

    def set_text(self, tokens: Iterable[Tuple[str, str, str]]) -> None:
        """Legacy API: set content from (word, group, symbol) tuples."""
        self.content = list(tokens)
        # Create minimal Token objects
        self.tokens = []
        for word, group, symbol in self.content:
            self.tokens.append(Token(
                word=word,
                group_name=group,
                symbol=symbol,
                color=self.trope_colors.get(group, "#D3D3D3"),
                trope_marks=[group],
                verse_end=False,
            ))
        self._selected_index = -1
        self.update_display()

    def set_view_mode(self, mode: str) -> None:
        if mode in {"modern", "stam", "tikkun"}:
            self.view_mode = mode
            self.update_display()

    def set_color_mode(self, mode: str) -> None:
        if mode in {"no_colors", "trope_colors", "symbol_colors"}:
            self.color_mode = mode
            self.update_display()

    def setPlaceholderText(self, text: str) -> None:
        """Override to set placeholder with appropriate styling."""
        super().setPlaceholderText(text)

    # ── Mouse handling ──────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Detect which word was clicked and emit word_clicked signal."""
        if event.button() == Qt.MouseButton.LeftButton and self.tokens:
            cursor = self.cursorForPosition(event.pos().toPoint() if isinstance(event.pos(), QPointF) else event.pos())
            pos = cursor.position()
            if 0 <= pos < len(self._char_to_token):
                token_idx = self._char_to_token[pos]
                if 0 <= token_idx < len(self.tokens):
                    token = self.tokens[token_idx]
                    self._selected_index = token_idx
                    # Re-render to highlight selected word
                    self.update_display()
                    # Emit signal
                    self.word_clicked.emit(
                        token.word,
                        token.group_name,
                        token.trope_marks,
                    )
        super().mousePressEvent(event)

    # ── Display methods ─────────────────────────────────────────────

    def update_display(self) -> None:
        if not self.tokens:
            self.clear()
            return
        if self.view_mode == "modern":
            self._display_modern()
        elif self.view_mode == "stam":
            self._display_stam()
        elif self.view_mode == "tikkun":
            self._display_tikkun()
        else:
            self._display_modern()

    def _display_modern(self) -> None:
        """Render modern view with trope-coloured backgrounds."""
        self.clear()
        self._char_to_token = []
        cursor = self.textCursor()
        # Set right-to-left alignment for Hebrew
        block_fmt = cursor.blockFormat()
        block_fmt.setAlignment(Qt.AlignmentFlag.AlignRight)
        cursor.setBlockFormat(block_fmt)

        for idx, token in enumerate(self.tokens):
            fmt = QTextCharFormat()
            fmt.setFont(QFont("Times New Roman", 22))

            is_selected = (idx == self._selected_index)

            if self.color_mode == "trope_colors":
                bg_color = token.color
                fmt.setBackground(QBrush(QColor(bg_color)))
                fmt.setForeground(QBrush(QColor("#000000")))
                if is_selected:
                    # Highlight selected word with a border effect
                    fmt.setFontWeight(QFont.Weight.Bold)
                    fmt.setFontUnderline(True)
                    fmt.setUnderlineColor(QColor("#FF0000"))

            elif self.color_mode == "symbol_colors":
                s_color = self.symbol_colors.get(token.symbol, "#FFFFFF")
                fmt.setBackground(QBrush(QColor(s_color)))
                fmt.setForeground(QBrush(QColor("#000000")))
                if is_selected:
                    fmt.setFontWeight(QFont.Weight.Bold)
                    fmt.setFontUnderline(True)

                # Insert symbol
                sym_text = f"{token.symbol} "
                start = len(self._char_to_token)
                cursor.insertText(sym_text, fmt)
                self._char_to_token.extend([idx] * len(sym_text))

            else:
                # no colours
                fmt.setForeground(QBrush(QColor("#FFFFFF")))
                if is_selected:
                    fmt.setFontWeight(QFont.Weight.Bold)
                    fmt.setFontUnderline(True)

            word_text = token.word + " "
            cursor.insertText(word_text, fmt)
            self._char_to_token.extend([idx] * len(word_text))

            # Add verse-end line break
            if token.verse_end:
                cursor.insertText("\n")
                self._char_to_token.append(idx)

    def _display_stam(self) -> None:
        """STAM view: consonants only, optionally coloured."""
        self.clear()
        self._char_to_token = []
        cursor = self.textCursor()
        block_fmt = cursor.blockFormat()
        block_fmt.setAlignment(Qt.AlignmentFlag.AlignRight)
        cursor.setBlockFormat(block_fmt)

        for idx, token in enumerate(self.tokens):
            stripped = _strip_diacritics(token.word)
            fmt = QTextCharFormat()
            fmt.setFont(QFont("Times New Roman", 22))

            is_selected = (idx == self._selected_index)

            if self.color_mode == "trope_colors":
                fmt.setBackground(QBrush(QColor(token.color)))
                fmt.setForeground(QBrush(QColor("#000000")))
            elif self.color_mode == "symbol_colors":
                fmt.setBackground(QBrush(QColor(token.color)))
                fmt.setForeground(QBrush(QColor("#000000")))
            else:
                fmt.setForeground(QBrush(QColor("#FFFFFF")))

            if is_selected:
                fmt.setFontWeight(QFont.Weight.Bold)
                fmt.setFontUnderline(True)

            word_text = stripped + " "
            cursor.insertText(word_text, fmt)
            self._char_to_token.extend([idx] * len(word_text))

            if token.verse_end:
                cursor.insertText("\n")
                self._char_to_token.append(idx)

    def _display_tikkun(self) -> None:
        """Tikkun view: two-column table (modern and STAM)."""
        modern_parts: List[str] = []
        stam_parts: List[str] = []
        for token in self.tokens:
            modern_parts.append(token.word)
            stam_parts.append(_strip_diacritics(token.word))

        modern_text = " ".join(modern_parts)
        stam_text = " ".join(stam_parts)

        html = f"""
        <table width='100%' border='1' style='border-collapse: collapse;
               background-color: #1a1a2e;'>
            <tr>
                <td width='50%' style='padding: 12px; text-align: right;
                    font-size: 20pt; font-family: Times New Roman;
                    color: white; direction: rtl;'>
                    <b>Modern:</b><br/>{modern_text}
                </td>
                <td width='50%' style='padding: 12px; text-align: right;
                    font-size: 20pt; font-family: Times New Roman;
                    color: white; direction: rtl;'>
                    <b>STAM:</b><br/>{stam_text}
                </td>
            </tr>
        </table>
        """
        self.setHtml(html)
        self._char_to_token = []


def _strip_diacritics(word: str) -> str:
    """Remove all combining characters (vowels and tropes) from a word."""
    return "".join(ch for ch in word if unicodedata.combining(ch) == 0)
