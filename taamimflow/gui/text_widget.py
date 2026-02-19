"""Modern Torah text display widget.

This module defines the :class:`ModernTorahTextWidget` class used by the
Ta'amimFlow application.  It extends :class:`QTextEdit` to display
Hebrew text with optional cantillation (trope) highlighting.  Three
view modes are supported:

* ``modern`` – display the text exactly as provided, including vowels
  and trope marks.
* ``stam`` – display only the consonantal text (STAM Sefarad) by
  stripping vowels and trope marks.  Uses a proper STAM font with
  tagin (crowns) when available.
* ``tikkun`` – present the modern and STAM text side-by-side in a
  simple two column table.

Colour highlighting can also be toggled.  In ``trope_colors`` mode the
background of each word is filled based on the trope group.  In
``symbol_colors`` mode a symbol is inserted before each word and
coloured based on the symbol.  In ``no_colors`` mode the text is
rendered in plain black on white.

**Verse / Chapter / Aliyah metadata support:**

The widget accepts optional per-token metadata via
:meth:`set_tokens_with_metadata`.  When metadata is present, verse
numbers appear on the right margin of each verse row (matching the
original TropeTrainer layout) and aliyah (reading division) headers
are rendered as coloured banners between the relevant verses.

Each metadata entry is a dict with the following keys::

    {
        "chapter":       int,   # e.g. 12
        "verse":         int,   # e.g. 21
        "is_verse_start":  bool,
        "aliyah_num":    int,   # 1–7 (or Maftir=8); 0 = no new aliyah
        "aliyah_name":   str,   # e.g. "Rishon", "Sheni" …
        "is_aliyah_start": bool,
    }

The widget emits a ``word_clicked`` signal when the user clicks on a
word, carrying the word text, its trope group name and the list of
trope marks.  The main window can connect to this signal to update the
musical notation and translation panels.
"""

from __future__ import annotations

import unicodedata
from typing import Dict, Iterable, List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QBrush,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QMouseEvent,
    QPalette,
)
from PyQt6.QtWidgets import QTextEdit, QAbstractScrollArea

from ..utils.trope_parser import (
    Token,
    GROUPS,
    get_all_group_colors,
    get_trope_group,
)


# ── Colour tables ────────────────────────────────────────────────────

DEFAULT_TROPE_COLORS = get_all_group_colors()

SYMBOL_COLORS = {
    "✱": "#00FFFF",
    "◆": "#FF00FF",
    "▲": "#FFFF00",
}

# ── Aliyah meta ─────────────────────────────────────────────────────

#: Human-readable aliyah names in order (1-indexed).
ALIYAH_NAMES: Dict[int, str] = {
    1: "Rishon",
    2: "Sheni",
    3: "Shlishi",
    4: "Revi'i",
    5: "Chamishi",
    6: "Shishi",
    7: "Shevi'i",
    8: "Maftir",
}

#: Background colours for aliyah header banners.
ALIYAH_BANNER_COLORS: Dict[int, str] = {
    1: "#6B3FA0",   # dark purple
    2: "#1565C0",   # dark blue
    3: "#1B5E20",   # dark green
    4: "#E65100",   # dark orange
    5: "#880E4F",   # dark rose
    6: "#00695C",   # dark teal
    7: "#4A148C",   # deep purple
    8: "#4E342E",   # dark brown  (Maftir)
}

# ── STAM font resolution ─────────────────────────────────────────────

# Preferred STAM Sefarad fonts with tagin (crowns), in order of priority.
# "Keter YG" (Yoram Gnat) is the most authentic and freely available.
_STAM_FONT_CANDIDATES = [
    "Keter YG",
    "SeferTorah",
    "Ezra SIL",       # no tagin but correct letterforms
    "FreeSerif",
    "Times New Roman",
]

def _resolve_stam_font() -> QFont:
    """Return the best available STAM Sefarad font."""
    families = QFontDatabase.families()
    for name in _STAM_FONT_CANDIDATES:
        if name in families:
            return QFont(name, 24)
    # Ultimate fallback – system serif
    f = QFont()
    f.setStyleHint(QFont.StyleHint.Serif)
    f.setPointSize(24)
    return f


_STAM_FONT: Optional[QFont] = None   # resolved lazily on first use


def get_stam_font() -> QFont:
    global _STAM_FONT
    if _STAM_FONT is None:
        _STAM_FONT = _resolve_stam_font()
    return _STAM_FONT


def _darken_color(hex_color: str, factor: float = 0.55) -> str:
    """Return a darkened version of a hex colour string.

    ``factor`` is the brightness multiplier (0 = black, 1 = unchanged).
    Used to highlight the selected word with a darker background instead
    of an underline, matching the original TropeTrainer look.
    """
    c = QColor(hex_color)
    r = int(c.red() * factor)
    g = int(c.green() * factor)
    b = int(c.blue() * factor)
    return QColor(r, g, b).name()


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
        # ── RTL layout for Hebrew text ──
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.trope_colors = DEFAULT_TROPE_COLORS.copy()
        self.symbol_colors = SYMBOL_COLORS.copy()
        # Modes
        self.view_mode: str = "modern"
        self.color_mode: str = "trope_colors"
        # Content as Token objects from trope_parser
        self.tokens: List[Token] = []
        # Legacy content as tuples (kept for backward compat)
        self.content: List[Tuple[str, str, str]] = []
        # Per-token verse/chapter/aliyah metadata (optional)
        self.verse_metadata: List[dict] = []
        # Track which character positions map to which token index
        self._char_to_token: List[int] = []
        # Currently selected token index
        self._selected_index: int = -1

    # ── Public API ───────────────────────────────────────────────────

    def set_tokens(self, tokens: List[Token]) -> None:
        """Set the widget content from parsed Token objects.

        This is the preferred method.  It preserves full trope
        information for click handling.  Verse metadata is cleared;
        use :meth:`set_tokens_with_metadata` to supply verse/aliyah
        information.
        """
        self.tokens = list(tokens)
        self.content = [
            (t.word, t.group_name, t.symbol) for t in self.tokens
        ]
        self.verse_metadata = []
        self._selected_index = -1
        self.update_display()

    def set_tokens_with_metadata(
        self,
        tokens: List[Token],
        verse_metadata: List[dict],
    ) -> None:
        """Set tokens together with per-token verse/chapter/aliyah metadata.

        :param tokens: List of :class:`Token` objects.
        :param verse_metadata: List of dicts, one per token, each containing
            the keys ``chapter``, ``verse``, ``is_verse_start``,
            ``aliyah_num``, ``aliyah_name`` and ``is_aliyah_start``.
            The list length must match *tokens*.  If lengths differ the
            metadata is silently ignored.
        """
        self.tokens = list(tokens)
        self.content = [
            (t.word, t.group_name, t.symbol) for t in self.tokens
        ]
        if len(verse_metadata) == len(self.tokens):
            self.verse_metadata = list(verse_metadata)
        else:
            self.verse_metadata = []
        self._selected_index = -1
        self.update_display()

    def set_text(self, tokens: Iterable[Tuple[str, str, str]]) -> None:
        """Legacy API: set content from (word, group, symbol) tuples."""
        self.content = list(tokens)
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
        self.verse_metadata = []
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

    def highlight_word_at_index(self, index: int) -> None:
        """Hebe das Wort mit dem gegebenen Index farbig hervor.

        Wird während der Wiedergabe von main_window aufgerufen, um das
        aktuell gesprochene Wort wie in TropeTrainer darzustellen.
        Die Scrollposition bleibt erhalten.
        """
        if not self.tokens:
            return
        index = max(0, min(index, len(self.tokens) - 1))
        if self._selected_index == index:
            return  # Kein unnötiges Re-Render
        # Scrollposition merken
        vbar = self.verticalScrollBar()
        hbar = self.horizontalScrollBar()
        v_pos = vbar.value()
        h_pos = hbar.value()
        self._selected_index = index
        self.update_display()
        # Scrollposition wiederherstellen
        vbar.setValue(v_pos)
        hbar.setValue(h_pos)

    def setPlaceholderText(self, text: str) -> None:
        super().setPlaceholderText(text)

    # ── Mouse handling ────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Detect which word was clicked and emit word_clicked signal.

        The vertical scroll position is saved before and restored after
        the re-render so the view does not jump to the top on every click.
        """
        if event.button() == Qt.MouseButton.LeftButton and self.tokens:
            pos_point = (
                event.pos().toPoint()
                if isinstance(event.pos(), QPointF)
                else event.pos()
            )
            cursor = self.cursorForPosition(pos_point)
            pos = cursor.position()
            if 0 <= pos < len(self._char_to_token):
                token_idx = self._char_to_token[pos]
                if 0 <= token_idx < len(self.tokens):
                    token = self.tokens[token_idx]
                    self._selected_index = token_idx
                    # ── Save scroll position before re-render ──
                    vbar = self.verticalScrollBar()
                    hbar = self.horizontalScrollBar()
                    v_pos = vbar.value()
                    h_pos = hbar.value()
                    self.update_display()
                    # ── Restore scroll position after re-render ──
                    vbar.setValue(v_pos)
                    hbar.setValue(h_pos)
                    self.word_clicked.emit(
                        token.word,
                        token.group_name,
                        token.trope_marks,
                    )
        # Do NOT call super() – we handle everything ourselves.
        # This also prevents Qt from moving the text cursor / selecting text.

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Treat double-click exactly like a single click.

        By default QTextEdit selects the word under the cursor on a
        double-click and moves the internal text cursor, which causes the
        display to jump.  Routing double-clicks through our single-click
        handler avoids both problems.
        """
        self.mousePressEvent(event)

    # ── Display dispatcher ───────────────────────────────────────────

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

    # ── Helper: verse number / aliyah banner insertion ────────────────

    def _meta(self, idx: int) -> Optional[dict]:
        """Return the metadata dict for token *idx*, or ``None``."""
        if self.verse_metadata and 0 <= idx < len(self.verse_metadata):
            return self.verse_metadata[idx]
        return None

    def _insert_aliyah_banner(
        self, cursor: QTextCursor, aliyah_num: int, aliyah_name: str
    ) -> None:
        """Insert a full-width coloured aliyah header banner."""
        display_name = aliyah_name or ALIYAH_NAMES.get(aliyah_num, f"Aliyah {aliyah_num}")
        color_hex = ALIYAH_BANNER_COLORS.get(aliyah_num, "#555555")

        blank_fmt = QTextCharFormat()
        blank_fmt.setBackground(QBrush(QColor("#1a1a2e")))
        blank_fmt.setForeground(QBrush(QColor("#1a1a2e")))

        # ── blank line before banner ──
        # insertBlock() inserts a block-separator at the current document
        # position. That separator occupies exactly one position and MUST be
        # tracked in _char_to_token or every subsequent position will be off.
        cursor.insertBlock()
        self._char_to_token.append(-1)          # ← block separator position
        cursor.insertText(" ", blank_fmt)
        self._char_to_token.append(-1)          # ← the space character

        # ── banner block ──
        banner_block_fmt = QTextBlockFormat()
        banner_block_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner_block_fmt.setBackground(QBrush(QColor(color_hex)))
        banner_block_fmt.setTopMargin(4)
        banner_block_fmt.setBottomMargin(4)
        cursor.insertBlock(banner_block_fmt)
        self._char_to_token.append(-1)          # ← block separator position

        banner_fmt = QTextCharFormat()
        banner_fmt.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        banner_fmt.setBackground(QBrush(QColor(color_hex)))
        banner_fmt.setForeground(QBrush(QColor("#FFFFFF")))
        banner_text = f"  ── {display_name}  (Aliyah {aliyah_num})  ──  "
        cursor.insertText(banner_text, banner_fmt)
        self._char_to_token.extend([-1] * len(banner_text))   # ← banner chars

        # ── blank line after banner ──
        cursor.insertBlock()
        self._char_to_token.append(-1)          # ← block separator position
        cursor.insertText(" ", blank_fmt)
        self._char_to_token.append(-1)          # ← the space character

    def _insert_verse_number(
        self,
        cursor: QTextCursor,
        chapter: int,
        verse: int,
        aliyah_num: int = 0,
    ) -> None:
        """Insert a verse label at the start of a new RTL block.

        In RTL layout the first text inserted into a block appears on
        the RIGHT margin.  Inserting ``chapter:verse`` first therefore
        places it at the far right – exactly like the original
        TropeTrainer.  Words appended afterwards flow left from there.

        Format: ``26:1`` (chapter:verse) in light-gray on the right.
        """
        # ── New block: RTL, justified (Blocksatz) ──
        verse_block_fmt = QTextBlockFormat()
        verse_block_fmt.setAlignment(Qt.AlignmentFlag.AlignJustify)
        verse_block_fmt.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        verse_block_fmt.setTopMargin(3)
        verse_block_fmt.setBottomMargin(3)
        cursor.insertBlock(verse_block_fmt)
        self._char_to_token.append(-1)          # ← block separator position

        # ── Verse number label: "chapter:verse" ──
        verse_fmt = QTextCharFormat()
        verse_fmt.setFont(QFont("Arial", 10))
        verse_fmt.setForeground(QBrush(QColor("#A0A0A0")))
        verse_fmt.setBackground(QBrush(QColor("#1a1a2e")))

        label = f"{chapter}:{verse}  "
        cursor.insertText(label, verse_fmt)
        self._char_to_token.extend([-1] * len(label))

    # ── Modern display ───────────────────────────────────────────────

    def _display_modern(self) -> None:
        """Render modern view with trope-coloured backgrounds.

        When verse metadata is available, verse numbers appear at the
        right margin (inserted first in the RTL block) and aliyah
        dividers are shown as coloured banners.
        """
        self.clear()
        self._char_to_token = []
        cursor = self.textCursor()
        has_meta = bool(self.verse_metadata)

        # ── Set up first block ──
        if has_meta:
            first_meta = self.verse_metadata[0] if self.verse_metadata else {}
            if first_meta.get("is_aliyah_start"):
                self._insert_aliyah_banner(
                    cursor,
                    first_meta.get("aliyah_num", 1),
                    first_meta.get("aliyah_name", ""),
                )
            # Insert first verse number (creates new RTL block internally)
            self._insert_verse_number(
                cursor,
                first_meta.get("chapter", 1),
                first_meta.get("verse", 1),
            )
        else:
            block_fmt = QTextBlockFormat()
            block_fmt.setAlignment(Qt.AlignmentFlag.AlignJustify)
            block_fmt.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            cursor.setBlockFormat(block_fmt)

        # ── Render tokens ──
        prev_verse: Optional[int] = None
        prev_chapter: Optional[int] = None

        for idx, token in enumerate(self.tokens):
            meta = self._meta(idx)
            cur_verse = meta["verse"] if meta else None
            cur_chapter = meta["chapter"] if meta else None

            # ── Aliyah divider (start of a new aliyah, not the first) ──
            if (
                meta
                and meta.get("is_aliyah_start")
                and prev_verse is not None          # not the very first token
            ):
                self._insert_aliyah_banner(
                    cursor,
                    meta.get("aliyah_num", 0),
                    meta.get("aliyah_name", ""),
                )

            # ── New verse row ──
            if (
                meta
                and meta.get("is_verse_start")
                and prev_verse is not None          # not the very first token
            ):
                self._insert_verse_number(
                    cursor,
                    cur_chapter,
                    cur_verse,
                )

            # ── Format and insert word ──
            fmt = QTextCharFormat()
            fmt.setFont(QFont("Times New Roman", 22))
            is_selected = (idx == self._selected_index)

            if self.color_mode == "trope_colors":
                bg_color = token.color
                if is_selected:
                    # Darker background to highlight selected word
                    bg_color = _darken_color(token.color)
                fmt.setBackground(QBrush(QColor(bg_color)))
                fmt.setForeground(QBrush(QColor("#000000")))

            elif self.color_mode == "symbol_colors":
                s_color = self.symbol_colors.get(token.symbol, "#FFFFFF")
                if is_selected:
                    s_color = _darken_color(s_color)
                fmt.setBackground(QBrush(QColor(s_color)))
                fmt.setForeground(QBrush(QColor("#000000")))
                sym_text = f"{token.symbol} "
                cursor.insertText(sym_text, fmt)
                self._char_to_token.extend([idx] * len(sym_text))

            else:
                # no colours: white text; selected = slightly highlighted
                if is_selected:
                    fmt.setBackground(QBrush(QColor("#3a3a5e")))
                fmt.setForeground(QBrush(QColor("#FFFFFF")))

            word_text = token.word + " "
            cursor.insertText(word_text, fmt)
            self._char_to_token.extend([idx] * len(word_text))

            # ── End-of-verse line break (no-metadata fallback) ──
            if token.verse_end and not has_meta:
                cursor.insertBlock()
                self._char_to_token.append(-1)   # ← block separator position
                fb = QTextBlockFormat()
                fb.setAlignment(Qt.AlignmentFlag.AlignJustify)
                fb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
                cursor.setBlockFormat(fb)

            if meta:
                prev_verse = cur_verse
                prev_chapter = cur_chapter

    # ── STAM display ─────────────────────────────────────────────────

    def _display_stam(self) -> None:
        """STAM Sefarad view: consonants only with proper STAM font.

        Uses the best available STAM Sefarad font (e.g. "Keter YG") so
        that tagim (crowns) on the letters ש ע ס נ ז ג ד ק ט ל י render
        correctly.  Verse numbers and aliyah banners are included when
        metadata is available.
        """
        self.clear()
        self._char_to_token = []
        cursor = self.textCursor()
        stam_font = get_stam_font()
        has_meta = bool(self.verse_metadata)

        if has_meta:
            first_meta = self.verse_metadata[0] if self.verse_metadata else {}
            if first_meta.get("is_aliyah_start"):
                self._insert_aliyah_banner(
                    cursor,
                    first_meta.get("aliyah_num", 1),
                    first_meta.get("aliyah_name", ""),
                )
            self._insert_verse_number(
                cursor,
                first_meta.get("chapter", 1),
                first_meta.get("verse", 1),
            )
        else:
            block_fmt = QTextBlockFormat()
            block_fmt.setAlignment(Qt.AlignmentFlag.AlignJustify)
            block_fmt.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            cursor.setBlockFormat(block_fmt)

        prev_verse: Optional[int] = None

        for idx, token in enumerate(self.tokens):
            meta = self._meta(idx)
            stripped = _strip_diacritics(token.word)
            cur_verse = meta["verse"] if meta else None

            if (
                meta
                and meta.get("is_aliyah_start")
                and prev_verse is not None
            ):
                self._insert_aliyah_banner(
                    cursor,
                    meta.get("aliyah_num", 0),
                    meta.get("aliyah_name", ""),
                )

            if (
                meta
                and meta.get("is_verse_start")
                and prev_verse is not None
            ):
                self._insert_verse_number(
                    cursor,
                    meta.get("chapter", 1),
                    cur_verse,
                )

            fmt = QTextCharFormat()
            fmt.setFont(stam_font)
            is_selected = (idx == self._selected_index)

            if self.color_mode == "trope_colors":
                bg = _darken_color(token.color) if is_selected else token.color
                fmt.setBackground(QBrush(QColor(bg)))
                fmt.setForeground(QBrush(QColor("#000000")))
            elif self.color_mode == "symbol_colors":
                bg = _darken_color(token.color) if is_selected else token.color
                fmt.setBackground(QBrush(QColor(bg)))
                fmt.setForeground(QBrush(QColor("#000000")))
            else:
                if is_selected:
                    fmt.setBackground(QBrush(QColor("#3a3a5e")))
                fmt.setForeground(QBrush(QColor("#FFFFFF")))

            word_text = stripped + " "
            cursor.insertText(word_text, fmt)
            self._char_to_token.extend([idx] * len(word_text))

            if token.verse_end and not has_meta:
                cursor.insertBlock()
                self._char_to_token.append(-1)   # ← block separator position
                fb = QTextBlockFormat()
                fb.setAlignment(Qt.AlignmentFlag.AlignJustify)
                fb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
                cursor.setBlockFormat(fb)

            if meta:
                prev_verse = cur_verse

    # ── Tikkun display ───────────────────────────────────────────────

    def _display_tikkun(self) -> None:
        """Tikkun view: two-column table (modern | STAM Sefarad).

        Left column: modern text with vowels and tropes.
        Right column: STAM Sefarad consonantal text.

        Verse numbers and aliyah headers are rendered in both columns
        when metadata is available.
        """
        has_meta = bool(self.verse_metadata)
        stam_font_name = get_stam_font().family()

        # ── Group tokens by verse ──
        if has_meta:
            verses: List[dict] = []
            current_verse_tokens: List[Token] = []
            current_meta: dict = {}
            for idx, token in enumerate(self.tokens):
                meta = self._meta(idx)
                if meta and meta.get("is_verse_start") and current_verse_tokens:
                    verses.append({
                        "tokens": current_verse_tokens,
                        "meta": current_meta,
                    })
                    current_verse_tokens = []
                current_meta = meta or {}
                current_verse_tokens.append(token)
            if current_verse_tokens:
                verses.append({
                    "tokens": current_verse_tokens,
                    "meta": current_meta,
                })
        else:
            # No metadata: treat whole content as one block
            verses = [{"tokens": self.tokens, "meta": {}}]

        # ── Build HTML ──
        rows_html = ""
        last_aliyah = -1

        for verse_data in verses:
            meta = verse_data["meta"]
            tokens_in_verse = verse_data["tokens"]

            # Aliyah banner row
            aliyah_num = meta.get("aliyah_num", 0)
            if aliyah_num and aliyah_num != last_aliyah and meta.get("is_aliyah_start"):
                last_aliyah = aliyah_num
                color_hex = ALIYAH_BANNER_COLORS.get(aliyah_num, "#555555")
                display_name = meta.get("aliyah_name") or ALIYAH_NAMES.get(aliyah_num, f"Aliyah {aliyah_num}")
                rows_html += (
                    f"<tr><td colspan='3' style='"
                    f"background-color:{color_hex}; color:white; font-size:11pt; "
                    f"font-weight:bold; text-align:center; padding:6px;'>"
                    f"── {display_name}  (Aliyah {aliyah_num}) ──"
                    f"</td></tr>"
                )

            # Verse number cell
            chapter = meta.get("chapter", "")
            verse = meta.get("verse", "")
            verse_label = f"{chapter}:{verse}" if chapter and verse else ""

            modern_words = " ".join(t.word for t in tokens_in_verse)
            stam_words = " ".join(_strip_diacritics(t.word) for t in tokens_in_verse)

            rows_html += (
                f"<tr>"
                f"<td style='width:8%; color:#A0A0A0; font-size:10pt; "
                f"  text-align:center; vertical-align:top; padding:4px;'>"
                f"  {verse_label}"
                f"</td>"
                f"<td style='width:46%; padding:8px; text-align:right; "
                f"  font-size:20pt; font-family:Times New Roman; "
                f"  color:white; direction:rtl; vertical-align:top;'>"
                f"  {modern_words}"
                f"</td>"
                f"<td style='width:46%; padding:8px; text-align:right; "
                f"  font-size:22pt; font-family:\"{stam_font_name}\"; "
                f"  color:white; direction:rtl; vertical-align:top;'>"
                f"  {stam_words}"
                f"</td>"
                f"</tr>"
            )

        html = (
            "<table width='100%' border='0' style='"
            "border-collapse:collapse; background-color:#1a1a2e;'>"
            "<tr>"
            "<th style='color:#A0A0A0; font-size:10pt; padding:4px;'>#</th>"
            "<th style='color:#D0D0D0; font-size:11pt; padding:4px;'>Modern</th>"
            "<th style='color:#D0D0D0; font-size:11pt; padding:4px;'>STAM Sefarad</th>"
            "</tr>"
            + rows_html
            + "</table>"
        )
        self.setHtml(html)
        self._char_to_token = []


# ── Utility ───────────────────────────────────────────────────────────

def _strip_diacritics(word: str) -> str:
    """Remove all combining characters (vowels and tropes) from a word."""
    return "".join(ch for ch in word if unicodedata.combining(ch) == 0)


# ── Chapter lengths for all Tanach books ─────────────────────────────
# Maps (book_num, chapter) → number of verses in that chapter.
# book_num mirrors sedrot_parser._BOOK_INFO:
#   1=Bereshit 2=Shemot 3=Vayikra 4=Bamidbar 5=Devarim
#   6=Joshua 7=Judges 8=I Samuel 9=II Samuel 10=I Kings 11=II Kings
#   12=Isaiah 13=Jeremiah 14=Ezekiel 15=Hosea 16=Joel 17=Amos 18=Obadiah
#   19=Jonah 20=Micah 21=Nahum 22=Habakkuk 23=Zephaniah 24=Haggai
#   25=Zechariah 26=Malachi 27=Psalms 28=Proverbs 29=Job
#   30=Ruth 31=Lamentations 32=Kohelet 33=Esther 34=Song of Songs
#   35=Nehemiah 36=Ezra 37=I Chronicles 38=II Chronicles
# Used by build_verse_metadata to advance the chapter number correctly.
_TORAH_CHAPTER_LENGTHS: Dict[Tuple[int, int], int] = {
    # ── Bereshit (Genesis) ──
    (1,1):31,(1,2):25,(1,3):24,(1,4):26,(1,5):32,(1,6):22,(1,7):24,
    (1,8):22,(1,9):29,(1,10):32,(1,11):32,(1,12):20,(1,13):18,(1,14):24,
    (1,15):21,(1,16):16,(1,17):27,(1,18):33,(1,19):38,(1,20):18,(1,21):34,
    (1,22):24,(1,23):20,(1,24):67,(1,25):34,(1,26):35,(1,27):46,(1,28):22,
    (1,29):35,(1,30):43,(1,31):54,(1,32):33,(1,33):20,(1,34):31,(1,35):29,
    (1,36):43,(1,37):36,(1,38):30,(1,39):23,(1,40):23,(1,41):57,(1,42):38,
    (1,43):34,(1,44):34,(1,45):28,(1,46):34,(1,47):31,(1,48):22,(1,49):33,
    (1,50):26,
    # ── Shemot (Exodus) ──
    (2,1):22,(2,2):25,(2,3):22,(2,4):31,(2,5):23,(2,6):30,(2,7):29,
    (2,8):28,(2,9):35,(2,10):29,(2,11):10,(2,12):51,(2,13):22,(2,14):31,
    (2,15):27,(2,16):36,(2,17):16,(2,18):27,(2,19):25,(2,20):23,(2,21):37,
    (2,22):30,(2,23):33,(2,24):18,(2,25):40,(2,26):37,(2,27):21,(2,28):43,
    (2,29):46,(2,30):38,(2,31):18,(2,32):35,(2,33):23,(2,34):35,(2,35):35,
    (2,36):38,(2,37):29,(2,38):31,(2,39):43,(2,40):38,
    # ── Vayikra (Leviticus) ──
    (3,1):17,(3,2):16,(3,3):17,(3,4):35,(3,5):26,(3,6):23,(3,7):38,
    (3,8):36,(3,9):24,(3,10):20,(3,11):47,(3,12):8,(3,13):59,(3,14):57,
    (3,15):33,(3,16):34,(3,17):16,(3,18):30,(3,19):37,(3,20):27,(3,21):24,
    (3,22):33,(3,23):44,(3,24):23,(3,25):55,(3,26):46,(3,27):34,
    # ── Bamidbar (Numbers) ──
    (4,1):54,(4,2):34,(4,3):51,(4,4):49,(4,5):31,(4,6):27,(4,7):89,
    (4,8):26,(4,9):23,(4,10):36,(4,11):35,(4,12):16,(4,13):33,(4,14):45,
    (4,15):41,(4,16):35,(4,17):28,(4,18):32,(4,19):22,(4,20):29,(4,21):35,
    (4,22):41,(4,23):30,(4,24):25,(4,25):18,(4,26):65,(4,27):23,(4,28):31,
    (4,29):39,(4,30):17,(4,31):54,(4,32):42,(4,33):56,(4,34):29,(4,35):34,
    (4,36):13,
    # ── Devarim (Deuteronomy) ──
    (5,1):46,(5,2):37,(5,3):29,(5,4):49,(5,5):30,(5,6):25,(5,7):26,
    (5,8):20,(5,9):29,(5,10):22,(5,11):32,(5,12):31,(5,13):19,(5,14):29,
    (5,15):23,(5,16):22,(5,17):20,(5,18):22,(5,19):21,(5,20):20,(5,21):23,
    (5,22):29,(5,23):26,(5,24):22,(5,25):19,(5,26):19,(5,27):26,(5,28):69,
    (5,29):28,(5,30):20,(5,31):30,(5,32):52,(5,33):29,(5,34):12,
    # ── Joshua (6) ──
    (6,1):18,(6,2):24,(6,3):17,(6,4):24,(6,5):15,(6,6):27,(6,7):26,
    (6,8):35,(6,9):27,(6,10):43,(6,11):23,(6,12):24,(6,13):33,(6,14):15,
    (6,15):63,(6,16):10,(6,17):18,(6,18):28,(6,19):51,(6,20):9,(6,21):45,
    (6,22):34,(6,23):16,(6,24):33,
    # ── Judges (7) ──
    (7,1):36,(7,2):23,(7,3):31,(7,4):24,(7,5):31,(7,6):40,(7,7):25,
    (7,8):35,(7,9):57,(7,10):18,(7,11):40,(7,12):15,(7,13):25,(7,14):20,
    (7,15):20,(7,16):31,(7,17):13,(7,18):31,(7,19):30,(7,20):48,(7,21):25,
    # ── I Samuel (8) ──
    (8,1):28,(8,2):36,(8,3):21,(8,4):22,(8,5):12,(8,6):21,(8,7):17,
    (8,8):22,(8,9):27,(8,10):27,(8,11):15,(8,12):25,(8,13):23,(8,14):52,
    (8,15):35,(8,16):23,(8,17):58,(8,18):30,(8,19):24,(8,20):42,(8,21):16,
    (8,22):23,(8,23):28,(8,24):23,(8,25):44,(8,26):25,(8,27):12,(8,28):25,
    (8,29):11,(8,30):31,(8,31):13,
    # ── II Samuel (9) ──
    (9,1):27,(9,2):32,(9,3):39,(9,4):12,(9,5):25,(9,6):23,(9,7):29,
    (9,8):18,(9,9):13,(9,10):19,(9,11):27,(9,12):31,(9,13):39,(9,14):33,
    (9,15):37,(9,16):23,(9,17):29,(9,18):32,(9,19):44,(9,20):26,(9,21):22,
    (9,22):51,(9,23):39,(9,24):25,
    # ── I Kings (10) ──
    (10,1):53,(10,2):46,(10,3):28,(10,4):20,(10,5):32,(10,6):38,(10,7):51,
    (10,8):66,(10,9):28,(10,10):29,(10,11):43,(10,12):33,(10,13):34,(10,14):31,
    (10,15):34,(10,16):34,(10,17):24,(10,18):46,(10,19):21,(10,20):43,
    (10,21):29,(10,22):54,
    # ── II Kings (11) ──
    (11,1):18,(11,2):25,(11,3):27,(11,4):44,(11,5):27,(11,6):33,(11,7):20,
    (11,8):29,(11,9):37,(11,10):36,(11,11):20,(11,12):22,(11,13):25,
    (11,14):29,(11,15):38,(11,16):20,(11,17):41,(11,18):37,(11,19):37,
    (11,20):21,(11,21):26,(11,22):20,(11,23):37,(11,24):20,(11,25):30,
    # ── Isaiah (12) ──
    (12,1):31,(12,2):22,(12,3):26,(12,4):6,(12,5):30,(12,6):13,(12,7):25,
    (12,8):23,(12,9):20,(12,10):34,(12,11):16,(12,12):6,(12,13):22,(12,14):32,
    (12,15):9,(12,16):14,(12,17):14,(12,18):7,(12,19):25,(12,20):6,
    (12,21):17,(12,22):25,(12,23):18,(12,24):23,(12,25):12,(12,26):21,
    (12,27):13,(12,28):29,(12,29):24,(12,30):33,(12,31):9,(12,32):20,
    (12,33):24,(12,34):17,(12,35):10,(12,36):22,(12,37):38,(12,38):22,
    (12,39):8,(12,40):31,(12,41):29,(12,42):25,(12,43):28,(12,44):28,
    (12,45):25,(12,46):13,(12,47):15,(12,48):22,(12,49):26,(12,50):11,
    (12,51):23,(12,52):15,(12,53):12,(12,54):17,(12,55):13,(12,56):12,
    (12,57):21,(12,58):14,(12,59):21,(12,60):22,(12,61):11,(12,62):12,
    (12,63):19,(12,64):11,(12,65):25,(12,66):24,
    # ── Jeremiah (13) ──
    (13,1):19,(13,2):37,(13,3):25,(13,4):31,(13,5):31,(13,6):30,
    (13,7):34,(13,8):23,(13,9):25,(13,10):25,(13,11):23,(13,12):17,
    (13,13):27,(13,14):22,(13,15):21,(13,16):21,(13,17):27,(13,18):23,
    (13,19):15,(13,20):18,(13,21):14,(13,22):30,(13,23):40,(13,24):10,
    (13,25):38,(13,26):24,(13,27):22,(13,28):17,(13,29):32,(13,30):24,
    (13,31):40,(13,32):44,(13,33):26,(13,34):22,(13,35):19,(13,36):32,
    (13,37):21,(13,38):28,(13,39):18,(13,40):16,(13,41):18,(13,42):22,
    (13,43):13,(13,44):30,(13,45):5,(13,46):28,(13,47):7,(13,48):47,
    (13,49):39,(13,50):46,(13,51):64,(13,52):34,
    # ── Ezekiel (14) ──
    (14,1):28,(14,2):10,(14,3):27,(14,4):17,(14,5):17,(14,6):14,
    (14,7):27,(14,8):18,(14,9):11,(14,10):22,(14,11):25,(14,12):28,
    (14,13):23,(14,14):23,(14,15):8,(14,16):63,(14,17):24,(14,18):32,
    (14,19):14,(14,20):44,(14,21):37,(14,22):31,(14,23):49,(14,24):27,
    (14,25):17,(14,26):21,(14,27):36,(14,28):26,(14,29):21,(14,30):26,
    (14,31):18,(14,32):32,(14,33):33,(14,34):31,(14,35):15,(14,36):38,
    (14,37):28,(14,38):23,(14,39):29,(14,40):49,(14,41):26,(14,42):20,
    (14,43):27,(14,44):31,(14,45):25,(14,46):24,(14,47):23,(14,48):35,
    # ── Hosea (15) ──
    (15,1):9,(15,2):25,(15,3):5,(15,4):19,(15,5):15,(15,6):11,
    (15,7):16,(15,8):14,(15,9):17,(15,10):15,(15,11):11,(15,12):15,
    (15,13):15,(15,14):10,
    # ── Joel (16) ──
    (16,1):20,(16,2):27,(16,3):5,(16,4):21,
    # ── Amos (17) ──
    (17,1):15,(17,2):16,(17,3):15,(17,4):13,(17,5):27,(17,6):14,
    (17,7):17,(17,8):14,(17,9):15,
    # ── Obadiah (18) ──
    (18,1):21,
    # ── Jonah (19) ──
    (19,1):16,(19,2):11,(19,3):10,(19,4):11,
    # ── Micah (20) ──
    (20,1):16,(20,2):13,(20,3):12,(20,4):14,(20,5):14,(20,6):16,(20,7):20,
    # ── Nahum (21) ──
    (21,1):14,(21,2):14,(21,3):19,
    # ── Habakkuk (22) ──
    (22,1):17,(22,2):20,(22,3):19,
    # ── Zephaniah (23) ──
    (23,1):18,(23,2):15,(23,3):20,
    # ── Haggai (24) ──
    (24,1):15,(24,2):23,
    # ── Zechariah (25) ──
    (25,1):17,(25,2):17,(25,3):10,(25,4):14,(25,5):11,(25,6):15,
    (25,7):14,(25,8):23,(25,9):17,(25,10):12,(25,11):17,(25,12):14,
    (25,13):9,(25,14):21,
    # ── Malachi (26) ──
    (26,1):14,(26,2):17,(26,3):24,
    # ── Ruth (30) ──
    (30,1):22,(30,2):23,(30,3):18,(30,4):22,
    # ── Lamentations (31) ──
    (31,1):22,(31,2):22,(31,3):66,(31,4):22,(31,5):22,
    # ── Kohelet / Ecclesiastes (32) ──
    (32,1):18,(32,2):26,(32,3):22,(32,4):17,(32,5):19,(32,6):12,
    (32,7):29,(32,8):17,(32,9):18,(32,10):20,(32,11):10,(32,12):14,
    # ── Esther (33) ──
    (33,1):22,(33,2):23,(33,3):15,(33,4):17,(33,5):14,(33,6):14,
    (33,7):10,(33,8):17,(33,9):32,(33,10):3,
    # ── Song of Songs (34) ──
    (34,1):17,(34,2):17,(34,3):11,(34,4):16,(34,5):16,(34,6):12,
    (34,7):14,(34,8):14,
    # ── Nehemiah (35) ──
    (35,1):11,(35,2):20,(35,3):38,(35,4):17,(35,5):19,(35,6):19,
    (35,7):72,(35,8):18,(35,9):37,(35,10):40,(35,11):36,(35,12):47,
    (35,13):31,
    # ── Psalms/Tehillim (27) ──  [WLC: 150 chapters, 2527 verses]
    (27,1):6,(27,2):12,(27,3):9,(27,4):9,(27,5):13,(27,6):11,(27,7):18,(27,8):10,(27,9):21,(27,10):18,
    (27,11):7,(27,12):9,(27,13):6,(27,14):7,(27,15):5,(27,16):11,(27,17):15,(27,18):51,(27,19):15,(27,20):10,
    (27,21):14,(27,22):32,(27,23):6,(27,24):10,(27,25):22,(27,26):12,(27,27):14,(27,28):9,(27,29):11,(27,30):13,
    (27,31):25,(27,32):11,(27,33):22,(27,34):23,(27,35):28,(27,36):13,(27,37):40,(27,38):23,(27,39):14,(27,40):18,
    (27,41):14,(27,42):12,(27,43):5,(27,44):27,(27,45):18,(27,46):12,(27,47):10,(27,48):15,(27,49):21,(27,50):23,
    (27,51):21,(27,52):11,(27,53):7,(27,54):9,(27,55):24,(27,56):14,(27,57):12,(27,58):12,(27,59):18,(27,60):14,
    (27,61):9,(27,62):13,(27,63):12,(27,64):11,(27,65):14,(27,66):20,(27,67):8,(27,68):36,(27,69):37,(27,70):6,
    (27,71):24,(27,72):20,(27,73):28,(27,74):23,(27,75):11,(27,76):13,(27,77):21,(27,78):72,(27,79):13,(27,80):20,
    (27,81):17,(27,82):8,(27,83):19,(27,84):13,(27,85):14,(27,86):17,(27,87):7,(27,88):19,(27,89):53,(27,90):17,
    (27,91):16,(27,92):16,(27,93):5,(27,94):23,(27,95):11,(27,96):13,(27,97):12,(27,98):9,(27,99):9,(27,100):5,
    (27,101):8,(27,102):29,(27,103):22,(27,104):35,(27,105):45,(27,106):48,(27,107):43,(27,108):14,(27,109):31,(27,110):7,
    (27,111):10,(27,112):10,(27,113):9,(27,114):8,(27,115):18,(27,116):19,(27,117):2,(27,118):29,(27,119):176,(27,120):7,
    (27,121):8,(27,122):9,(27,123):4,(27,124):8,(27,125):5,(27,126):6,(27,127):5,(27,128):6,(27,129):8,(27,130):8,
    (27,131):3,(27,132):18,(27,133):3,(27,134):3,(27,135):21,(27,136):26,(27,137):9,(27,138):8,(27,139):24,(27,140):14,
    (27,141):10,(27,142):8,(27,143):12,(27,144):15,(27,145):21,(27,146):10,(27,147):20,(27,148):14,(27,149):9,(27,150):6,
    # ── Proverbs (28) ──
    (28,1):33,(28,2):22,(28,3):35,(28,4):27,(28,5):23,(28,6):35,(28,7):27,(28,8):36,(28,9):18,(28,10):32,
    (28,11):31,(28,12):28,(28,13):25,(28,14):35,(28,15):33,(28,16):33,(28,17):28,(28,18):24,(28,19):29,(28,20):30,
    (28,21):31,(28,22):29,(28,23):35,(28,24):34,(28,25):28,(28,26):28,(28,27):27,(28,28):28,(28,29):27,(28,30):33,
    (28,31):31,
    # ── Job (29) ──
    (29,1):22,(29,2):13,(29,3):26,(29,4):21,(29,5):27,(29,6):30,(29,7):21,(29,8):22,(29,9):35,(29,10):22,
    (29,11):20,(29,12):25,(29,13):28,(29,14):22,(29,15):35,(29,16):22,(29,17):16,(29,18):21,(29,19):29,(29,20):29,
    (29,21):34,(29,22):30,(29,23):17,(29,24):25,(29,25):6,(29,26):14,(29,27):23,(29,28):28,(29,29):25,(29,30):31,
    (29,31):40,(29,32):22,(29,33):33,(29,34):37,(29,35):16,(29,36):33,(29,37):24,(29,38):41,(29,39):30,(29,40):32,
    (29,41):26,(29,42):17,
    # ── Ezra (36) ──
    (36,1):11,(36,2):70,(36,3):13,(36,4):24,(36,5):17,(36,6):22,(36,7):28,(36,8):36,(36,9):15,(36,10):44,
    # ── I Chronicles (37) ──
    (37,1):54,(37,2):55,(37,3):24,(37,4):43,(37,5):41,(37,6):66,(37,7):40,(37,8):40,(37,9):44,(37,10):14,
    (37,11):47,(37,12):41,(37,13):14,(37,14):17,(37,15):29,(37,16):43,(37,17):27,(37,18):17,(37,19):19,(37,20):8,
    (37,21):30,(37,22):19,(37,23):32,(37,24):31,(37,25):31,(37,26):32,(37,27):34,(37,28):21,(37,29):30,
    # ── II Chronicles (38) ──
    (38,1):18,(38,2):17,(38,3):17,(38,4):22,(38,5):14,(38,6):42,(38,7):22,(38,8):18,(38,9):31,(38,10):19,
    (38,11):23,(38,12):16,(38,13):23,(38,14):14,(38,15):19,(38,16):14,(38,17):19,(38,18):34,(38,19):11,(38,20):37,
    (38,21):20,(38,22):12,(38,23):21,(38,24):27,(38,25):28,(38,26):23,(38,27):9,(38,28):27,(38,29):36,(38,30):27,
    (38,31):21,(38,32):33,(38,33):25,(38,34):33,(38,35):27,(38,36):23,
}


def build_verse_metadata(
    tokens: List[Token],
    starting_chapter: int = 1,
    starting_verse: int = 1,
    aliyah_boundaries: Optional[Dict] = None,
    book_num: int = 0,
) -> List[dict]:
    """Build per-token verse metadata from a flat token list.

    Counts ``verse_end`` flags to advance verse and chapter numbers.
    When *book_num* is supplied (1–5 for the five books of Moses), the
    chapter boundary is looked up from ``_TORAH_CHAPTER_LENGTHS`` and
    the chapter number is incremented automatically whenever the verse
    counter exceeds the known chapter length.

    :param tokens: List of Token objects.
    :param starting_chapter: Chapter number of the first verse.
    :param starting_verse: Verse number of the first verse.
    :param aliyah_boundaries: Mapping whose keys are either:

        * ``(chapter, verse)`` tuples – the **preferred** format coming
          from ``sedrot_parser``.  The aliyah starts exactly at that
          chapter:verse.
        * Plain ``int`` verse-index values – legacy fallback used when
          no XML data is available.

        Values are ``(aliyah_num, aliyah_name)`` tuples in both cases.
    :param book_num: Book number 1–5 (0 = unknown, no chapter wrapping).
    :return: List of metadata dicts, one per token.
    """
    if aliyah_boundaries is None:
        aliyah_boundaries = {}

    # Detect boundary key type: tuple keys = XML-sourced exact boundaries.
    _keys = list(aliyah_boundaries.keys())
    _use_cv_keys: bool = bool(_keys) and isinstance(_keys[0], tuple)

    metadata: List[dict] = []
    chapter = starting_chapter
    verse = starting_verse
    verse_idx = 0
    current_aliyah_num = 0
    current_aliyah_name = ""
    is_verse_start = True

    for token in tokens:
        # ── Look up aliyah boundary ──
        if _use_cv_keys:
            # Key is (chapter, verse) – exact Torah position.
            aliyah_info = aliyah_boundaries.get((chapter, verse))
        else:
            # Legacy: key is 0-based verse index.
            aliyah_info = aliyah_boundaries.get(verse_idx)

        is_aliyah_start = False
        if aliyah_info is not None and aliyah_info[0] != current_aliyah_num:
            current_aliyah_num = aliyah_info[0]
            current_aliyah_name = aliyah_info[1]
            is_aliyah_start = True

        metadata.append({
            "chapter": chapter,
            "verse": verse,
            "is_verse_start": is_verse_start,
            "aliyah_num": current_aliyah_num,
            "aliyah_name": current_aliyah_name,
            "is_aliyah_start": is_aliyah_start,
        })

        is_verse_start = False
        if token.verse_end:
            verse += 1
            verse_idx += 1
            is_verse_start = True

            # ── Chapter boundary check ──
            if book_num > 0:
                chapter_max = _TORAH_CHAPTER_LENGTHS.get(
                    (book_num, chapter), 999
                )
                if verse > chapter_max:
                    chapter += 1
                    verse = 1

    return metadata

