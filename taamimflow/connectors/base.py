"""Base interface for connectors.

Connectors encapsulate the logic for retrieving the text of a
Torah reading.  Subclasses must implement at least the
:meth:`get_parasha` method, which returns the full text for a named
parasha.  Optionally, :meth:`get_parasha_partial` may be provided to
return a list of individual aliyah texts for piecewise loading.
"""

from __future__ import annotations
from typing import List

class BaseConnector:
    """Abstract base class for all connectors."""

    def get_parasha(self, parasha_name: str, *, cycle: int = 0) -> str:
        """Return the full text for the given parasha.

        The ``cycle`` parameter may be used to specify the triennial
        year (1–3).  Implementations may ignore this parameter if the
        data source does not support triennial readings.
        """
        raise NotImplementedError

    def get_parasha_partial(self, parasha_name: str, *, cycle: int = 0) -> List[str]:
        """Return a list of aliyah texts for the given parasha.

        By default this simply returns a single element list
        containing the full parasha text returned by :meth:`get_parasha`.
        Subclasses may override this to return each aliyah as a
        separate entry for piecewise loading.
        """
        return [self.get_parasha(parasha_name, cycle=cycle)]

    def get_text(self, reference: str, *, with_cantillation: bool = True) -> str:
        """Return the text for an arbitrary reference.

        Connectors that support direct text references may implement
        this method to fetch the content of a specific range.  The
        default implementation always raises ``NotImplementedError``.
        """
        raise NotImplementedError