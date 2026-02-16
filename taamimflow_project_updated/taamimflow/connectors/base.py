"""Abstract base classes for text connectors.

Connectors are responsible for fetching biblical text and related
metadata from various backends (e.g., Sefaria, local files or custom
APIs).  To ensure a consistent interface across backends, all
connectors should inherit from :class:`BaseConnector` and implement
the abstract methods defined therein.
"""

from __future__ import annotations

import abc
from datetime import date
from typing import Any, Dict, List, Optional


class BaseConnector(abc.ABC):
    """Abstract base class defining the minimal connector interface."""

    @abc.abstractmethod
    def get_text(self, reference: str, *, with_cantillation: bool = True) -> str:
        """Return a textual range from the Hebrew Bible.

        :param reference: A Sefaria-style reference, e.g. ``"Genesis 1:1-2:3"``.
        :param with_cantillation: Whether to include cantillation marks and vowels.
        :return: The requested text as a single string.  Multi‑verse ranges
            should be concatenated with appropriate separators (e.g.
            whitespace or newline characters).  Exact formatting is left
            to the implementation.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_parasha(self, parasha_name: str, *, cycle: int = 0) -> str:
        """Return the full text of a named parasha.

        :param parasha_name: Name of the parasha (e.g. ``"Bereishis"``).
        :param cycle: Cycle number for triennial readings.  Zero means the
            full annual reading.
        :return: The text of the parasha.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_calendar(self, dt: date) -> Dict[str, Any]:
        """Return calendar information for a given date.

        The returned dictionary may include keys such as ``"parasha"``,
        ``"holiday"``, ``"aliyot"``, etc., depending on the backend.

        :param dt: The date for which to fetch calendar data.
        :return: A dictionary of calendar information.
        """
        raise NotImplementedError

    # Optionally connectors may implement additional methods such as
    # get_haftarah(), get_megillah(), search(), etc.  Derived classes
    # should document any extra capabilities they provide.