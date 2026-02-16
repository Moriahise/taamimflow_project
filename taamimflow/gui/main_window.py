"""Main application window for Ta'amimFlow.

This module defines the :class:`MainWindow` class which ties
together the text display widget, the reading selection dialog,
the musical notation widget, the transliteration module and
the connector used to fetch text from an external source.  The
interface has been expanded to resemble the complete TropeTrainer UI
with a menu bar, a richly featured toolbar and a split central area
containing both the text display and a panel of controls.

The design deliberately avoids embedding business logic directly in
the GUI.  Reading selection is delegated to :class:`OpenReadingDialog`
and text retrieval is performed by the connector returned from
``get_default_connector``.  A legacy tokenisation method is retained
for backward compatibility; the preferred path now uses the real
:func:`tokenise` function from ``trope_parser``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

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
    QFileDialog,
)
from PyQt6.QtGui import QAction, QFont, QColor, QPalette
from PyQt6.QtCore import Qt, QSize

from ..config import get_app_config
from ..connectors import get_default_connector
from ..connectors.base import BaseConnector
from .text_widget import ModernTorahTextWidget
from .open_reading_dialog import OpenReadingDialog
from .notation_widget import TropeNotationPanel
from ..utils.trope_parser import tokenise, Token, GROUPS, get_trope_group

# ── Optional imports with safe fallbacks ──
# Customize dialog (from V5)
try:
    from .customize_dialog import CustomizeColorsDialog, DEFAULT_TROPE_COLORS
    _HAS_CUSTOMIZE_DIALOG = True
except ImportError:
    _HAS_CUSTOMIZE_DIALOG = False
    DEFAULT_TROPE_COLORS: Dict[str, str] = {}  # type: ignore[no-redef]

# Transliteration module (new)
try:
    from ..utils.transliteration import (
        transliterate_word,
        get_table as get_pronunciation_table,
    )
    _HAS_TRANSLITERATION = True
except ImportError:
    _HAS_TRANSLITERATION = False

    def transliterate_word(word, table=None):  # type: ignore[misc]
        return ["..."]

    def get_pronunciation_table(name):  # type: ignore[misc]
        return None


class MainWindow(QMainWindow):
    """Main window for the Ta'amimFlow application."""

    def __init__(self) -> None:
        super().__init__()
        # Track current selection and display modes
        self.current_parsha: str | None = None
        self.current_book: str | None = None
        self.current_view_mode: str = "modern"
        self.current_color_mode: str = "trope_colors"
        self.current_pronunciation: str = "Sephardi"
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
    # Menu bar  (V5 structure preserved + new features merged)
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
        # Action to open a local text file
        open_file_action = QAction("O&pen Text File...", self)
        open_file_action.setShortcut("Ctrl+T")
        open_file_action.triggered.connect(self.open_text_file)
        file_menu.addAction(open_file_action)
        file_menu.addSeparator()
        # Customize colours (from V5)
        customize_action = QAction("&Customize...", self)
        customize_action.triggered.connect(self.open_customize_dialog)
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
        # View mode sub‑menu (V5 descriptive labels preserved)
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
        # Colour mode sub‑menu (V5 descriptive labels preserved)
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
    # Customisation  (from V5 – fully preserved)
    # ------------------------------------------------------------------
    def open_customize_dialog(self) -> None:
        """Open the colour customisation dialog.

        This method instantiates :class:`CustomizeColorsDialog` with the
        current trope colour mapping, shows it modally, and updates
        the text widget if the user accepts the changes.  Colours not
        included in the returned mapping are left unchanged.  After
        updating the colours, the display is refreshed via
        ``update_display`` if available.  Finally, the status bar is
        updated to reflect that colours were modified.
        """
        if not _HAS_CUSTOMIZE_DIALOG:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Customize",
                "The customize_dialog module is not available.\n"
                "Please ensure customize_dialog.py is in the gui package.",
            )
            return

        # Determine the current colour mapping; use the widget's
        # ``trope_colors`` attribute if available, otherwise fall back
        # to the defaults defined in customize_dialog.
        current_colors: Dict[str, str]
        if hasattr(self.torah_text, "trope_colors") and isinstance(
            self.torah_text.trope_colors, dict
        ):
            current_colors = self.torah_text.trope_colors
        else:
            # Use a shallow copy to avoid modifying globals
            current_colors = DEFAULT_TROPE_COLORS.copy()
        dialog = CustomizeColorsDialog(current_colors, self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            new_colors = dialog.get_colors()
            # Merge the new colours into the existing mapping
            if hasattr(self.torah_text, "trope_colors") and isinstance(
                self.torah_text.trope_colors, dict
            ):
                # Update only the keys we provide
                for k, v in new_colors.items():
                    self.torah_text.trope_colors[k] = v
            # Refresh the display if the widget exposes update_display
            if hasattr(self.torah_text, "update_display"):
                try:
                    self.torah_text.update_display()
                except Exception:
                    pass
            # Ensure the colour mode remains set to trope colours if no
            # colours are currently selected.  This will update toggle
            # states and redraw accordingly.
            self.set_color_mode("trope_colors")
            self.statusBar().showMessage(
                "Colours updated | View: "
                + self.current_view_mode.replace("_", " ").title()
                + " | Color: Trope Colors"
            )

    # ------------------------------------------------------------------
    # Toolbar  (V5 structure with explicit tooltips preserved)
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
        # View mode buttons (Group 1)  – V5 style with explicit tooltips
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
        # Colour mode buttons (Group 2)  – V5 style with explicit tooltips
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
    # Central widget  (V5 layout preserved + new panels added)
    # ------------------------------------------------------------------
    def create_central_widget(self) -> None:
        """Create the central widget with text and controls panels."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()

        # ── Text panel ──
        text_panel = QWidget()
        text_layout = QVBoxLayout()

        # Titles (V5 styling preserved)
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

        # Modern Torah text widget  (+ word_clicked signal – new)
        self.torah_text = ModernTorahTextWidget()
        self.torah_text.setPlaceholderText(
            "Select File → Open Reading to choose a Torah portion..."
        )
        self.torah_text.word_clicked.connect(self._on_word_clicked)
        text_layout.addWidget(self.torah_text)

        # Translation  (V5 preserved)
        translation_label = QLabel("Translation:")
        translation_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        text_layout.addWidget(translation_label)
        self.translation_text = QLabel("")
        self.translation_text.setWordWrap(True)
        self.translation_text.setStyleSheet(
            "padding: 10px; background-color: #E8E8E0; border: 1px solid #999;"
        )
        self.translation_text.setMinimumHeight(60)
        text_layout.addWidget(self.translation_text)

        # Musical Notation label  (V5 preserved as fallback text display)
        music_label = QLabel("Musical Notation:")
        music_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        text_layout.addWidget(music_label)
        # V5 legacy: simple QLabel for text-based note symbols
        self.music_notation = QLabel("")
        self.music_notation.setStyleSheet(
            "padding: 10px; background-color: #E8E8E0; border: 1px solid #999;"
        )
        self.music_notation.setMinimumHeight(20)
        text_layout.addWidget(self.music_notation)
        # NEW: QPainter notation panel with real staff / notes / syllables
        self.notation_panel = TropeNotationPanel()
        text_layout.addWidget(self.notation_panel)

        text_panel.setLayout(text_layout)

        # ── Controls panel ──
        controls_panel = QWidget()
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(10)

        # Melody selection  (V5 preserved + extra melody added)
        melody_group = QGroupBox("Melody")
        melody_layout = QVBoxLayout()
        melody_layout.addWidget(QLabel("Melody:"))
        self.melody_combo = QComboBox()
        self.melody_combo.addItems([
            "Sephardic - Syrian - Halab (Aleppo)",
            "Ashkenazi - Standard",
            "Ashkenazi - Spiro High Holiday",
        ])
        melody_layout.addWidget(self.melody_combo)
        melody_layout.addWidget(QLabel("Range:"))
        self.range_combo = QComboBox()
        self.range_combo.addItems(["Bass", "Tenor", "Alto", "Soprano"])
        melody_layout.addWidget(self.range_combo)
        melody_layout.addWidget(QPushButton("Melody Help"))
        melody_group.setLayout(melody_layout)
        controls_layout.addWidget(melody_group)

        # Pronunciation  (V5 Yemenite preserved + currentTextChanged – new)
        pronunciation_group = QGroupBox("Pronunciation/Accent")
        pronunciation_layout = QVBoxLayout()
        self.pronunciation_combo = QComboBox()
        self.pronunciation_combo.addItems(["Sephardi", "Ashkenazi", "Yemenite"])
        self.pronunciation_combo.currentTextChanged.connect(
            self._on_pronunciation_changed
        )
        pronunciation_layout.addWidget(self.pronunciation_combo)
        pronunciation_group.setLayout(pronunciation_layout)
        controls_layout.addWidget(pronunciation_group)

        # Pitch  (V5 preserved)
        pitch_group = QGroupBox("Pitch")
        pitch_layout = QVBoxLayout()
        self.pitch_spinbox = QSpinBox()
        self.pitch_spinbox.setRange(-12, 12)
        self.pitch_spinbox.setSuffix(" semitones")
        pitch_layout.addWidget(self.pitch_spinbox)
        pitch_group.setLayout(pitch_layout)
        controls_layout.addWidget(pitch_group)

        # Speed/Volume  (V5 preserved)
        speed_group = QGroupBox("Speed/Vol")
        speed_layout = QVBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        speed_layout.addWidget(self.speed_slider)
        self.speed_value_label = QLabel("100%")
        self.speed_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_value_label.setText(f"{v}%")
        )
        speed_layout.addWidget(self.speed_value_label)
        speed_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setValue(80)
        speed_layout.addWidget(self.volume_slider)
        self.volume_value_label = QLabel("80%")
        self.volume_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_value_label.setText(f"{v}%")
        )
        speed_layout.addWidget(self.volume_value_label)
        speed_group.setLayout(speed_layout)
        controls_layout.addWidget(speed_group)

        # Selected Trope info  (new – sidebar detail panel)
        self.trope_info_group = QGroupBox("Selected Trope")
        trope_info_layout = QVBoxLayout()
        self.trope_info_label = QLabel("Click a word to see info")
        self.trope_info_label.setWordWrap(True)
        self.trope_info_label.setStyleSheet("font-size: 11px; padding: 4px;")
        trope_info_layout.addWidget(self.trope_info_label)
        self.trope_info_group.setLayout(trope_info_layout)
        controls_layout.addWidget(self.trope_info_group)

        controls_layout.addStretch()
        controls_panel.setLayout(controls_layout)
        controls_panel.setMaximumWidth(250)

        # Splitter for resizing  (V5 preserved)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(text_panel)
        splitter.addWidget(controls_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)

    # ------------------------------------------------------------------
    # Word click handler – notation + transliteration  (new)
    # ------------------------------------------------------------------
    def _on_word_clicked(self, word: str, group_name: str, trope_marks: list) -> None:
        """Handle word click: show notation with real notes and transliteration.

        Updates the musical notation panel (staff + notes + syllables),
        the translation area, and the sidebar trope info group.
        """
        # ── Transliterate the Hebrew word to Latin syllables ──
        table = get_pronunciation_table(self.current_pronunciation)
        syllables = transliterate_word(word, table)

        # If transliteration produced nothing, use a fallback
        if not syllables:
            syllables = ["..."]

        # ── Update the musical notation panel ──
        primary_trope = trope_marks[0] if trope_marks else group_name
        self.notation_panel.set_trope(primary_trope, syllables)

        # ── Update the verse label inside notation panel ──
        translit_text = "  ".join(syllables)
        self.notation_panel.set_verse_text(
            f"Word: {word}    Trope: {group_name}    "
            f"Pronunciation: {translit_text}"
        )

        # ── Update the legacy music_notation label with a text summary ──
        self.music_notation.setText(
            f"{group_name.upper()}:  {translit_text}"
        )

        # ── Translation panel ──
        marks_str = ", ".join(trope_marks) if trope_marks else "none"
        self.translation_text.setText(
            f"<div style='direction: rtl; text-align: right;'>"
            f"<b style='font-size: 16px;'>{word}</b><br/>"
            f"Trope: {group_name}  |  Marks: {marks_str}</div>"
        )
        self.translation_text.setTextFormat(Qt.TextFormat.RichText)

        # ── Sidebar trope info ──
        group = get_trope_group(group_name)
        self.trope_info_label.setText(
            f"Word: {word}\n"
            f"Group: {group_name}\n"
            f"Marks: {marks_str}\n"
            f"Color: {group.color}\n"
            f"Rank: {group.rank}\n"
            f"Pronunciation: {translit_text}"
        )

        self.statusBar().showMessage(
            f"Selected: {group_name} | {translit_text} | "
            f"View: {self.current_view_mode.replace('_', ' ').title()} | "
            f"Color: {self.current_color_mode.replace('_', ' ').title()}"
        )

    # ------------------------------------------------------------------
    # Pronunciation change  (new)
    # ------------------------------------------------------------------
    def _on_pronunciation_changed(self, text: str) -> None:
        """Update the current pronunciation table when the user changes
        the selection in the Pronunciation/Accent dropdown."""
        self.current_pronunciation = text

    # ------------------------------------------------------------------
    # Reading operations  (V5 preserved + improved with real parser)
    # ------------------------------------------------------------------
    def open_reading_dialog(self) -> None:
        """Open the complete reading selection dialog."""
        dialog = OpenReadingDialog(self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted and dialog.selected_parsha:
            self.load_parsha(dialog.selected_parsha, dialog.selected_book)

    def load_parsha(self, parsha_name: str, book_name: str) -> None:
        """Load and display a parsha using the configured connector.

        This method loads the **full** reading (all aliyot) using the
        real trope parser to produce properly coloured tokens.
        """
        self.current_parsha = parsha_name
        self.current_book = book_name
        # Update titles
        self.title_label.setText(f"[{parsha_name}]")
        self.subtitle_label.setText("")
        self.book_label.setText(book_name)

        # ── Fetch FULL text (all aliyot) ──
        try:
            text = self.connector.get_parasha(parsha_name)
        except Exception:
            # Fallback: try partial if full fails
            try:
                if hasattr(self.connector, "get_parasha_partial"):
                    text = self.connector.get_parasha_partial(parsha_name)
                else:
                    text = ""
            except Exception:
                text = ""

        # ── Tokenise with the real trope parser ──
        tokens = tokenise(text)
        self.torah_text.set_tokens(tokens)

        # Generate translation and music notation overview  (V5 method)
        self.update_translation_and_music(tokens)

        # Reset notation panel (user must click a word)
        self.notation_panel.clear()
        self.notation_panel.set_verse_text("")
        self.trope_info_label.setText("Click a word to see info")

        # Update status bar  (V5 rich format preserved)
        self.statusBar().showMessage(
            f"Loaded: {parsha_name} ({book_name}) | {len(tokens)} words | "
            f"View: {self.current_view_mode.title()} | "
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
        # Update status bar  (V5 rich format preserved)
        self.statusBar().showMessage(
            f"View: {mode.replace('_', ' ').title()} | "
            f"Color: {self.current_color_mode.replace('_', ' ').title()}"
        )

    def set_color_mode(self, mode: str) -> None:
        """Set the colour mode and update the display and toggle states."""
        self.current_color_mode = mode
        self.torah_text.set_color_mode(mode)
        # Update toggle buttons
        self.no_colors_btn.setChecked(mode == "no_colors")
        self.trope_colors_btn.setChecked(mode == "trope_colors")
        self.symbol_colors_btn.setChecked(mode == "symbol_colors")
        # Update status bar  (V5 rich format preserved)
        self.statusBar().showMessage(
            f"View: {self.current_view_mode.replace('_', ' ').title()} | "
            f"Color: {mode.replace('_', ' ').title()}"
        )

    # ------------------------------------------------------------------
    # File open operation  (V5 preserved + improved with real parser)
    # ------------------------------------------------------------------
    def open_text_file(self) -> None:
        """Prompt the user to open a local Tanach text file (UTF‑8 encoded).

        If the user selects a file, its contents are read, tokenised and
        displayed in the central text widget.  Titles and status
        information are updated accordingly.  Unsupported or unreadable
        files are silently ignored.
        """
        # Use QFileDialog to get the path from the user.  Restrict to
        # plain text files for Tanach passages.
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Tanach Text File",
            "",
            "Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            # Reading failed; do nothing
            return

        # Tokenise with the real trope parser and display
        tokens = tokenise(text)
        self.torah_text.set_tokens(tokens)

        # Update labels: use file name as parsha name; book unspecified
        import os

        base_name = os.path.basename(file_path)
        self.title_label.setText(f"[{base_name}]")
        self.subtitle_label.setText("")
        self.book_label.setText("Local File")
        self.translation_text.setText("")
        self.music_notation.setText("")
        self.current_parsha = base_name
        self.current_book = "Local File"

        # Generate translation and music notation for the local file  (V5)
        self.update_translation_and_music(tokens)

        # Reset notation panel
        self.notation_panel.clear()
        self.notation_panel.set_verse_text("")
        self.trope_info_label.setText("Click a word to see info")

        self.statusBar().showMessage(
            f"Loaded local file: {base_name} | {len(tokens)} words | "
            f"View: {self.current_view_mode.title()} | "
            f"Color: {self.current_color_mode.replace('_', ' ').title()}"
        )

    # ------------------------------------------------------------------
    # Utility – legacy tokeniser  (from V5 – preserved for compat)
    # ------------------------------------------------------------------
    def _tokenise(self, text: str) -> List[Tuple[str, str, str]]:
        """Naively split a passage into tokens for display.

        This method is a legacy placeholder from V5 retained for
        backward compatibility.  The preferred method is to use the
        module-level :func:`tokenise` from ``trope_parser`` which
        produces proper :class:`Token` objects with correct trope
        group assignments and colours.

        :param text: Raw Hebrew text.
        :return: List of ``(word, trope_group, symbol)`` tuples.
        """
        words = text.split()
        tokens: List[Tuple[str, str, str]] = []
        for w in words:
            tokens.append((w, "Sof Pasuk", "✱"))
        return tokens

    # ------------------------------------------------------------------
    # Translation and music notation  (from V5 – improved for Token)
    # ------------------------------------------------------------------
    def update_translation_and_music(self, tokens) -> None:
        """Populate the translation and musical notation fields.

        This helper constructs simple placeholder values for the
        translation and music notation based on the provided tokens.
        In the absence of a network connection or a translation API,
        the translation consists of the first line of text rendered
        verbatim.  The musical notation is represented by a sequence
        of note glyphs derived from the trope group of each token.

        Accepts either new-style :class:`Token` objects or legacy
        ``(word, trope_group, symbol)`` tuples for backward
        compatibility.

        :param tokens: List of Token objects or (word, group, symbol) tuples.
        """
        if not tokens:
            self.translation_text.setText("")
            self.music_notation.setText("")
            return

        # Extract words and trope groups – handle both Token objects
        # and legacy (word, group, symbol) tuples
        words: List[str] = []
        groups: List[str] = []
        for t in tokens:
            if isinstance(t, tuple):
                words.append(t[0])
                groups.append(t[1])
            else:
                # Token dataclass
                words.append(t.word)
                groups.append(t.group_name)

        # Join into paragraphs separated by newlines (crude fallback)
        # Use up to 40 words to avoid overly long lines
        translation_snippet = " ".join(words[:40])
        # Prepend a warning about placeholder translation if offline
        self.translation_text.setText(
            f"{translation_snippet}\n\n(Translation placeholder – network unavailable)"
        )

        # Build a simple music notation line: map trope groups to symbols
        note_map = {
            "Sof Pasuk": "♪",
            "Zakef Katon": "♬",
            "Zakef": "♬",
            "Etnachta": "♩",
            "Revia": "♫",
            "Segol": "♭",
            "Tipeha": "♪",
            "Merkha": "♪",
            "Munach": "♪",
            "Mahpakh": "♪",
            "Pashta": "♫",
            "Geresh": "♬",
            "Gershayim": "♬",
            "Pazer": "♭",
            "Telisha Gedola": "♮",
            "Telisha Qetana": "♮",
            "Darga": "♪",
            "Qadma": "♪",
            "Zarqa": "♫",
            "Tevir": "♩",
            "End of Aliyah": "♯",
            "End of Book": "♮",
        }
        notes = [note_map.get(g, "♪") for g in groups[:60]]
        music_line = " ".join(notes)
        self.music_notation.setText(music_line)
