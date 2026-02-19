"""
Core cantillation logic for Ta'amimFlow.

This subpackage contains the high‑level pipeline for analysing Hebrew text
and producing cantillation information.  It encapsulates normalisation,
trope mark extraction, trope group mapping, context flag computation via
a finite‑state machine, and matching against melodic definitions using a
pre‑compiled decision tree.

The primary entry point is :func:`extract_tokens_with_notes`, which
returns a list of :class:`TokenFull` objects.  Each token carries the
original word, the detected trope marks, the assigned group, the
computed context flags, and the resulting sequence of :class:`~Note`
objects representing the melody.  Callers should treat the tokens as
immutable data structures.

Example::

    from taamimflow.core import extract_tokens_with_notes
    tokens = extract_tokens_with_notes("ויאמר ה׳ אל משה")
    for t in tokens:
        print(t.text, [note.pitch for note in t.notes])
"""

# Public API of the core package
from .cantillation import extract_tokens_with_notes, TokenFull  # noqa: F401
from .decision_tree import DecisionTreeMatcher  # noqa: F401
from .fsm_phrase_logic import PhraseFSM  # noqa: F401
from .aliyah_parser import AliyahParser  # noqa: F401
from .timing_map import create_timing_map  # noqa: F401

__all__ = [
    "extract_tokens_with_notes",
    "TokenFull",
    "DecisionTreeMatcher",
    "PhraseFSM",
    "AliyahParser",
    "create_timing_map",
]