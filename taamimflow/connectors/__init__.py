"""Connector package for retrieving textual data.

This package bundles different connectors that Ta'amimFlow can use to
retrieve the text of a Torah reading.  The default connector
exposes the Sefaria API via the :class:`SefariaConnector`.  Additional
connectors may be added in future to support other data sources,
including local files or proprietary APIs.

The :func:`get_default_connector` helper returns an instance of the
default connector.  Currently this is :class:`SefariaConnector`.
"""

from __future__ import annotations

from .sefaria import SefariaConnector
from .base import BaseConnector

def get_default_connector(config: dict | None = None) -> BaseConnector:
    """Return an instance of the default connector.

    The optional ``config`` argument is accepted for future
    compatibility but is currently ignored.
    """
    # Ignore config for now and always return a SefariaConnector.
    return SefariaConnector()

__all__ = [
    "BaseConnector",
    "SefariaConnector",
    "get_default_connector",
]