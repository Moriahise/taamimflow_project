"""Utility functions for locating data files.

This module provides a helper to locate data files used by the
application.  Rather than hard‑coding relative paths, it
searches a few standard locations: the current working directory
of the process, the repository root, the package directory and
the utils directory itself.  This makes it robust to various
launch contexts (e.g. running via `python -m taamimflow.main` or
when frozen with PyInstaller).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _candidate_locations(filename: str) -> Iterable[Path]:
    """Yield candidate locations for a data file.

    The order of locations is:
    1. Current working directory.
    2. Repository root (two levels above this file).
    3. Package directory (one level above this file).
    4. utils directory (the directory containing this module).
    """
    here = Path(__file__).resolve()
    cwd = Path.cwd()
    # repository root: utils/../../
    repo_root = here.parents[2]
    # package root: utils/..
    pkg_root = here.parents[1]
    utils_dir = here.parent
    yield cwd / filename
    yield repo_root / filename
    yield pkg_root / filename
    yield utils_dir / filename


def find_data_file(filename: str) -> Path:
    """Locate a data file by searching standard locations.

    Returns the first existing path from the candidate locations.
    Raises FileNotFoundError if the file is not found.
    """
    for candidate in _candidate_locations(filename):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Could not find data file '{filename}'. Tried: "
                            f"{', '.join(str(p) for p in _candidate_locations(filename))}")