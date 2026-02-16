"""
Configuration management for Ta'amimFlow.

The application reads its default settings from a JSON file (see
``config_default_settings.json`` at the repository root). These
settings can be overridden by user‑specific values stored in a
different location (for example, in the user's home directory).  This
module provides a simple API to load and merge configuration data.

The configuration schema mirrors the structure of the legacy
``config_default_settings.json`` provided with the original GUI
prototype.  While the default file contains sensible values for a
desktop application, you are encouraged to extend it as needed for
future features (e.g. network settings, connectors, caching options).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG_FILE: Path = Path(__file__).resolve().parent.parent / "config_default_settings.json"


@dataclass
class AppConfig:
    """In‑memory representation of the application configuration.

    Attributes mirror the keys in the JSON file.  Additional keys
    provided by the user will be preserved in the internal ``data``
    dictionary but may not have dedicated attributes on this class.
    """

    data: Dict[str, Any] = field(default_factory=dict)

    def get(self, *keys: str, default: Optional[Any] = None) -> Any:
        """Retrieve a nested configuration value safely.

        Usage::

            config = load_config()
            volume = config.get("audio", "default_volume", default=1.0)

        :param keys: Sequence of keys describing a path in the config.
        :param default: Value returned when the path does not exist.
        :return: The configuration value or ``default``.
        """

        current: Any = self.data
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    def merge(self, other: Dict[str, Any]) -> None:
        """Merge another dictionary into this configuration.

        When keys exist in both ``self.data`` and ``other``, values from
        ``other`` take precedence.  Nested dictionaries are merged
        recursively.
        """

        def _merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
            result = dict(a)
            for k, v in b.items():
                if isinstance(v, dict) and isinstance(a.get(k), dict):
                    result[k] = _merge(a[k], v)
                else:
                    result[k] = v
            return result

        self.data = _merge(self.data, other)


def load_config(user_config_path: Optional[os.PathLike] = None) -> AppConfig:
    """Load configuration from the default and optional user files.

    This helper reads the built‑in ``config_default_settings.json`` and
    overlays any user provided overrides.  The resulting dictionary is
    used to construct an :class:`AppConfig` instance.  If
    ``user_config_path`` does not exist, only the default config is
    loaded.

    :param user_config_path: Path to an optional JSON override file.
    :return: A fully merged :class:`AppConfig`.
    """

    with open(DEFAULT_CONFIG_FILE, "r", encoding="utf-8") as f:
        base = json.load(f)
    cfg = AppConfig(base)
    if user_config_path:
        user_path = Path(user_config_path)
        if user_path.is_file():
            with open(user_path, "r", encoding="utf-8") as uf:
                overrides = json.load(uf)
            cfg.merge(overrides)
    return cfg


def get_app_config() -> AppConfig:
    """Convenience accessor to obtain the global application configuration.

    The loader honours the ``TAAMIMFLOW_CONFIG`` environment variable.  If
    set, this variable should point to a JSON file containing user
    specific configuration overrides.  If not set, only the default
    configuration is used.

    :return: The loaded :class:`AppConfig`.
    """

    override_path = os.environ.get("TAAMIMFLOW_CONFIG")
    return load_config(override_path)