"""Ta'amimFlow core package.

Ta'amimFlow is a modular, extensible platform for learning and practicing
Hebrew cantillation (ta'amim) on modern systems.  It is inspired by the
original TropeTrainer application but is being rebuilt from the ground up
using open data sources and modern technology.  All heavy logic
for parsing trope definitions, managing calendar data, retrieving texts
from external sources, and rendering content lives in subpackages of
``taamimflow``.

The top‑level package exposes high level entrypoints and shared
functionality.  Importing ``taamimflow`` will automatically expose
important classes and functions under a concise namespace, for example:

.. code-block:: python

   from taamimflow import AppConfig, get_default_connector, MainWindow

The project is organised into several subpackages:

``config``
    Loading and managing application configuration.

``connectors``
    Interfaces for retrieving biblical text and metadata from a variety
    of sources (e.g., Sefaria API, local files).  New connectors can be
    added without modifying the core application.

``data``
    Parsers for static XML definitions such as trope melodies, trope
    names and reading schedules (sedrot).  These parsers return Python
    data structures that can be consumed by the GUI or audio engine.

``gui``
    Widgets, dialogs and the main application window built with
    PyQt6.  The GUI communicates with connectors and data parsers to
    display text, control audio playback and manage user interactions.

``utils``
    Helper modules such as audio handling and Hebrew text utilities.

The build is intentionally minimal at this stage.  Many components are
implemented as stubs with clear docstrings describing their intended
purpose.  Developers are encouraged to extend the functionality by
following the patterns established here.  See the README for guidance
on contributing and the technical roadmap for the long‑term vision.
"""

from .config import AppConfig, get_app_config  # noqa: F401
from .connectors import get_default_connector  # noqa: F401
from .gui.main_window import MainWindow  # noqa: F401