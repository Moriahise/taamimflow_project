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

Changes in this version (V9 – merged V8 + open‑reading improvements):

* **Preserved from V8:** TropeNotationPanel, trope_parser tokenise,
  transliteration, word_clicked handler, pronunciation change handler,
  trope info sidebar, expanded note_map, safe fallback imports.
* **New:** :meth:`load_parsha` accepts ``reading_type``, ``cycle``,
  ``date`` and ``diaspora`` parameters and dispatches to the
  appropriate connector method (``get_parasha``, ``get_maftir`` or
  ``get_haftarah``).
* **New:** :meth:`open_reading_dialog` passes the selected reading
  type, triennial cycle, date and diaspora setting from the dialog.
* **New:** The status bar shows the current cycle when triennial
  reading is active.
"""

from __future__ import annotations

import inspect
import os
from datetime import date as _date
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
from PyQt6.QtCore import Qt, QSize, QDate

from ..config import get_app_config
from ..connectors import get_default_connector
from ..connectors.base import BaseConnector
from .text_widget import ModernTorahTextWidget, build_verse_metadata
from .open_reading_dialog import OpenReadingDialog
from .notation_widget import TropeNotationPanel
from ..utils.trope_parser import tokenise, Token, GROUPS, get_trope_group
from ..utils.sedrot_parser import get_aliyah_boundaries, get_parsha_start, get_book_name_for_reading, get_option_type, get_haftarah_refs, get_maftir_refs

# ── Optional imports with safe fallbacks ──
# Customize dialog (from V5)
try:
    from .customize_dialog import CustomizeColorsDialog, DEFAULT_TROPE_COLORS
    _HAS_CUSTOMIZE_DIALOG = True
except ImportError:
    _HAS_CUSTOMIZE_DIALOG = False
    DEFAULT_TROPE_COLORS: Dict[str, str] = {}  # type: ignore[no-redef]

# Transliteration module
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
        # New: track reading‑type, cycle, diaspora from open‑reading dialog
        self.current_cycle: int = 0
        self.current_reading_type: str = "Torah"
        self.current_holiday_option: str | None = None
        self.current_diaspora: bool = True
        # Load configuration and connector
        config = get_app_config()
        connector_config = config.get("connector", default={})
        self.connector: BaseConnector = get_default_connector(connector_config)
        # Build UI
        self.init_ui()

    def init_ui(self) -> None:
        """Set up the window title, palette and child widgets."""
        self.setWindowTitle("Ta'amimFlow – Torah Reading Trainer")
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
        self.statusBar().showMessage("Ready – Select File → Open Reading to begin")

    # ------------------------------------------------------------------
    # Menu bar  (V5 structure preserved + new features merged)
    # ------------------------------------------------------------------
    def create_menu_bar(self) -> None:
        """Create the application menu bar."""
        menubar = self.menuBar()
        # FILE
        file_menu = menubar.addMenu("&File")
        open_action = QAction("&Open Reading…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_reading_dialog)
        file_menu.addAction(open_action)
        # Action to open a local text file
        open_file_action = QAction("O&pen Text File…", self)
        open_file_action.setShortcut("Ctrl+T")
        open_file_action.triggered.connect(self.open_text_file)
        file_menu.addAction(open_file_action)
        file_menu.addSeparator()
        # Customize colours (from V5)
        customize_action = QAction("&Customize…", self)
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
    # Central widget  (V5 layout preserved + notation panel + new panels)
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

        # Modern Torah text widget  (+ word_clicked signal from V8)
        self.torah_text = ModernTorahTextWidget()
        self.torah_text.setPlaceholderText(
            "Select File → Open Reading to choose a Torah portion..."
        )
        self.torah_text.word_clicked.connect(self._on_word_clicked)
        text_layout.addWidget(self.torah_text)

        # Translation  (V5 preserved with V8 styling)
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
        # V8: QPainter notation panel with real staff / notes / syllables
        self.notation_panel = TropeNotationPanel()
        text_layout.addWidget(self.notation_panel)

        text_panel.setLayout(text_layout)

        # ── Controls panel ──
        controls_panel = QWidget()
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(10)

        # Melody selection  (V5 preserved + extra melody from V8)
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

        # Pronunciation  (V5 Yemenite preserved + currentTextChanged from V8)
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

        # Selected Trope info  (V8 – sidebar detail panel)
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
    # Word click handler – notation + transliteration  (from V8)
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
    # Pronunciation change  (from V8)
    # ------------------------------------------------------------------
    def _on_pronunciation_changed(self, text: str) -> None:
        """Update the current pronunciation table when the user changes
        the selection in the Pronunciation/Accent dropdown."""
        self.current_pronunciation = text

    # ------------------------------------------------------------------
    # Reading operations  (V8 preserved + NEW reading‑type dispatch)
    # ------------------------------------------------------------------
    def open_reading_dialog(self) -> None:
        """Open the complete reading selection dialog.

        After the user makes a selection, determine the type of reading
        (Torah, Haftarah or Maftir), the desired triennial cycle (if
        enabled) and the date/location options.  Pass these values to
        :meth:`load_parsha` so it can choose the appropriate connector
        method.
        """
        dialog = OpenReadingDialog(self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted and dialog.selected_parsha:
            # Determine cycle from dialog
            cycle: int = getattr(dialog, "cycle", 0)
            if cycle == 0 and hasattr(dialog, "triennial_checkbox"):
                if dialog.triennial_checkbox.isChecked():
                    cycle = dialog.cycle_spinbox.value()

            # Reading type from dialog
            reading_type = getattr(dialog, "reading_type", "Torah")

            # Date and location
            selected_date: QDate = getattr(
                dialog, "selected_date", None
            ) or QDate.currentDate()
            diaspora: bool = getattr(dialog, "diaspora", True)
            if hasattr(dialog, "diaspora_radio"):
                diaspora = dialog.diaspora_radio.isChecked()

            # Capture the specific sub-option chosen (e.g. "Day 8 (Weekday)")
            holiday_option: str | None = getattr(dialog, "selected_option", None)

            self.load_parsha(
                dialog.selected_parsha,
                dialog.selected_book or "",
                reading_type=reading_type,
                cycle=cycle,
                date=selected_date,
                diaspora=diaspora,
                holiday_option=holiday_option,
            )

    def load_parsha(
        self,
        parsha_name: str,
        book_name: str,
        *,
        reading_type: str = "Torah",
        cycle: int = 0,
        date: QDate | None = None,
        diaspora: bool = True,
        holiday_option: str | None = None,
    ) -> None:
        """Load and display a Torah portion, Haftarah or Maftir reading.

        This method loads the reading using the real trope parser to
        produce properly coloured tokens.

        :param parsha_name: The name of the parsha selected.
        :param book_name: The name of the book or category.
        :param reading_type: ``"Torah"``, ``"Haftarah"`` or ``"Maftir"``.
        :param cycle: Triennial cycle (0 = annual, 1–3).
        :param date: The date selected in the dialog.
        :param diaspora: Whether to use the Diaspora calendar.
        :param holiday_option: For holiday readings, the specific sub-option
            name chosen by the user (e.g. ``"Day 8 (Weekday)"`` for Pesach).
            When provided this overrides cycle-based option selection.
        """
        # Store current selection
        self.current_parsha = parsha_name
        self.current_book = book_name
        self.current_cycle = cycle
        self.current_reading_type = reading_type
        self.current_diaspora = diaspora
        self.current_holiday_option = holiday_option  # specific day/service option

        # Update titles
        # For holiday readings show "[Pesach: Day 8 (Weekday)]" in the title bar
        # to match TropeTrainer's display style.
        if holiday_option:
            title_text = f"[{parsha_name}: {holiday_option}]"
        else:
            title_text = f"[{parsha_name}]"
        self.title_label.setText(title_text)
        self.subtitle_label.setText(
            f"{reading_type}" + (f" – Cycle {cycle}" if cycle else "")
        )
        # ── Determine the actual book name from sedrot.xml ──────────
        # For Torah readings use the Torah book (e.g. "Bamidbar/Numbers").
        # For Haftarah, show the Nevi'im book (e.g. "Jeremiah").
        # For Megillot, show the Ketuvim book (e.g. "Ruth", "Esther").
        # Pass holiday_option so we look up the *specific* day's book,
        # not the first option of the holiday (e.g. Pesach Day 8 → Devarim).
        try:
            xml_book = get_book_name_for_reading(
                parsha_name,
                cycle=cycle,
                reading_type=reading_type,
                option_name=holiday_option,
            )
            self.book_label.setText(xml_book if xml_book else book_name)
        except Exception:
            self.book_label.setText(book_name)


        # Convert QDate to Python date for the connector
        py_date: _date | None = None
        if date is not None:
            try:
                py_date = _date(date.year(), date.month(), date.day())
            except Exception:
                py_date = None

        # ── Fetch text based on reading type (NEW dispatch logic) ──
        text = ""
        try:
            rt = reading_type.lower()
            if rt == "haftarah":
                # Use sedrot_parser to resolve the correct refs for the specific
                # option (e.g. "Shabbas Chanukah" vs standard Mikeitz Haftarah).
                # This ensures holiday_option is honoured at the text-loading stage.
                refs = get_haftarah_refs(
                    parsha_name, option_name=holiday_option
                )
                if refs and hasattr(self.connector, "get_text"):
                    parts: list = []
                    for ref in refs:
                        try:
                            parts.append(self.connector.get_text(ref))
                        except Exception as exc:
                            logger.warning("Skipping haftarah ref %r: %s", ref, exc)
                    text = "\n".join(parts)
                elif hasattr(self.connector, "get_haftarah"):
                    kwargs: Dict = {"cycle": cycle}
                    sig = inspect.signature(self.connector.get_haftarah)
                    if "for_date" in sig.parameters and py_date:
                        kwargs["for_date"] = py_date
                    text = self.connector.get_haftarah(parsha_name, **kwargs)
                elif hasattr(self.connector, "get_parasha_partial"):
                    text = self.connector.get_parasha_partial(parsha_name, cycle=cycle)
                else:
                    text = self.connector.get_parasha(parsha_name, cycle=cycle)

            elif rt == "maftir":
                # Same pattern: use sedrot_parser to pick the correct Maftir option
                # (e.g. "Chanukah Day 6" vs the standard Maftir).
                maftir_refs = get_maftir_refs(
                    parsha_name, option_name=holiday_option, cycle=cycle
                )
                if maftir_refs and hasattr(self.connector, "get_text"):
                    parts = []
                    for ref in maftir_refs:
                        try:
                            parts.append(self.connector.get_text(ref))
                        except Exception as exc:
                            logger.warning("Skipping maftir ref %r: %s", ref, exc)
                    text = "\n".join(parts)
                elif hasattr(self.connector, "get_maftir"):
                    text = self.connector.get_maftir(parsha_name, cycle=cycle)
                elif hasattr(self.connector, "get_parasha_partial"):
                    text = self.connector.get_parasha_partial(parsha_name, cycle=cycle)
                else:
                    text = self.connector.get_parasha(parsha_name, cycle=cycle)

            else:  # Torah reading
                # Use full reading (all aliyot)
                try:
                    text = self.connector.get_parasha(parsha_name, cycle=cycle)
                except Exception:
                    # Fallback: try partial if full fails
                    if hasattr(self.connector, "get_parasha_partial"):
                        text = self.connector.get_parasha_partial(parsha_name, cycle=cycle)
                    else:
                        text = ""

        except Exception:
            text = ""

        # ── Tokenise with the real trope parser ──
        tokens = tokenise(text)

        # ── Build verse/chapter/aliyah metadata ──
        # Try to get structured data from the connector first.
        # Fall back to deriving it from verse_end flags on the tokens.
        verse_metadata = self._extract_verse_metadata(
            parsha_name, tokens, reading_type, cycle, holiday_option
        )
        if verse_metadata:
            self.torah_text.set_tokens_with_metadata(tokens, verse_metadata)
        else:
            self.torah_text.set_tokens(tokens)

        # Generate translation and music notation overview  (V5 method)
        self.update_translation_and_music(tokens)

        # Reset notation panel (user must click a word)
        self.notation_panel.clear()
        self.notation_panel.set_verse_text("")
        self.trope_info_label.setText("Click a word to see info")

        # Update status bar with comprehensive information
        cycle_info = f" | Cycle: {cycle}" if cycle else ""
        diaspora_info = "Diaspora" if diaspora else "Israel"
        self.statusBar().showMessage(
            f"Loaded: {parsha_name} ({book_name}) | {len(tokens)} words | "
            f"Type: {reading_type} | {diaspora_info}{cycle_info} | "
            f"View: {self.current_view_mode.title()} | "
            f"Color: {self.current_color_mode.replace('_', ' ').title()}"
        )

    # ------------------------------------------------------------------
    # Verse / Chapter / Aliyah metadata extraction  (NEW)
    # ------------------------------------------------------------------

    # Lookup table: parsha name (lowercase, normalised) →
    #   (book_num, starting_chapter, starting_verse)
    # book_num: 1=Bereshit, 2=Shemot, 3=Vayikra, 4=Bamidbar, 5=Devarim
    _PARSHA_START_VERSES: Dict[str, Tuple[int, int, int]] = {
        # Bereshit
        "bereshit":              (1,  1,  1),
        "noach":                 (1,  6,  9),
        "lech lecha":            (1, 12,  1),
        "lech-lecha":            (1, 12,  1),
        "vayera":                (1, 18,  1),
        "chayei sarah":          (1, 23,  1),
        "chaye sarah":           (1, 23,  1),
        "toldot":                (1, 25, 19),
        "vayetzei":              (1, 28, 10),
        "vayishlach":            (1, 32,  4),
        "vayeshev":              (1, 37,  1),
        "miketz":                (1, 41,  1),
        "vayigash":              (1, 44, 18),
        "vayechi":               (1, 47, 28),
        # Shemot
        "shemot":                (2,  1,  1),
        "vaera":                 (2,  6,  2),
        "bo":                    (2, 10,  1),
        "beshalach":             (2, 13, 17),
        "beshalah":              (2, 13, 17),
        "yitro":                 (2, 18,  1),
        "mishpatim":             (2, 21,  1),
        "terumah":               (2, 25,  1),
        "tetzaveh":              (2, 27, 20),
        "ki tisa":               (2, 30, 11),
        "ki tissa":              (2, 30, 11),
        "vayakhel":              (2, 35,  1),
        "pekudei":               (2, 38, 21),
        "vayakhel-pekudei":      (2, 35,  1),
        # Vayikra
        "vayikra":               (3,  1,  1),
        "tzav":                  (3,  6,  1),
        "shemini":               (3,  9,  1),
        "tazria":                (3, 12,  1),
        "metzora":               (3, 14,  1),
        "tazria-metzora":        (3, 12,  1),
        "acharei mot":           (3, 16,  1),
        "acharei":               (3, 16,  1),
        "kedoshim":              (3, 19,  1),
        "acharei mot-kedoshim":  (3, 16,  1),
        "emor":                  (3, 21,  1),
        "behar":                 (3, 25,  1),
        "bechukotai":            (3, 26,  3),
        "behar-bechukotai":      (3, 25,  1),
        # Bamidbar
        "bamidbar":              (4,  1,  1),
        "nasso":                 (4,  4, 21),
        "behaalotcha":           (4,  8,  1),
        "beha'alotcha":          (4,  8,  1),
        "beha'alotecha":         (4,  8,  1),
        "shelach":               (4, 13,  1),
        "shelach lecha":         (4, 13,  1),
        "korach":                (4, 16,  1),
        "chukat":                (4, 19,  1),
        "balak":                 (4, 22,  2),
        "pinchas":               (4, 25, 10),
        "matot":                 (4, 30,  2),
        "masei":                 (4, 33,  1),
        "matot-masei":           (4, 30,  2),
        # Devarim
        "devarim":               (5,  1,  1),
        "vaetchanan":            (5,  3, 23),
        "ekev":                  (5,  7, 12),
        "reeh":                  (5, 11, 26),
        "shoftim":               (5, 16, 18),
        "ki tetze":              (5, 21, 10),
        "ki tavo":               (5, 26,  1),
        "ki savo":               (5, 26,  1),
        "nitzavim":              (5, 29,  9),
        "vayelech":              (5, 31,  1),
        "nitzavim-vayelech":     (5, 29,  9),
        "haazinu":               (5, 32,  1),
        "vezot haberachah":      (5, 33,  1),
        "vezot habracha":        (5, 33,  1),
        "vezot habracha":        (5, 33,  1),
    }

    @classmethod
    def _lookup_parsha_start(
        cls, parsha_name: str
    ) -> Optional[Tuple[int, int, int]]:
        """Look up (book_num, chapter, verse) for a parsha name.

        Normalises the name and strips common TropeTrainer suffixes
        like ``": Shabbas"`` or ``": Weekday"``.

        :return: ``(book_num, chapter, verse)`` or ``None``.
        """
        key = " ".join(parsha_name.lower().split())
        for suffix in (
            ": shabbas", ": weekday", ": shabbat", ": holiday",
            " shabbas", " weekday", " shabbat", " holiday",
        ):
            if key.endswith(suffix):
                key = key[: -len(suffix)].strip()
                break
        result = cls._PARSHA_START_VERSES.get(key)
        if result:
            return result
        first_word = key.split()[0] if key else ""
        return cls._PARSHA_START_VERSES.get(first_word)

    def _extract_verse_metadata(
        self,
        parsha_name: str,
        tokens: List[Token],
        reading_type: str,
        cycle: int,
        holiday_option: str | None = None,
    ) -> List[dict]:
        """Derive per-token verse/chapter/aliyah metadata.

        Strategy order:

        0. **sedrot.xml** (primary) – exact aliyah (chapter, verse) start
           points read directly from the bundled ``sedrot.xml`` data file.
           When *holiday_option* is supplied the exact named sub-option is
           used (e.g. "Day 8 (Weekday)" within Pesach).
        1. Connector ``get_structured_parasha`` if available.
        2. Connector ``get_verse_ranges`` if available.
        3. Built-in parsha lookup table (starting chapter/verse only).
        4. Absolute fallback – chapter 1, verse 1, equal-length aliyot.
        """
        if not tokens:
            return []

        # Helper: build even aliyah boundaries (legacy int-keyed format)
        def _even_aliyah_boundaries(total_v: int, n_aliyot: int) -> Dict:
            names_map = {
                1: "Rishon", 2: "Sheni", 3: "Shlishi",
                4: "Revi'i", 5: "Chamishi", 6: "Shishi",
                7: "Shevi'i", 8: "Maftir",
            }
            size = max(1, total_v // n_aliyot)
            return {
                i * size: (i + 1, names_map.get(i + 1, f"Aliyah {i+1}"))
                for i in range(n_aliyot)
            }

        total_verses = max(1, sum(1 for t in tokens if t.verse_end))
        num_aliyot = 7 if reading_type.lower() == "torah" else 1

        # ── Strategy 0: sedrot.xml ─────────────────────────────────────
        # Ask the sedrot_parser for exact (chapter, verse) aliyah starts.
        # Pass holiday_option so that e.g. "Day 8 (Weekday)" within Pesach
        # is looked up directly instead of defaulting to the first option.
        # Also pass reading_type so Haftarah/Megilla get their own books.
        try:
            # For Maftir reuse the Torah option; for everything else verbatim.
            xml_rt = reading_type if reading_type.lower() != "maftir" else "Torah"
            xml_boundaries = get_aliyah_boundaries(
                parsha_name,
                cycle=cycle,
                reading_type=xml_rt,
                option_name=holiday_option,
            )
            if xml_boundaries:
                start_info = get_parsha_start(
                    parsha_name,
                    cycle=cycle,
                    reading_type=xml_rt,
                    option_name=holiday_option,
                )
                if start_info:
                    book_num, s_chapter, s_verse = start_info
                else:
                    tbl = self._lookup_parsha_start(parsha_name)
                    if tbl:
                        book_num, s_chapter, s_verse = tbl
                    else:
                        book_num, s_chapter, s_verse = 0, 1, 1

                return build_verse_metadata(
                    tokens,
                    starting_chapter=s_chapter,
                    starting_verse=s_verse,
                    aliyah_boundaries=xml_boundaries,  # (ch,v)-keyed
                    book_num=book_num,
                )
        except Exception:
            pass

        # ── Strategy 1: connector supplies structured data ──
        try:
            if hasattr(self.connector, "get_structured_parasha"):
                data = self.connector.get_structured_parasha(
                    parsha_name, cycle=cycle
                )
                if data and isinstance(data, dict):
                    start = self._lookup_parsha_start(parsha_name)
                    bk = start[0] if start else 0
                    return build_verse_metadata(
                        tokens,
                        starting_chapter=data.get("starting_chapter", 1),
                        starting_verse=data.get("starting_verse", 1),
                        aliyah_boundaries=data.get("aliyah_boundaries") or
                            _even_aliyah_boundaries(total_verses, num_aliyot),
                        book_num=bk,
                    )
        except Exception:
            pass

        # ── Strategy 2: connector supplies verse-range data ──
        try:
            if hasattr(self.connector, "get_verse_ranges"):
                ranges = self.connector.get_verse_ranges(parsha_name, cycle=cycle)
                if ranges and isinstance(ranges, dict):
                    start = self._lookup_parsha_start(parsha_name)
                    bk = start[0] if start else 0
                    return build_verse_metadata(
                        tokens,
                        starting_chapter=ranges.get("chapter", 1),
                        starting_verse=ranges.get("verse", 1),
                        aliyah_boundaries=ranges.get("aliyah_boundaries") or
                            _even_aliyah_boundaries(total_verses, num_aliyot),
                        book_num=bk,
                    )
        except Exception:
            pass

        # ── Strategy 3: built-in parsha lookup table ──
        start = self._lookup_parsha_start(parsha_name)
        if start is not None:
            book_num, s_chapter, s_verse = start
            return build_verse_metadata(
                tokens,
                starting_chapter=s_chapter,
                starting_verse=s_verse,
                aliyah_boundaries=_even_aliyah_boundaries(total_verses, num_aliyot),
                book_num=book_num,
            )

        # ── Strategy 4: absolute fallback ──
        return build_verse_metadata(
            tokens,
            starting_chapter=1,
            starting_verse=1,
            aliyah_boundaries=_even_aliyah_boundaries(total_verses, num_aliyot),
            book_num=0,
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
    # Translation and music notation  (from V5 – improved for Token in V8)
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
        # (expanded map from V8)
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
