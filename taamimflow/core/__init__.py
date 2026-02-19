"""Ta'amimFlow core package.

Exports the high-level cantillation extraction API so that the GUI
can import directly from ``taamimflow.core`` without knowing internal
module names.

Example::

    from taamimflow.core import extract_tokens_with_notes, TokenFull
"""

from .cantillation import (
    extract_tokens_with_notes,
    tokenize,
    TokenFull,
    TokenWithNotes,
    Token,
    GROUPS,
    normalise_hebrew,
    segment_text,
    ContextMatcher,
)

__all__ = [
    "extract_tokens_with_notes",
    "tokenize",
    "TokenFull",
    "TokenWithNotes",
    "Token",
    "GROUPS",
    "normalise_hebrew",
    "segment_text",
    "ContextMatcher",
]
