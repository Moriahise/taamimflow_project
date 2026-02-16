"""Connectors for retrieving text and metadata.

The connectors module defines interfaces for fetching biblical text
from various sources.  Different backends expose different sets of
capabilities (e.g., retrieving a Torah portion, verse ranges or
calendar data).  Connectors should be loosely coupled to the rest of
the application so that new sources can be added without modifying
existing code.

The :func:`get_default_connector` function instantiates a connector
based on application configuration.  By default, this returns a
``SefariaConnector``, but you may override the choice via the
configuration file or environment variables.
"""

from __future__ import annotations

from importlib import import_module
from typing import Optional

from .base import BaseConnector


def get_default_connector(config: Optional[dict] = None) -> BaseConnector:
    """Create an instance of the configured default connector.

    The configuration dictionary may contain a key ``connector`` with
    the dotted module path of a connector class (for example,
    ``"taamimflow.connectors.sefaria.SefariaConnector"``).  If the key
    is absent or invalid, a Sefaria connector is returned by default.

    :param config: Optional configuration dictionary.
    :return: An instantiated connector.
    """

    connector_path: str = "taamimflow.connectors.sefaria.SefariaConnector"
    if config:
        connector_path = config.get("connector", connector_path)
    module_name, _, class_name = connector_path.rpartition(".")
    try:
        module = import_module(module_name)
        cls = getattr(module, class_name)
        if not issubclass(cls, BaseConnector):
            raise TypeError(f"{connector_path} is not a subclass of BaseConnector")
        return cls()
    except Exception:
        # Fallback to default
        from .sefaria import SefariaConnector  # noqa: WPS433
        return SefariaConnector()