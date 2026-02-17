"""Connector registry for Ta'amimFlow.

Connectors are pluggable text sources.  The ``get_default_connector``
factory reads the ``connector`` section of the application config and
returns an appropriate :class:`BaseConnector` instance.

Currently supported connector types:
    * ``"sefaria"``  – calls the Sefaria public API (requires internet)
    * ``"local"``    – reads local tanach.us TXT files (fully offline)

Configuration example (config_default_settings.json)::

    {
        "connector": {
            "type": "local",
            "tanach_dir": "tanach_data",
            "preferred_format": "cantillation"
        }
    }

Or for Sefaria::

    {
        "connector": {
            "type": "sefaria",
            "base_url": "https://www.sefaria.org/api"
        }
    }
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .base import BaseConnector
from .sefaria import SefariaConnector
from .local_tanach import LocalTanachConnector

logger = logging.getLogger(__name__)

__all__ = [
    "BaseConnector",
    "SefariaConnector",
    "LocalTanachConnector",
    "get_default_connector",
]


def get_default_connector(config: Dict[str, Any] | None = None) -> BaseConnector:
    """Return a connector instance based on *config*.

    :param config: The ``connector`` section of the application config.
        Recognised keys:
        * ``type`` – "sefaria" or "local" (default: "sefaria")
        * All other keys are forwarded as kwargs to the connector class.
    :return: A ready-to-use :class:`BaseConnector`.
    """
    if config is None:
        config = {}

    connector_type = config.get("type", "sefaria").lower()

    if connector_type == "local":
        kwargs: Dict[str, Any] = {}
        if "tanach_dir" in config:
            kwargs["tanach_dir"] = config["tanach_dir"]
        if "preferred_format" in config:
            kwargs["preferred_format"] = config["preferred_format"]
        if "strip_cantillation" in config:
            kwargs["strip_cantillation"] = bool(config["strip_cantillation"])
        if "strip_paragraph_markers" in config:
            kwargs["strip_paragraph_markers"] = bool(
                config["strip_paragraph_markers"]
            )
        logger.info("Using LocalTanachConnector with kwargs=%s", kwargs)
        return LocalTanachConnector(**kwargs)

    elif connector_type == "sefaria":
        base_url = config.get("base_url", "https://www.sefaria.org/api")
        logger.info("Using SefariaConnector with base_url=%s", base_url)
        return SefariaConnector(base_url=base_url)

    else:
        logger.warning(
            "Unknown connector type %r, falling back to SefariaConnector",
            connector_type,
        )
        return SefariaConnector()
