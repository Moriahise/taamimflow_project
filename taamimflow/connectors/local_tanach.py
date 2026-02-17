"""LocalTanachConnector — Milestone 8: Offline Tanach TXT Reader.

Reads plain-text Tanach files (tanach.us / Miqra-Masorah format) from a
local directory.  Completely independent of Sefaria and the internet.
No network calls, no freezes.

Supported file formats (all three variants from tanach.us):
    • Tanach with Ta'amei Hamikra  (full cantillation + vowels)
    • Tanach with Text Only         (consonants only)
    • Miqra according to the Masorah (cantillation, with HTML markup that
      is automatically cleaned)

File format recognised by this parser:
    Line 1  – English book name  (e.g. "Genesis")
    Line 2  – Hebrew book name   (e.g. "בראשית")
    Line 3  – Source description
    Line 4  – URL
    ...
    "Chapter N"  – chapter header
    <verse text>  – one verse per line

Usage (from config_default_settings.json):
    {
        "connector": {
            "type": "local",
            "tanach_dir": "tanach_data",
            "preferred_format": "cantillation"
        }
    }

Drop .txt files into the ``tanach_dir`` folder and they are auto-indexed
by English book name.  Multiple files for the same book are supported;
``preferred_format`` selects which variant is loaded first.

``preferred_format`` values:
    "cantillation"   → prefers files containing "Ta_amei" in the name
    "text_only"      → prefers files containing "Text_Only"
    "masorah"        → prefers files containing "Masorah"
    "any"            → first file found wins
"""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import date

from .base import BaseConnector
from ..data.sedrot import load_sedrot, SedraOption
from ..utils.paths import find_data_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------------------------

# Strip any HTML tags (e.g. from Miqra-Masorah format)
_RE_TAG = re.compile(r"<[^>]+>")
# Collapse extra whitespace
_RE_WS = re.compile(r"[ \t\u00A0\u200f\u200e]+")
# Parenthetical paragraph markers: (פ) (ס)
_RE_PARA_MARKER = re.compile(r"\s*[(\[]\s*[פס]\s*[)\]]")
# Chapter header line, e.g. "Chapter 3"
_RE_CHAPTER = re.compile(r"^\s*Chapter\s+(\d+)\s*$", re.IGNORECASE)
# TropeTrainer-style reference: GEN1:1-2:3 or Genesis.1.1-2.3 or Genesis 1:1-2:3
_RE_TT_REF = re.compile(
    r"^([A-Z]{2,5})(\d+):(\d+)(?:-(\d+):(\d+))?$", re.IGNORECASE
)
_RE_DOT_REF = re.compile(
    r"^([A-Za-z ]+?)\.(\d+)\.(\d+)(?:-(\d+)\.(\d+))?$"
)
_RE_COLON_REF = re.compile(
    r"^([A-Za-z ]+?)\s+(\d+):(\d+)(?:\s*[-–]\s*(\d+):(\d+))?$"
)

# ---------------------------------------------------------------------------
# Book-name mappings
# ---------------------------------------------------------------------------

#: Map 3-letter TropeTrainer abbreviations → canonical English book names
ABBREV_TO_BOOK: Dict[str, str] = {
    "GEN": "Genesis",
    "EXO": "Exodus",
    "LEV": "Leviticus",
    "NUM": "Numbers",
    "DEU": "Deuteronomy",
    "JOS": "Joshua",
    "JDG": "Judges",
    "ISA": "Isaiah",
    "JER": "Jeremiah",
    "EZK": "Ezekiel",
    "HOS": "Hosea",
    "JOE": "Joel",
    "AMO": "Amos",
    "OBA": "Obadiah",
    "JON": "Jonah",
    "MIC": "Micah",
    "NAH": "Nahum",
    "HAB": "Habakkuk",
    "ZEP": "Zephaniah",
    "HAG": "Haggai",
    "ZEC": "Zechariah",
    "MAL": "Malachi",
    "PSA": "Psalms",
    "JOB": "Job",
    "PRO": "Proverbs",
    "RUT": "Ruth",
    "SOS": "Song of Songs",
    "LAM": "Lamentations",
    "ECC": "Ecclesiastes",
    "EST": "Esther",
    "DAN": "Daniel",
    "EZR": "Ezra",
    "NEH": "Nehemiah",
    "1CH": "I Chronicles",
    "2CH": "II Chronicles",
    "1SA": "I Samuel",
    "2SA": "II Samuel",
    "1KI": "I Kings",
    "2KI": "II Kings",
}

#: Alternative English spellings → canonical name used in tanach.us files
_ALT_NAMES: Dict[str, str] = {
    "song of solomon": "Song of Songs",
    "song of song": "Song of Songs",
    "kohelet": "Ecclesiastes",
    "qohelet": "Ecclesiastes",
    "tehillim": "Psalms",
    "bereishit": "Genesis",
    "shemot": "Exodus",
    "vayikra": "Leviticus",
    "bamidbar": "Numbers",
    "devarim": "Deuteronomy",
    "i kings": "I Kings",
    "1 kings": "I Kings",
    "ii kings": "II Kings",
    "2 kings": "II Kings",
    "1 samuel": "I Samuel",
    "i samuel": "I Samuel",
    "2 samuel": "II Samuel",
    "ii samuel": "II Samuel",
    "1 chronicles": "I Chronicles",
    "i chronicles": "I Chronicles",
    "2 chronicles": "II Chronicles",
    "ii chronicles": "II Chronicles",
}

#: Preferred-format keyword → substring in filename
_FORMAT_HINTS: Dict[str, str] = {
    "cantillation": "Ta_amei",
    "text_only": "Text_Only",
    "masorah": "Masorah",
}


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def _clean_verse(raw: str) -> str:
    """Remove HTML markup, paragraph markers and excess whitespace from a verse."""
    # Unescape HTML entities first (&thinsp; etc.)
    text = html.unescape(raw)
    # Remove HTML tags
    text = _RE_TAG.sub("", text)
    # Remove bidi marks
    text = text.replace("\u200f", "").replace("\u200e", "")
    # Remove paragraph markers like (פ) (ס)
    text = _RE_PARA_MARKER.sub("", text)
    # Collapse whitespace
    text = _RE_WS.sub(" ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# TXT file parser
# ---------------------------------------------------------------------------

class TanachTxtFile:
    """Parsed representation of a single tanach.us TXT file.

    Attributes:
        path: Source file path.
        book_en: English book name from line 1.
        book_he: Hebrew book name from line 2.
        source: Source description from line 3.
        url: URL from line 4.
        chapters: dict mapping chapter_number (int) → list of verse strings.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.book_en: str = ""
        self.book_he: str = ""
        self.source: str = ""
        self.url: str = ""
        self.chapters: Dict[int, List[str]] = {}
        self._parse()

    def _parse(self) -> None:
        """Parse the file into chapter/verse structure."""
        try:
            text = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.error("Cannot read %s: %s", self.path, exc)
            return

        lines = text.splitlines()
        # Header metadata (first 4 meaningful lines)
        header_lines = [l.strip() for l in lines[:6] if l.strip()]
        if len(header_lines) >= 1:
            self.book_en = header_lines[0]
        if len(header_lines) >= 2:
            self.book_he = header_lines[1]
        if len(header_lines) >= 3:
            self.source = header_lines[2]
        if len(header_lines) >= 4:
            self.url = header_lines[3]

        current_chapter: int = 0
        for raw_line in lines[4:]:
            line = raw_line.strip()
            if not line:
                continue
            m = _RE_CHAPTER.match(line)
            if m:
                current_chapter = int(m.group(1))
                self.chapters.setdefault(current_chapter, [])
                continue
            if current_chapter == 0:
                # Skip the repeated Hebrew title block at the top
                continue
            # It is a verse line
            verse_text = _clean_verse(line)
            if verse_text:
                self.chapters[current_chapter].append(verse_text)

    def get_verse(self, chapter: int, verse: int) -> Optional[str]:
        """Return a single verse (1-indexed) or None if out of range."""
        verses = self.chapters.get(chapter)
        if verses is None:
            return None
        idx = verse - 1
        if idx < 0 or idx >= len(verses):
            return None
        return verses[idx]

    def get_range(
        self,
        chapter_from: int,
        verse_from: int,
        chapter_to: int,
        verse_to: int,
    ) -> str:
        """Return all verses in [chapter_from:verse_from .. chapter_to:verse_to].

        Returns a newline-joined string.
        """
        result: List[str] = []
        for chap in range(chapter_from, chapter_to + 1):
            verses = self.chapters.get(chap, [])
            v_start = verse_from if chap == chapter_from else 1
            v_end = verse_to if chap == chapter_to else len(verses)
            for vi in range(v_start, v_end + 1):
                idx = vi - 1
                if 0 <= idx < len(verses):
                    result.append(verses[idx])
        return "\n".join(result)


# ---------------------------------------------------------------------------
# Reference parsing helpers
# ---------------------------------------------------------------------------

def _normalise_book_name(name: str) -> str:
    """Lower-case + strip, then apply known aliases."""
    key = name.strip().lower()
    return _ALT_NAMES.get(key, name.strip())


def parse_reference(ref: str) -> Tuple[str, int, int, int, int]:
    """Parse a verse reference into (book, ch_from, v_from, ch_to, v_to).

    Understands three formats:
        * TropeTrainer: ``GEN1:1-2:3``
        * Dotted:       ``Genesis.1.1-2.3``
        * Colon:        ``Genesis 1:1-2:3``

    Single-verse references have ch_to == ch_from, v_to == v_from.

    Raises:
        ValueError: If the reference cannot be parsed.
    """
    ref = ref.strip()

    # --- TropeTrainer format (e.g. GEN1:1  or  GEN1:1-2:3) ---
    m = _RE_TT_REF.match(ref)
    if m:
        abbrev = m.group(1).upper()
        book = ABBREV_TO_BOOK.get(abbrev, abbrev.capitalize())
        ch1, v1 = int(m.group(2)), int(m.group(3))
        ch2 = int(m.group(4)) if m.group(4) else ch1
        v2 = int(m.group(5)) if m.group(5) else v1
        return book, ch1, v1, ch2, v2

    # --- Dotted format (e.g. Genesis.1.1-2.3) ---
    m = _RE_DOT_REF.match(ref)
    if m:
        book = _normalise_book_name(m.group(1))
        ch1, v1 = int(m.group(2)), int(m.group(3))
        ch2 = int(m.group(4)) if m.group(4) else ch1
        v2 = int(m.group(5)) if m.group(5) else v1
        return book, ch1, v1, ch2, v2

    # --- Colon / space format (e.g. Genesis 1:1-2:3 or Genesis 1:1) ---
    m = _RE_COLON_REF.match(ref)
    if m:
        book = _normalise_book_name(m.group(1))
        ch1, v1 = int(m.group(2)), int(m.group(3))
        ch2 = int(m.group(4)) if m.group(4) else ch1
        v2 = int(m.group(5)) if m.group(5) else v1
        return book, ch1, v1, ch2, v2

    raise ValueError(f"Cannot parse reference: {ref!r}")


# ---------------------------------------------------------------------------
# Main connector
# ---------------------------------------------------------------------------

class LocalTanachConnector(BaseConnector):
    """Offline connector that reads tanach.us plain-text files.

    Configuration keys (all optional):
        ``tanach_dir``          Directory containing .txt files.
                                Defaults to ``tanach_data`` next to the
                                running script or in the package root.
        ``preferred_format``    Which file variant to prefer when multiple
                                files exist for the same book.
                                Values: "cantillation" | "text_only" |
                                        "masorah" | "any"
                                Default: "cantillation"
        ``strip_cantillation``  If True, strip all vowel / trope marks
                                before returning text.  Default: False.
        ``strip_paragraph_markers``
                                Remove (פ) and (ס) markers.  Default: True.

    Example config_default_settings.json entry::

        "connector": {
            "type": "local",
            "tanach_dir": "tanach_data",
            "preferred_format": "cantillation"
        }
    """

    def __init__(
        self,
        tanach_dir: Optional[str] = None,
        preferred_format: str = "cantillation",
        strip_cantillation: bool = False,
        strip_paragraph_markers: bool = True,
    ) -> None:
        # Resolve directory
        if tanach_dir:
            self._dir = Path(tanach_dir)
        else:
            # Try common locations
            self._dir = self._find_default_dir()

        self._preferred_format = preferred_format.lower()
        self._strip_cantillation = strip_cantillation
        self._strip_paragraph_markers = strip_paragraph_markers

        # Book cache: lowercase English name → TanachTxtFile
        self._cache: Dict[str, TanachTxtFile] = {}
        # Index: lowercase English name → list of candidate paths (sorted by preference)
        self._index: Dict[str, List[Path]] = {}
        self._build_index()

    # ------------------------------------------------------------------
    # Directory resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _find_default_dir() -> Path:
        """Search for a 'tanach_data' directory in common locations."""
        candidates = [
            Path("tanach_data"),
            Path(__file__).parent.parent.parent / "tanach_data",
            Path(__file__).parent.parent / "tanach_data",
        ]
        for p in candidates:
            if p.is_dir():
                return p
        # Return the first candidate even if it doesn't exist yet;
        # _build_index will handle the empty-dir case gracefully.
        return Path("tanach_data")

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _build_index(self) -> None:
        """Scan ``tanach_dir`` and map English book names → file paths."""
        self._index.clear()
        if not self._dir.is_dir():
            logger.warning(
                "LocalTanachConnector: directory not found: %s", self._dir
            )
            return

        txt_files = sorted(self._dir.glob("*.txt"))
        if not txt_files:
            logger.warning(
                "LocalTanachConnector: no .txt files in %s", self._dir
            )
            return

        for path in txt_files:
            # Peek at the first line to get the English book name
            try:
                with path.open(encoding="utf-8", errors="replace") as fh:
                    first_line = fh.readline().strip()
            except OSError:
                continue
            if not first_line:
                continue
            key = first_line.lower()
            self._index.setdefault(key, []).append(path)

        # Sort each entry so the preferred format comes first
        hint = _FORMAT_HINTS.get(self._preferred_format, "")
        for key in self._index:
            paths = self._index[key]
            if hint:
                paths.sort(key=lambda p: (0 if hint in p.name else 1, p.name))
            else:
                paths.sort(key=lambda p: p.name)

        logger.info(
            "LocalTanachConnector: indexed %d books in %s",
            len(self._index),
            self._dir,
        )

    # ------------------------------------------------------------------
    # Book loading
    # ------------------------------------------------------------------

    def _load_book(self, book_name: str) -> Optional[TanachTxtFile]:
        """Return a parsed TanachTxtFile for *book_name*, using cache."""
        key = book_name.strip().lower()
        # Check alias table
        canonical = _ALT_NAMES.get(key, book_name.strip())
        key = canonical.lower()

        if key in self._cache:
            return self._cache[key]

        paths = self._index.get(key)
        if not paths:
            # Fuzzy fallback: try substring match
            for idx_key, idx_paths in self._index.items():
                if key in idx_key or idx_key in key:
                    paths = idx_paths
                    break

        if not paths:
            logger.warning("LocalTanachConnector: book not found: %r", book_name)
            return None

        book_file = TanachTxtFile(paths[0])
        self._cache[key] = book_file
        logger.debug("Loaded %s from %s", book_name, paths[0])
        return book_file

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _postprocess(self, text: str) -> str:
        """Apply optional strip_cantillation and other post-processing."""
        if self._strip_cantillation:
            # Remove Hebrew cantillation marks (U+0591–U+05AF) and nikud (U+05B0–U+05BD, U+05BF, U+05C1-U+05C2, U+05C4-U+05C7)
            text = "".join(
                ch for ch in text
                if not (0x0591 <= ord(ch) <= 0x05C7 and unicodedata.category(ch) == "Mn")
            )
        return text

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def get_text(self, reference: str, *, with_cantillation: bool = True) -> str:
        """Return the Hebrew text for *reference*.

        :param reference: Supports formats:
            * ``GEN1:1-2:3``          (TropeTrainer)
            * ``Genesis.1.1-2.3``     (dotted)
            * ``Genesis 1:1-2:3``     (space/colon)
            * ``Genesis 1:1``         (single verse)
        :param with_cantillation: If False, cantillation marks are stripped
            regardless of the ``strip_cantillation`` config setting.
        :raises ValueError: If the reference cannot be parsed.
        :raises LookupError: If the book or verse range is not found.
        """
        book, ch1, v1, ch2, v2 = parse_reference(reference)
        book_file = self._load_book(book)
        if book_file is None:
            raise LookupError(
                f"Book not found in local data: {book!r}. "
                f"Available books: {self.list_available_books()}"
            )
        text = book_file.get_range(ch1, v1, ch2, v2)
        if not text:
            raise LookupError(
                f"Verses not found: {reference!r} "
                f"(chapters available: {sorted(book_file.chapters)})"
            )
        if not with_cantillation:
            # Temporarily force strip
            old = self._strip_cantillation
            self._strip_cantillation = True
            text = self._postprocess(text)
            self._strip_cantillation = old
        else:
            text = self._postprocess(text)
        return text

    def get_parasha(
        self,
        parasha_name: str,
        reading_type: str = "Torah",
        aliyah: Optional[str] = None,
        cycle: int = 0,
    ) -> str:
        """Return the Hebrew text of an entire parasha / aliyah.

        Loads the verse reference from sedrot.xml (the same XML used by
        the SefariaConnector) and resolves it against the local files.

        :param parasha_name: Name matching the sedrot.xml entry, e.g. "Bereshit".
        :param reading_type: "Torah" or "Haftarah".
        :param aliyah: Optional aliyah key (KOHEN, LEVI, …, SHVII) to return
            only that section.
        :raises LookupError: If the parasha is not found in sedrot.xml or the
            local files.
        """
        try:
            sedrot_path = find_data_file("sedrot.xml")
            sedrot = load_sedrot(str(sedrot_path))
        except Exception as exc:
            raise LookupError(f"Cannot load sedrot.xml: {exc}") from exc

        # Find the sedra
        target = None
        for sedra in sedrot:
            if sedra.name.lower() == parasha_name.lower():
                target = sedra
                break
        if target is None:
            raise LookupError(
                f"Parasha not found in sedrot.xml: {parasha_name!r}"
            )

        # Collect options for the requested reading type
        options = [o for o in target.options if reading_type.upper() in o.type.upper()]
        if not options:
            # Fall back to all options
            options = target.options

        # Gather all aliyot references
        refs_to_fetch: List[str] = []
        for opt in options:
            if aliyah:
                refs_to_fetch = [
                    v for k, v in opt.aliyot.items()
                    if k.upper() == aliyah.upper() and v
                ]
                if refs_to_fetch:
                    break
            else:
                for ref in opt.aliyot.values():
                    if ref:
                        refs_to_fetch.append(ref)
                if refs_to_fetch:
                    break

        if not refs_to_fetch:
            raise LookupError(
                f"No verse references for parasha {parasha_name!r} "
                f"type={reading_type} aliyah={aliyah}"
            )

        # Fetch and concatenate
        parts: List[str] = []
        for ref in refs_to_fetch:
            try:
                parts.append(self.get_text(ref))
            except (ValueError, LookupError) as exc:
                logger.warning("Skipping ref %r: %s", ref, exc)

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Utility / introspection
    # ------------------------------------------------------------------

    def get_haftarah(
        self,
        parasha_name: str,
        cycle: int = 0,
        for_date: Optional[date] = None,
    ) -> str:
        """Get Haftarah reading for a parasha.
        
        Uses sedrot.xml to find Haftarah references.
        
        :param parasha_name: Name of the parasha.
        :param cycle: Triennial cycle (not used for Haftarot).
        :param for_date: Optional date (for special Haftarot).
        :returns: Hebrew text as string.
        """
        return self.get_parasha(parasha_name, reading_type="Haftarah", cycle=cycle)

    def get_maftir(self, parasha_name: str, cycle: int = 0) -> str:
        """Get Maftir reading (typically last aliyah).
        
        :param parasha_name: Name of the parasha.
        :param cycle: Triennial cycle.
        :returns: Hebrew text as string.
        """
        return self.get_parasha(parasha_name, reading_type="Torah", aliyah="SHVII", cycle=cycle)


    def list_available_books(self) -> List[str]:
        """Return the list of English book names found in ``tanach_dir``."""
        return sorted(self._index.keys())

    def reload_index(self) -> None:
        """Re-scan the directory and clear the book cache."""
        self._cache.clear()
        self._build_index()

    def get_book_info(self, book_name: str) -> Optional[Dict]:
        """Return metadata dict for a book, or None if not found."""
        book_file = self._load_book(book_name)
        if book_file is None:
            return None
        return {
            "book_en": book_file.book_en,
            "book_he": book_file.book_he,
            "source": book_file.source,
            "url": book_file.url,
            "chapters": len(book_file.chapters),
            "total_verses": sum(len(v) for v in book_file.chapters.values()),
            "path": str(book_file.path),
        }

    def get_chapter(self, book_name: str, chapter: int) -> List[str]:
        """Return all verses of a chapter as a list of strings."""
        book_file = self._load_book(book_name)
        if book_file is None:
            raise LookupError(f"Book not found: {book_name!r}")
        verses = book_file.chapters.get(chapter)
        if verses is None:
            raise LookupError(
                f"Chapter {chapter} not found in {book_name!r} "
                f"(available: {sorted(book_file.chapters)})"
            )
        return [self._postprocess(v) for v in verses]

    def get_verse(self, book_name: str, chapter: int, verse: int) -> str:
        """Return a single verse as a string."""
        book_file = self._load_book(book_name)
        if book_file is None:
            raise LookupError(f"Book not found: {book_name!r}")
        text = book_file.get_verse(chapter, verse)
        if text is None:
            raise LookupError(
                f"Verse not found: {book_name} {chapter}:{verse}"
            )
        return self._postprocess(text)
