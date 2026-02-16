"""Connector for retrieving text and calendar data from Sefaria.

This connector wraps Sefaria's public API.  It can fetch Torah text in
Hebrew with cantillation marks, return the contents of a given
parasha, and provide calendar information.  It is implemented as a
minimal example: if internet access is not available the methods will
raise a :class:`ConnectionError`.  To use this connector in a
production environment, ensure that outbound HTTPS requests to
``sefaria.org`` are permitted.

For details on the Sefaria API, see the documentation at
https://developers.sefaria.org.  The endpoints used here are based on
the v2/v3 ``texts`` and ``calendars`` APIs.  Should these endpoints
change, adjust the URL construction accordingly.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict

import requests

from .base import BaseConnector
from ..data.sedrot import load_sedrot, SedraOption


class SefariaConnector(BaseConnector):
    """Fetch biblical text and calendar information using Sefaria's API."""

    def __init__(self, base_url: str = "https://www.sefaria.org/api") -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def _request(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/') }"
        resp = self.session.get(url, params=params or {}, headers={"User-Agent": "TaamimFlow/0.1"})
        if resp.status_code != 200:
            raise ConnectionError(f"Sefaria API responded with status {resp.status_code} for {url}")
        return resp.json()

    def get_text(self, reference: str, *, with_cantillation: bool = True) -> str:
        """Retrieve a single continuous range of text.

        This implementation uses the v2 ``texts`` endpoint.  The "ref"
        parameter should be in English (e.g. "Genesis 1:1-2:3").
        ``with_cantillation`` toggles the inclusion of nikkud and
        trope marks; setting it to ``False`` will strip these signs via
        Sefaria's ``stripItags`` and ``vhe" parameters.
        """

        params: Dict[str, Any] = {
            "context": 0,  # do not include extra context
            "pad": 0,
        }
        if with_cantillation:
            # Request Hebrew with vowels and trope (vhe = vocalized Hebrew)
            params["lang"] = "he"
        else:
            # ``with_cantillation`` off uses untagged text: vhe=1 returns
            # nikud but no trope; there is no dedicated parameter to
            # remove both, so the caller may post‑process further.
            params["lang"] = "he"
            params["vhe"] = 1
        data = self._request(f"texts/{reference}", params=params)
        # The API returns an array of strings under "he" or "text".
        # Combine them with newlines to form a single continuous string.
        text_list = data.get("he") or data.get("text") or []
        return "\n".join(text_list)

    def get_parasha(self, parasha_name: str, *, cycle: int = 0) -> str:
        """Retrieve the full Torah text for a given parasha.

        This method resolves the parasha's verse ranges using the
        built‑in ``sedrot.xml`` parser and then concatenates the text
        fetched from Sefaria.  For a triennial cycle, the ``cycle``
        argument should be set to the desired year (1–3).  When
        ``cycle=0``, the full annual reading is retrieved.

        :raises FileNotFoundError: If ``sedrot.xml`` is not found.
        :raises ConnectionError: If the Sefaria API call fails.
        """

        # Load sedrot definitions once per process.  In a real
        # implementation this could be cached at module level.
        sedrot_xml = Path(__file__).resolve().parent.parent.parent / "sedrot.xml"
        sedrot = load_sedrot(sedrot_xml)
        # Find the matching sedra
        for sedra in sedrot:
            if sedra.name.lower().replace(" ", "").startswith(parasha_name.lower().replace(" ", "")):
                # Choose the first option matching the cycle and type
                selected_option: SedraOption | None = None
                for opt in sedra.options:
                    if opt.type.lower() == "torah":
                        # Cycle 0 means full reading; if cycle is None treat as 0
                        opt_cycle = opt.cycle or 0
                        if opt_cycle == cycle:
                            selected_option = opt
                            break
                if not selected_option:
                    # Fallback to first Torah option
                    selected_option = next((o for o in sedra.options if o.type.lower() == "torah"), None)
                if not selected_option:
                    raise ValueError(f"No Torah option found for parasha {parasha_name}")
                # Concatenate all aliyot ranges into a single reference
                text_pieces: list[str] = []
                for aliyah in [
                    "KOHEN",
                    "LEVI",
                    "SHLISHI",
                    "REVII",
                    "CHAMISHI",
                    "SHISHI",
                    "SHVII",
                ]:
                    if aliyah in selected_option.aliyot:
                        ref = selected_option.aliyot[aliyah]
                        text_pieces.append(self.get_text(ref))
                return "\n".join(text_pieces)
        raise ValueError(f"Parasha not found: {parasha_name}")

    def get_calendar(self, dt: date) -> Dict[str, Any]:
        """Retrieve calendar information for a date from Sefaria.

        Uses the ``calendars`` API, which returns an array of events
        (e.g., Torah readings, holidays).  The return value is a
        simplified dictionary keyed by event type.
        """

        # Format date as ISO string
        iso_date = dt.isoformat()
        data = self._request(f"calendars/{iso_date}")
        # Simplify the response: group events by category
        events: Dict[str, Any] = {}
        for item in data.get("events", []):
            category = item.get("category", "other")
            events.setdefault(category, []).append(item)
        return events