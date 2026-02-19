"""Audio debug logger configuration.

This module configures a **single** file-backed logger for all audio
subsystems (sine synthesis, concat synthesis, GUI playback workers).

Goals
-----
- Always write to ``audio_debug.log`` in the **repo root**.
- Be idempotent (safe to call multiple times).
- Work even if other parts of the app already configured logging.
- Emit a visible *startup* entry so users can confirm the log is active.

Repo-root detection
-------------------
The file lives under ``taamimflow/audio`` so the repository root is
``Path(__file__).resolve().parents[2]`` (…/repo/taamimflow/audio/audio_logger.py).

"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Lock

_LOCK = Lock()
_CONFIGURED = False


def get_repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[2]


def get_audio_log_path() -> Path:
    """Return the absolute path to ``audio_debug.log`` in repo root."""
    return get_repo_root() / "audio_debug.log"


def configure_audio_logger(force: bool = False) -> logging.Logger:
    """Configure the audio debug logger and return it.

    Parameters
    ----------
    force:
        If True, forces adding a fresh FileHandler and writing a startup
        line even if the logger seems configured already.

    Returns
    -------
    logging.Logger
        The configured logger named ``taamimflow.audio``.
    """
    global _CONFIGURED

    with _LOCK:
        logger = logging.getLogger("taamimflow.audio")
        logger.setLevel(logging.DEBUG)

        # Do not propagate into the root logger; we want deterministic file logging
        # without depending on global app logging configuration.
        logger.propagate = False

        log_path = str(get_audio_log_path())

        # Ensure the file exists (best-effort). If it fails, we still keep going.
        try:
            with open(log_path, "a", encoding="utf-8"):
                pass
        except Exception:
            pass

        # Add a FileHandler if not already attached for this path.
        has_matching_file_handler = False
        for h in list(logger.handlers):
            if isinstance(h, logging.FileHandler):
                try:
                    if os.path.abspath(getattr(h, "baseFilename", "")) == os.path.abspath(log_path):
                        has_matching_file_handler = True
                        break
                except Exception:
                    continue

        if force or not has_matching_file_handler:
            fh = logging.FileHandler(log_path, mode="a", encoding="utf-8", delay=False)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            logger.addHandler(fh)

        # Startup entry: write exactly once per process (unless forced).
        if force or not _CONFIGURED:
            logger.info("=== Audio debug logging started (pid=%s) ===", os.getpid())
            for h in logger.handlers:
                try:
                    h.flush()
                except Exception:
                    pass
            _CONFIGURED = True

        return logger
