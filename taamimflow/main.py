"""Ta'amimFlow application entry point.

This script can be invoked directly (``python -m taamimflow.main``) or
via the package's ``__main__`` module.  It initialises the Qt
application, creates the main window and starts the event loop.
"""

from __future__ import annotations

import sys
from PyQt6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()