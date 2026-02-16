"""Main application window for Ta'amimFlow.

This module defines the :class:`MainWindow` class which ties
together the text display widget, the reading selection dialog and
the connector used to fetch text from an external source.  The
interface has been expanded to resemble the complete TropeTrainer UI
with a menu bar, a richly featured toolbar and a split central area
containing both the text display and a panel of controls.

The design deliberately avoids embedding business logic directly in
the GUI.  Reading selection is delegated to :class:`OpenReadingDialog`
and text retrieval is performed by the connector returned from
``get_default_connector``.  A naive tokenisation method is provided
to convert plain text into a sequence of triples ``(word, trope_group,
symbol)`` suitable for display by :class:`ModernTorahTextWidget`.
"""

from __future__ import annotations

from typing import List, Tuple

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QToolBar,
    QApplication,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QComboBox,
    QSpinBox,
    QSlider,
    QSplitter,
    QDialog,
)
from PyQt6.QtGui import QAction, QFont, QColor, QPalette
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
        # Track current selection and display modes
        self.current_parsha: str | None = None
        self.current_book: str | None = None
        self.current_view_mode: str = "modern"
        self.current_color_mode: str = "trope_colors"
        # Load configuration and connector
        config = get_app_config()
        connector_config = config.get("connector", default={})
        self.connector: BaseConnector = get_default_connector(connector_config)
        # Build UI
        self.init_ui()

    def init_ui(self) -> None:
        """Set up the window title, palette and child widgets."""
        self.setWindowTitle("TropeTrainer 2.0 - Torah Reading Trainer")
        self.setGeometry(100, 100, 1200, 800)
        # Light grey background to match the classic application
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        self.setPalette(palette)
        # Menu bar and toolbar
        self.create_menu_bar()
        self.create_modern_toolbar()
        # Central area
        self.create_central_widget()
        # Status bar
        self.statusBar().showMessage("Ready - Select File → Open Reading to begin")

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------
    def create_menu_bar(self) -> None:
        """Create the application menu bar."""
        menubar = self.menuBar()
        # FILE
        file_menu = menubar.addMenu("&File")
        open_action = QAction("&Open Reading...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_reading_dialog)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        customize_action = QAction("&Customize...", self)
        file_menu.addAction(customize_action)
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        # PLAY (placeholder for future audio controls)
        play_menu = menubar.addMenu("&Play")
        play_action = QAction("&Play", self)
        play_action.setShortcut("Space")
        play_menu.addAction(play_action)
        # VIEW
        view_menu = menubar.addMenu("&View")
        # View mode sub‑menu
        view_mode_menu = view_menu.addMenu("View Mode")
        modern_action = QAction("&Modern (with vowels)", self)
        modern_action.triggered.connect(lambda: self.set_view_mode("modern"))
        view_mode_menu.addAction(modern_action)
        stam_action = QAction("&STAM (letters only)", self)
        stam_action.triggered.connect(lambda: self.set_view_mode("stam"))
        view_mode_menu.addAction(stam_action)
        tikkun_action = QAction("&Tikkun (two columns)", self)
        tikkun_action.triggered.connect(lambda: self.set_view_mode("tikkun"))
        view_mode_menu.addAction(tikkun_action)
        view_menu.addSeparator()
        # Colour mode sub‑menu
        color_mode_menu = view_menu.addMenu("Color Mode")
        no_colors_action = QAction("&No Colors", self)
        no_colors_action.triggered.connect(lambda: self.set_color_mode("no_colors"))
        color_mode_menu.addAction(no_colors_action)
        trope_colors_action = QAction("&Trope Group Colors", self)
        trope_colors_action.triggered.connect(lambda: self.set_color_mode("trope_colors"))
        color_mode_menu.addAction(trope_colors_action)
        symbol_colors_action = QAction("&Symbol Colors", self)
        symbol_colors_action.triggered.connect(lambda: self.set_color_mode("symbol_colors"))
        color_mode_menu.addAction(symbol_colors_action)
        # HELP
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------
    def create_modern_toolbar(self) -> None:
        """Create the primary toolbar with grouped toggle buttons."""
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        # File operations
        toolbar.addAction(QAction("📂", self, toolTip="Open", triggered=self.open_reading_dialog))
        toolbar.addAction(QAction("💾", self, toolTip="Save"))
        toolbar.addAction(QAction("🖨️", self, toolTip="Print"))
        toolbar.addSeparator()
        # View mode buttons (Group 1)
        self.view_mode_group = QGroupBox()
        self.stam_btn = QPushButton("📜\nSTAM")
        self.stam_btn.setCheckable(True)
        self.stam_btn.setToolTip("STAM letters only (no vowels/tropes)")
        self.stam_btn.setFixedSize(70, 50)
        self.stam_btn.clicked.connect(lambda: self.set_view_mode("stam"))
        self.modern_btn = QPushButton("📖\nModern")
        self.modern_btn.setCheckable(True)
        self.modern_btn.setChecked(True)
        self.modern_btn.setToolTip("Modern with vowels & tropes")
        self.modern_btn.setFixedSize(70, 50)
        self.modern_btn.clicked.connect(lambda: self.set_view_mode("modern"))
        self.tikkun_btn = QPushButton("📋\nTikkun")
        self.tikkun_btn.setCheckable(True)
        self.tikkun_btn.setToolTip("Tikkun style (two columns)")
        self.tikkun_btn.setFixedSize(70, 50)
        self.tikkun_btn.clicked.connect(lambda: self.set_view_mode("tikkun"))
        # Colour mode buttons (Group 2)
        self.no_colors_btn = QPushButton("⬜\nNo Color")
        self.no_colors_btn.setCheckable(True)
        self.no_colors_btn.setToolTip("No color highlighting")
        self.no_colors_btn.setFixedSize(80, 50)
        self.no_colors_btn.clicked.connect(lambda: self.set_color_mode("no_colors"))
        self.trope_colors_btn = QPushButton("🌈\nTrope")
        self.trope_colors_btn.setCheckable(True)
        self.trope_colors_btn.setChecked(True)
        self.trope_colors_btn.setToolTip("Color by trope groups")
        self.trope_colors_btn.setFixedSize(80, 50)
        self.trope_colors_btn.clicked.connect(lambda: self.set_color_mode("trope_colors"))
        self.symbol_colors_btn = QPushButton("⭐\nSymbol")
        self.symbol_colors_btn.setCheckable(True)
        self.symbol_colors_btn.setToolTip("Color by symbols")
        self.symbol_colors_btn.setFixedSize(80, 50)
        self.symbol_colors_btn.clicked.connect(lambda: self.set_color_mode("symbol_colors"))
        # Add widgets to toolbar
        toolbar.addWidget(self.stam_btn)
        toolbar.addWidget(self.modern_btn)
        toolbar.addWidget(self.tikkun_btn)
        toolbar.addSeparator()
        toolbar.addWidget(self.no_colors_btn)
        toolbar.addWidget(self.trope_colors_btn)
        toolbar.addWidget(self.symbol_colors_btn)
        toolbar.addSeparator()
        # Playback controls (placeholders)
        toolbar.addAction(QAction("⏮️", self, toolTip="First"))
        toolbar.addAction(QAction("◀️", self, toolTip="Previous"))
        toolbar.addAction(QAction("⏯️", self, toolTip="Play/Pause"))
        toolbar.addAction(QAction("▶️", self, toolTip="Next"))
        toolbar.addAction(QAction("⏭️", self, toolTip="Last"))
        toolbar.addSeparator()
        # Tools (placeholders)
        toolbar.addAction(QAction("🔍", self, toolTip="Search"))
        toolbar.addAction(QAction("⚙️", self, toolTip="Settings"))

    # ------------------------------------------------------------------
    # Central widget
    # ------------------------------------------------------------------
    def create_central_widget(self) -> None:
        """Create the central widget with text and controls panels."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()
        # Text panel
        text_panel = QWidget()
        text_layout = QVBoxLayout()
        # Titles
        self.title_label = QLabel("[Select a Parsha]")
        self.title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #8B008B; padding: 10px;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_layout.addWidget(self.title_label)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.subtitle_label.setStyleSheet("color: #8B008B; padding: 5px;")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_layout.addWidget(self.subtitle_label)
        self.book_label = QLabel("")
        self.book_label.setFont(QFont("Arial", 12))
        self.book_label.setStyleSheet("color: gray;")
        self.book_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        text_layout.addWidget(self.book_label)
        # Modern Torah text widget
        self.torah_text = ModernTorahTextWidget()
        self.torah_text.setPlaceholderText("Select File → Open Reading to choose a Torah portion...")
        text_layout.addWidget(self.torah_text)
        # Translation
        translation_label = QLabel("Translation:")
        text_layout.addWidget(translation_label)
        self.translation_text = QLabel("")
        self.translation_text.setWordWrap(True)
        self.translation_text.setStyleSheet("padding: 10px; background-color: white;")
        self.translation_text.setMinimumHeight(60)
        text_layout.addWidget(self.translation_text)
        # Musical notation
        music_label = QLabel("Musical Notation:")
        text_layout.addWidget(music_label)
        self.music_notation = QLabel("")
        self.music_notation.setStyleSheet("padding: 10px; background-color: white;")
        self.music_notation.setMinimumHeight(60)
        text_layout.addWidget(self.music_notation)
        text_panel.setLayout(text_layout)
        # Controls panel
        controls_panel = QWidget()
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(10)
        # Melody selection
        melody_group = QGroupBox("Melody")
        melody_layout = QVBoxLayout()
        melody_layout.addWidget(QLabel("Melody:"))
        self.melody_combo = QComboBox()
        self.melody_combo.addItems([
            "Sephardic - Syrian - Halab (Aleppo)",
            "Ashkenazi - Standard",
        ])
        melody_layout.addWidget(self.melody_combo)
        melody_layout.addWidget(QLabel("Range:"))
        self.range_combo = QComboBox()
        self.range_combo.addItems(["Bass", "Tenor", "Alto", "Soprano"])
        melody_layout.addWidget(self.range_combo)
        melody_layout.addWidget(QPushButton("Melody Help"))
        melody_group.setLayout(melody_layout)
        controls_layout.addWidget(melody_group)
        # Pronunciation
        pronunciation_group = QGroupBox("Pronunciation/Accent")
        pronunciation_layout = QVBoxLayout()
        self.pronunciation_combo = QComboBox()
        self.pronunciation_combo.addItems(["Ashkenazi", "Sephardi", "Yemenite"])
        pronunciation_layout.addWidget(self.pronunciation_combo)
        pronunciation_group.setLayout(pronunciation_layout)
        controls_layout.addWidget(pronunciation_group)
        # Pitch
        pitch_group = QGroupBox("Pitch")
        pitch_layout = QVBoxLayout()
        self.pitch_spinbox = QSpinBox()
        self.pitch_spinbox.setRange(-12, 12)
        self.pitch_spinbox.setSuffix(" semitones")
        pitch_layout.addWidget(self.pitch_spinbox)
        pitch_group.setLayout(pitch_layout)
        controls_layout.addWidget(pitch_group)
        # Speed/Volume
        speed_group = QGroupBox("Speed/Vol")
        speed_layout = QVBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        speed_layout.addWidget(self.speed_slider)
        self.speed_value_label = QLabel("100%")
        self.speed_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_slider.valueChanged.connect(lambda v: self.speed_value_label.setText(f"{v}%"))
        speed_layout.addWidget(self.speed_value_label)
        speed_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setValue(80)
        speed_layout.addWidget(self.volume_slider)
        self.volume_value_label = QLabel("80%")
        self.volume_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.volume_slider.valueChanged.connect(lambda v: self.volume_value_label.setText(f"{v}%"))
        speed_layout.addWidget(self.volume_value_label)
        speed_group.setLayout(speed_layout)
        controls_layout.addWidget(speed_group)
        controls_layout.addStretch()
        controls_panel.setLayout(controls_layout)
        controls_panel.setMaximumWidth(250)
        # Splitter for resizing
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(text_panel)
        splitter.addWidget(controls_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)

    # ------------------------------------------------------------------
    # Reading operations
    # ------------------------------------------------------------------
    def open_reading_dialog(self) -> None:
        """Open the complete reading selection dialog."""
        dialog = OpenReadingDialog(self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted and dialog.selected_parsha:
            self.load_parsha(dialog.selected_parsha, dialog.selected_book)

    def load_parsha(self, parsha_name: str, book_name: str) -> None:
        """Load and display a parsha using the configured connector."""
        self.current_parsha = parsha_name
        self.current_book = book_name
        # Update titles
        self.title_label.setText(f"[{parsha_name}]")
        self.subtitle_label.setText("")
        self.book_label.setText(book_name)
        # Fetch the text from the connector.  Errors are silently
        # ignored and result in empty content.
        try:
            text = self.connector.get_parasha(parsha_name)
        except Exception:
            text = ""
        tokens = self._tokenise(text)
        self.torah_text.set_text(tokens)
        # For now set translation and music notation to placeholders.
        self.translation_text.setText("")
        self.music_notation.setText("")
        # Update status bar
        self.statusBar().showMessage(
            f"Loaded: {parsha_name} ({book_name}) | View: {self.current_view_mode.title()} | "
            f"Color: {self.current_color_mode.replace('_', ' ').title()}"
        )

    def set_view_mode(self, mode: str) -> None:
        """Set the view mode and update the display and toggle states."""
        self.current_view_mode = mode
        self.torah_text.set_view_mode(mode)
        # Update toggle buttons
        self.modern_btn.setChecked(mode == "modern")
        self.stam_btn.setChecked(mode == "stam")
        self.tikkun_btn.setChecked(mode == "tikkun")
        # Update status bar
        self.statusBar().showMessage(
            f"View: {mode.replace('_', ' ').title()} | Color: {self.current_color_mode.replace('_', ' ').title()}"
        )

    def set_color_mode(self, mode: str) -> None:
        """Set the colour mode and update the display and toggle states."""
        self.current_color_mode = mode
        self.torah_text.set_color_mode(mode)
        # Update toggle buttons
        self.no_colors_btn.setChecked(mode == "no_colors")
        self.trope_colors_btn.setChecked(mode == "trope_colors")
        self.symbol_colors_btn.setChecked(mode == "symbol_colors")
        # Update status bar
        self.statusBar().showMessage(
            f"View: {self.current_view_mode.replace('_', ' ').title()} | Color: {mode.replace('_', ' ').title()}"
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def _tokenise(self, text: str) -> List[Tuple[str, str, str]]:
        """Naively split a passage into tokens for display.

        This method is a placeholder for a proper parser that would
        extract cantillation marks and assign trope groups.  Currently
        it splits on whitespace and assigns a dummy trope group and
        symbol (✱) to each word.
        """
        words = text.split()
        tokens: List[Tuple[str, str, str]] = []
        for w in words:
            tokens.append((w, "Sof Pasuk", "✱"))
        return tokens