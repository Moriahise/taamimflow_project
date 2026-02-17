"""Connector for retrieving text and calendar data from Sefaria.

This connector wraps Sefaria's public API.  It can fetch Torah text in
Hebrew with cantillation marks, return the contents of a given
parasha, and provide calendar information.  It is implemented as a
minimal example: if internet access is not available the methods will
raise a :class:`ConnectionError`.  To use this connector in a
production environment, ensure that outbound HTTPS requests to
``sefaria.org`` are permitted.

New methods added for Ta'amimFlow:

* :meth:`get_maftir`  – retrieve the Maftir (additional reading) for a
  given parasha, with fallback to the last aliyah of the Torah reading.
* :meth:`get_haftarah` – retrieve the Haftarah for a given parasha.
* :meth:`_retrieve_sedra_option` – internal helper to find a
  :class:`SedraOption` of a given type from ``sedrot.xml``.

For details on the Sefaria API, see the documentation at
https://developers.sefaria.org.  The endpoints used here are based on
the v2/v3 ``texts`` and ``calendars`` APIs.  Should these endpoints
change, adjust the URL construction accordingly.
"""

from __future__ import annotations

import json
import logging
import re
import html as _html
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .base import BaseConnector
from ..data.sedrot import load_sedrot, SedraOption
from ..utils.paths import find_data_file
from ..utils.refs import normalize_ref

logger = logging.getLogger(__name__)

# Regular expressions and helpers for cleaning Sefaria HTML responses.
_RE_BR = re.compile(r"(?i)<br\s*/?>")
_RE_P = re.compile(r"(?i)</p>\s*<p>")
_RE_TAG = re.compile(r"<[^>]+>")
_RE_WS = re.compile(r"[ \t\u00A0]+")


def _clean_sefaria_text(s: str) -> str:
    """Clean up HTML markup and whitespace in Sefaria responses.

    Sefaria sometimes returns HTML tags (e.g. ``<b>``, ``&thinsp;``) and
    irregular whitespace in its text fields.  This helper normalizes
    paragraph and line breaks, strips out all tags, unescapes HTML
    entities, removes bidirectional marks, and collapses extraneous
    whitespace.  If ``s`` is falsy, an empty string is returned.

    :param s: Raw text returned by the API.
    :return: Cleaned text ready for display.
    """
    if not s:
        return ""
    # Normalize paragraphs (<p>..</p>) into double newlines
    s = _RE_P.sub("\n\n", s)
    # Normalize <br> tags into single newlines
    s = _RE_BR.sub("\n", s)
    # Unescape HTML entities before removing tags
    s = _html.unescape(s)
    # Remove all remaining HTML tags
    s = _RE_TAG.sub("", s)
    # Strip left/right mark characters that sometimes appear
    s = s.replace("\u200f", "").replace("\u200e", "")
    # Replace non-breaking spaces with regular spaces
    s = s.replace("\xa0", " ")
    # Collapse runs of spaces or tabs
    s = _RE_WS.sub(" ", s)
    # Remove spaces at the end of lines
    s = re.sub(r"[ \t]+\n", "\n", s)
    # Collapse more than two consecutive newlines into two
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# Ordered list of aliyah keys used throughout the connector.
_ALIYAH_ORDER: List[str] = [
    "KOHEN", "LEVI", "SHLISHI", "REVII",
    "CHAMISHI", "SHISHI", "SHVII",
]


class SefariaConnector(BaseConnector):
    """Fetch biblical text and calendar information using Sefaria's API.

    This class provides methods to retrieve Torah text, Maftir, Haftarah
    and calendar data.  It uses the built‑in ``sedrot.xml`` definitions
    to resolve parasha names into verse ranges and then fetches the
    Hebrew text from Sefaria's API.

    :param base_url: The base URL for the Sefaria API.
    """

    def __init__(self, base_url: str = "https://www.sefaria.org/api") -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    # ------------------------------------------------------------------ #
    # Low‑level request helper
    # ------------------------------------------------------------------ #
    def _request(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Send a GET request to the Sefaria API and return JSON.

        :raises ConnectionError: If the API returns a non‑200 status.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self.session.get(
            url,
            params=params or {},
            headers={"User-Agent": "TaamimFlow/0.1"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise ConnectionError(
                f"Sefaria API responded with status {resp.status_code} for {url}"
            )
        return resp.json()

    # ------------------------------------------------------------------ #
    # Text retrieval
    # ------------------------------------------------------------------ #
    def get_text(self, reference: str, *, with_cantillation: bool = True) -> str:
        """Retrieve a single continuous range of text.

        This implementation uses the v2 ``texts`` endpoint.  The "ref"
        parameter should be in English (e.g. ``"Genesis 1:1-2:3"``).
        ``with_cantillation`` toggles the inclusion of nikkud and
        trope marks.

        :param reference: Sefaria‑style reference string.
        :param with_cantillation: Whether to include vowels and trope.
        :return: Cleaned Hebrew text.
        """
        reference = normalize_ref(reference)
        params: Dict[str, Any] = {"context": 0, "pad": 0}
        if with_cantillation:
            params["lang"] = "he"
        else:
            params["lang"] = "he"
            params["vhe"] = 1
        data = self._request(f"texts/{reference}", params=params)
        text_list = data.get("he") or data.get("text") or []

        def _flatten(lst: Any) -> list[str]:
            result: list[str] = []
            for item in lst:
                if isinstance(item, list):
                    result.extend(_flatten(item))
                elif item is None:
                    continue
                else:
                    result.append(str(item))
            return result

        flat = _flatten(text_list)
        cleaned: list[str] = [_clean_sefaria_text(item) for item in flat if item]
        return "\n".join(cleaned)

    # ------------------------------------------------------------------ #
    # Sedra option retrieval helper
    # ------------------------------------------------------------------ #
    def _retrieve_sedra_option(
        self,
        parasha_name: str,
        type_filter: str,
        cycle: int = 0,
    ) -> SedraOption | None:
        """Internal helper to find a :class:`SedraOption` of a given type.

        Searches ``sedrot.xml`` for the parasha matching *parasha_name*
        and returns the first option whose ``type`` matches
        *type_filter* and whose ``cycle`` matches *cycle*.  If no
        exact match is found, the first option of the requested type is
        returned as a fallback.

        :param parasha_name: Name of the parasha to search for.
        :param type_filter: Desired option type (e.g. ``'torah'``,
            ``'maftir'``, ``'haftarah'``).
        :param cycle: Triennial cycle (0 for annual reading).
        :return: The matching :class:`SedraOption` or ``None``.
        """
        try:
            sedrot_xml = find_data_file("sedrot.xml")
            sedrot = load_sedrot(sedrot_xml)
        except Exception:
            logger.warning("Could not load sedrot.xml", exc_info=True)
            return None

        key = parasha_name.lower().replace(" ", "")
        type_filter_lc = type_filter.lower()

        for sedra in sedrot:
            if sedra.name.lower().replace(" ", "").startswith(key):
                # First pass: exact match on type and cycle
                for opt in sedra.options:
                    if opt.type.lower() == type_filter_lc:
                        opt_cycle = opt.cycle or 0
                        if opt_cycle == (cycle or 0):
                            return opt

                # Second pass: fallback to first option of the requested type
                for opt in sedra.options:
                    if opt.type.lower() == type_filter_lc:
                        return opt
                return None
        return None

    # ------------------------------------------------------------------ #
    # Helper: fetch text for all aliyot in a SedraOption
    # ------------------------------------------------------------------ #
    def _fetch_aliyot_text(
        self,
        option: SedraOption,
        keys: List[str] | None = None,
    ) -> str:
        """Fetch and concatenate text for the aliyot in *option*.

        :param option: The :class:`SedraOption` whose aliyot to fetch.
        :param keys: If given, only these keys are retrieved (in order).
            Otherwise all aliyot in ``_ALIYAH_ORDER`` are tried.
        :return: Concatenated Hebrew text.
        """
        aliyot: Dict[str, str] = getattr(option, "aliyot", None) or {}
        if not aliyot:
            return ""

        target_keys = keys or _ALIYAH_ORDER
        pieces: list[str] = []
        for k in target_keys:
            ref = aliyot.get(k)
            if ref:
                try:
                    pieces.append(self.get_text(ref))
                except Exception:
                    logger.debug("Failed to fetch aliyah %s (%s)", k, ref)
                    continue
        return "\n".join(pieces)

    # ------------------------------------------------------------------ #
    # Parasha (full Torah reading)
    # ------------------------------------------------------------------ #
    def get_parasha(self, parasha_name: str, *, cycle: int = 0) -> str:
        """Retrieve the full Torah text for a given parasha.

        This method resolves the parasha's verse ranges using the
        built‑in ``sedrot.xml`` parser and then concatenates the text
        fetched from Sefaria.  For a triennial cycle, the ``cycle``
        argument should be set to the desired year (1–3).  When
        ``cycle=0``, the full annual reading is retrieved.

        :raises FileNotFoundError: If ``sedrot.xml`` is not found.
        :raises ConnectionError: If the Sefaria API call fails.
        :raises ValueError: If the parasha or option is not found.
        """
        opt = self._retrieve_sedra_option(parasha_name, "torah", cycle)
        if opt is None:
            raise ValueError(f"No Torah option found for parasha {parasha_name}")
        text = self._fetch_aliyot_text(opt)
        if text:
            return text
        raise ValueError(f"Parasha not found: {parasha_name}")

    # ------------------------------------------------------------------ #
    # Partial reading (first aliyah only)
    # ------------------------------------------------------------------ #
    def get_parasha_partial(self, parasha_name: str, *, cycle: int = 0) -> str:
        """Retrieve the first aliyah of a given parasha.

        Falls back to :meth:`get_parasha` if the first aliyah cannot be
        determined.
        """
        try:
            opt = self._retrieve_sedra_option(parasha_name, "torah", cycle)
            if opt and getattr(opt, "aliyot", None):
                for key in _ALIYAH_ORDER:
                    ref = opt.aliyot.get(key)  # type: ignore[union-attr]
                    if ref:
                        return self.get_text(ref)
        except Exception:
            pass
        # Fallback to full reading
        return self.get_parasha(parasha_name, cycle=cycle)

    # ------------------------------------------------------------------ #
    # Maftir
    # ------------------------------------------------------------------ #
    def get_maftir(self, parasha_name: str, *, cycle: int = 0) -> str:
        """Retrieve the Maftir (additional reading) for a given parasha.

        The Maftir is typically the last aliyah of the Torah reading or
        a separate section defined in ``sedrot.xml``.  Lookup order:

        1.  A dedicated ``maftir`` option in ``sedrot.xml``, trying keys
            ``MAFTIR`` → ``SHVII`` → … → first available aliyah.
        2.  The ``MAFTIR`` or ``SHVII`` aliyah from the Torah option.
        3.  The last aliyah of the Torah option (insertion order).
        4.  Empty string as a final fallback.

        :param parasha_name: Name of the parasha.
        :param cycle: Triennial cycle (0 for annual).
        :return: Hebrew text for the Maftir portion.
        """
        # 1. Try dedicated maftir option
        maftir_opt = self._retrieve_sedra_option(parasha_name, "maftir", cycle)
        if maftir_opt and getattr(maftir_opt, "aliyot", None):
            aliyot: Dict[str, str] = maftir_opt.aliyot  # type: ignore[assignment]
            # Try explicit keys in priority order
            for key in ["MAFTIR", "SHVII", "SHISHI", "CHAMISHI",
                        "REVII", "SHLISHI", "LEVI", "KOHEN"]:
                ref = aliyot.get(key)
                if ref:
                    try:
                        return self.get_text(ref)
                    except Exception:
                        continue
            # Concatenate whatever is available
            text = self._fetch_aliyot_text(maftir_opt)
            if text:
                return text

        # 2. Fallback to Torah option's MAFTIR or SHVII
        torah_opt = self._retrieve_sedra_option(parasha_name, "torah", cycle)
        if torah_opt and getattr(torah_opt, "aliyot", None):
            aliyot = torah_opt.aliyot  # type: ignore[assignment]
            for key in ["MAFTIR", "SHVII"]:
                ref = aliyot.get(key)
                if ref:
                    try:
                        return self.get_text(ref)
                    except Exception:
                        continue
            # 3. Last aliyah in insertion order
            last_ref: str | None = None
            for ref in aliyot.values():
                last_ref = ref
            if last_ref:
                try:
                    return self.get_text(last_ref)
                except Exception:
                    pass

        # 4. Final fallback
        return ""

    # ------------------------------------------------------------------ #
    # Haftarah
    # ------------------------------------------------------------------ #
    def get_haftarah(
        self,
        parasha_name: str,
        *,
        cycle: int = 0,
        for_date: date | None = None,
    ) -> str:
        """Retrieve the Haftarah for a given parasha.

        A Haftarah is a reading from the Prophets associated with a
        parasha.  Lookup order:

        1.  A dedicated ``haftarah`` option in ``sedrot.xml`` whose
            aliyot are concatenated.
        2.  Sefaria's calendar API for *for_date* (if provided) to
            look up the correct Haftarah reference.
        3.  A direct Sefaria API call using a generated reference of the
            form ``"Haftarah for <parasha>"``.
        4.  Empty string as a final fallback.

        :param parasha_name: Name of the parasha.
        :param cycle: Triennial cycle (currently unused for Haftarah).
        :param for_date: If given, used to query the Sefaria calendar.
        :return: Hebrew text for the Haftarah.
        """
        # 1. Try dedicated haftarah option from sedrot.xml
        haft_opt = self._retrieve_sedra_option(parasha_name, "haftarah", cycle)
        if haft_opt and getattr(haft_opt, "aliyot", None):
            aliyot: Dict[str, str] = haft_opt.aliyot  # type: ignore[assignment]
            pieces: list[str] = []
            for ref in aliyot.values():
                try:
                    pieces.append(self.get_text(ref))
                except Exception:
                    continue
            if pieces:
                return "\n".join(pieces)

        # 2. Try the calendar API with a specific date
        if for_date is not None:
            try:
                cal = self.get_calendar(for_date)
                # Look for a haftarah entry in the calendar events
                for category, events in cal.items():
                    if not isinstance(events, list):
                        continue
                    for evt in events:
                        title = (evt.get("title", {}).get("en", "") or "").lower()
                        if "haftarah" in title or "haftara" in title:
                            ref = evt.get("ref")
                            if ref:
                                try:
                                    return self.get_text(ref)
                                except Exception:
                                    continue
            except Exception:
                logger.debug("Calendar fallback for haftarah failed", exc_info=True)

        # 3. Attempt a direct reference guess
        try:
            return self.get_text(f"Haftarah for {parasha_name}")
        except Exception:
            pass

        # 4. Final fallback
        return ""

    # ------------------------------------------------------------------ #
    # Calendar
    # ------------------------------------------------------------------ #
    def get_calendar(self, dt: date) -> Dict[str, Any]:
        """Retrieve calendar information for a date from Sefaria.

        Uses the ``calendars`` API, which returns an array of events
        (e.g., Torah readings, holidays).  The return value is a
        simplified dictionary keyed by event category.

        :param dt: The date to query.
        :return: Dictionary of events grouped by category.
        """
        iso_date = dt.isoformat()
        data = self._request(f"calendars/{iso_date}")
        events: Dict[str, Any] = {}
        for item in data.get("calendar_items", data.get("events", [])):
            category = item.get("category", "other")
            events.setdefault(category, []).append(item)
        return events
