"""Main application window for Ta'amimFlow.

This window ties together the text display widget, the reading
selection dialog and the connector used to fetch text.  The toolbar
provides simple controls for toggling view and colour modes.  The
menu bar exposes actions to open a parasha and exit the application.

At present, this implementation focuses on the core workflow:

1.  User selects "Open Reading" from the File menu.
2.  A dialog lists available parshiot (loaded from ``sedrot.xml``).
3.  Upon selection, the connector fetches the corresponding text.
4.  The text is naively tokenised into words and displayed.

In subsequent versions, the tokenisation should be replaced with a
proper parser that extracts trope marks and assigns them to the
appropriate groups.  Similarly, the toolbar can be extended with
audio controls and other advanced features.
"""

from __future__ import annotations

from typing import List, Tuple

from PyQt6.QtWidgets import (
    QMainWindow,
    QAction,
    QToolBar,
    QMessageBox,
    QApplication,
    QDialog,
)
from PyQt6.QtCore import Qt, QSize

from ..config import get_app_config
from ..connectors import get_default_connector
from ..connectors.base import BaseConnector
from .text_widget import ModernTorahTextWidget
from .open_reading_dialog import OpenReadingDialog


class MainWindow(QMainWindow):
    """Main window for the Ta'amimFlow application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Ta'amimFlow")
        self.resize(1024, 768)
        # Load configuration and connector
        config = get_app_config()
        connector_config = config.get("connector", default={})
        self.connector: BaseConnector = get_default_connector(connector_config)
        # Central widget
        self.text_widget = ModernTorahTextWidget()
        self.setCentralWidget(self.text_widget)
        # Create menu and toolbar
        self._create_actions()
        self._create_menus()
        self._create_toolbar()

    def _create_actions(self) -> None:
        # File menu actions
        self.open_reading_act = QAction("Open Reading", self)
        self.open_reading_act.setShortcut("Ctrl+O")
        self.open_reading_act.triggered.connect(self.open_reading)
        self.exit_act = QAction("Exit", self)
        self.exit_act.setShortcut("Ctrl+Q")
        self.exit_act.triggered.connect(QApplication.instance().quit)
        # View mode actions
        self.modern_mode_act = QAction("Modern", self)
        self.modern_mode_act.setCheckable(True)
        self.modern_mode_act.setChecked(True)
        self.modern_mode_act.triggered.connect(lambda: self.set_view_mode("modern"))
        self.stam_mode_act = QAction("STAM", self)
        self.stam_mode_act.setCheckable(True)
        self.stam_mode_act.triggered.connect(lambda: self.set_view_mode("stam"))
        self.tikkun_mode_act = QAction("Tikkun", self)
        self.tikkun_mode_act.setCheckable(True)
        self.tikkun_mode_act.triggered.connect(lambda: self.set_view_mode("tikkun"))
        # Colour mode actions
        self.no_color_act = QAction("No Color", self)
        self.no_color_act.setCheckable(True)
        self.no_color_act.triggered.connect(lambda: self.set_color_mode("no_colors"))
        self.trope_color_act = QAction("Trope Colors", self)
        self.trope_color_act.setCheckable(True)
        self.trope_color_act.setChecked(True)
        self.trope_color_act.triggered.connect(lambda: self.set_color_mode("trope_colors"))
        self.symbol_color_act = QAction("Symbol Colors", self)
        self.symbol_color_act.setCheckable(True)
        self.symbol_color_act.triggered.connect(lambda: self.set_color_mode("symbol_colors"))

    def _create_menus(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction(self.open_reading_act)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_act)
        view_menu = menubar.addMenu("View")
        view_mode_menu = view_menu.addMenu("View Mode")
        view_mode_menu.addAction(self.modern_mode_act)
        view_mode_menu.addAction(self.stam_mode_act)
        view_mode_menu.addAction(self.tikkun_mode_act)
        color_mode_menu = view_menu.addMenu("Color Mode")
        color_mode_menu.addAction(self.no_color_act)
        color_mode_menu.addAction(self.trope_color_act)
        color_mode_menu.addAction(self.symbol_color_act)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.addAction(self.open_reading_act)
        toolbar.addSeparator()
        toolbar.addAction(self.modern_mode_act)
        toolbar.addAction(self.stam_mode_act)
        toolbar.addAction(self.tikkun_mode_act)
        toolbar.addSeparator()
        toolbar.addAction(self.no_color_act)
        toolbar.addAction(self.trope_color_act)
        toolbar.addAction(self.symbol_color_act)
        self.addToolBar(toolbar)

    def set_view_mode(self, mode: str) -> None:
        self.text_widget.set_view_mode(mode)
        # update check states
        self.modern_mode_act.setChecked(mode == "modern")
        self.stam_mode_act.setChecked(mode == "stam")
        self.tikkun_mode_act.setChecked(mode == "tikkun")

    def set_color_mode(self, mode: str) -> None:
        self.text_widget.set_color_mode(mode)
        self.no_color_act.setChecked(mode == "no_colors")
        self.trope_color_act.setChecked(mode == "trope_colors")
        self.symbol_color_act.setChecked(mode == "symbol_colors")

    def open_reading(self) -> None:
        dialog = OpenReadingDialog(self)
        if dialog.exec() == QDialog.Accepted:
            parasha = dialog.selected_parasha
            if parasha:
                try:
                    text = self.connector.get_parasha(parasha)
                    tokens = self._tokenise(text)
                    self.text_widget.set_text(tokens)
                except Exception as exc:
                    QMessageBox.warning(self, "Error", f"Failed to load parasha: {exc}")

    def _tokenise(self, text: str) -> List[Tuple[str, str, str]]:
        """Naively split a passage into tokens for display.

        This method is a placeholder for a proper tokeniser that would
        parse cantillation marks and assign trope groups.  Currently it
        splits on whitespace and assigns a dummy trope group and symbol.
        """
        words = text.split()
        tokens: List[Tuple[str, str, str]] = []
        for w in words:
            tokens.append((w, "Sof Pasuk", "✱"))
        return tokens