"""Main application window for Ta'amimFlow.

This module defines the :class:`MainWindow` class which ties
together the text display widget, the reading selection dialog and
the connector used to fetch text from an external source.  The
interface has been expanded to resemble the complete TropeTrainer UI
with a menu bar, a richly featured toolbar and a split central area
containing both the text display and a panel of controls.
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
from PyQt6.QtGui import QAction, QFont, QColor, QPalette, QPixmap, QPainter
from PyQt6.QtCore import Qt, QSize

from ..config import get_app_config
from ..connectors import get_default_connector
from ..connectors.base import BaseConnector
from .text_widget import ModernTorahTextWidget
from .open_reading_dialog import OpenReadingDialog
from ..utils.trope_parser import tokenise, Token, GROUPS, get_trope_group


# ── Musical notation symbols for each trope ─────────────────────────
# A simplified mapping from trope group names to Unicode musical
# notation representations.  In a full implementation this would
# reference the tropedef.xml note sequences.  For display purposes
# we show the trope name and a stylised note pattern.

TROPE_NOTATION: Dict[str, str] = {
    "Sof Pasuk":       "𝅘𝅥𝅮 𝅘𝅥𝅮 𝅗𝅥  (Sof Pasuq – final cadence)",
    "Etnachta":        "𝅘𝅥𝅮 𝅘𝅥 𝅗𝅥  (Etnachta – half cadence)",
    "Segol":           "𝅘𝅥𝅮 𝅘𝅥𝅮 𝅘𝅥𝅮 𝅗𝅥  (Segolta)",
    "Zakef":           "𝅘𝅥 𝅘𝅥𝅮 𝅗𝅥  (Zaqef Qatan)",
    "Zakef Gadol":     "𝅘𝅥 𝅘𝅥 𝅗𝅥  (Zaqef Gadol)",
    "Shalshelet":      "𝅘𝅥𝅮𝅘𝅥𝅮𝅘𝅥𝅮 𝅘𝅥𝅮𝅘𝅥𝅮𝅘𝅥𝅮 𝅘𝅥𝅮𝅘𝅥𝅮𝅘𝅥𝅮 𝅗𝅥  (Shalshelet – chain)",
    "Tipeha":          "𝅘𝅥𝅮 𝅘𝅥  (Tipeha / Tarcha)",
    "Revia":           "𝅘𝅥 𝅗𝅥  (Revia)",
    "Tevir":           "𝅘𝅥𝅮 𝅘𝅥 𝅘𝅥𝅮  (Tevir)",
    "Pashta":          "𝅘𝅥𝅮 𝅘𝅥  (Pashta)",
    "Yetiv":           "𝅘𝅥 𝅘𝅥𝅮  (Yetiv)",
    "Zarqa":           "𝅘𝅥𝅮 𝅘𝅥𝅮 𝅘𝅥  (Zarqa)",
    "Geresh":          "𝅘𝅥𝅮  (Geresh)",
    "Gershayim":       "𝅘𝅥𝅮 𝅘𝅥𝅮  (Gershayim)",
    "Pazer":           "𝅘𝅥𝅮 𝅘𝅥𝅮 𝅘𝅥𝅮 𝅘𝅥  (Pazer)",
    "Qarney Para":     "𝅘𝅥𝅮 𝅘𝅥𝅮 𝅘𝅥 𝅘𝅥  (Qarney Para)",
    "Telisha Gedola":  "𝅘𝅥𝅮 𝅘𝅥  (Telisha Gedola)",
    "Munach":          "𝅘𝅥  (Munach)",
    "Mahpakh":         "𝅘𝅥𝅮 𝅘𝅥  (Mahpakh)",
    "Merkha":          "𝅘𝅥  (Merkha)",
    "Merkha Kefula":   "𝅘𝅥 𝅘𝅥  (Merkha Kefula)",
    "Darga":           "𝅘𝅥𝅮 𝅘𝅥𝅮 𝅘𝅥  (Darga)",
    "Qadma":           "𝅘𝅥𝅮  (Qadma / Azla)",
    "Telisha Qetana":  "𝅘𝅥𝅮  (Telisha Qetana)",
    "Yerah Ben Yomo":  "𝅘𝅥 𝅘𝅥 𝅘𝅥  (Yerah Ben Yomo / Galgal)",
    "Ole":             "𝅘𝅥𝅮  (Ole)",
    "Iluy":            "𝅘𝅥𝅮  (Iluy)",
    "Dehi":            "𝅘𝅥  (Dehi)",
    "Zinor":           "𝅘𝅥𝅮 𝅘𝅥𝅮  (Zinor)",
    "Unknown":         "—",
}


class MainWindow(QMainWindow):
    """Main window for the Ta'amimFlow application."""

    def __init__(self) -> None:
        super().__init__()
        self.current_parsha: str | None = None
        self.current_book: str | None = None
        self.current_view_mode: str = "modern"
        self.current_color_mode: str = "trope_colors"
        config = get_app_config()
        connector_config = config.get("connector", default={})
        self.connector: BaseConnector = get_default_connector(connector_config)
        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle("TropeTrainer 2.0 - Torah Reading Trainer")
        self.setGeometry(100, 100, 1200, 800)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        self.setPalette(palette)
        self.create_menu_bar()
        self.create_modern_toolbar()
        self.create_central_widget()
        self.statusBar().showMessage("Ready - Select File → Open Reading to begin")

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------
    def create_menu_bar(self) -> None:
        menubar = self.menuBar()
        # FILE
        file_menu = menubar.addMenu("&File")
        open_action = QAction("&Open Reading...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_reading_dialog)
        file_menu.addAction(open_action)
        open_file_action = QAction("O&pen Text File...", self)
        open_file_action.setShortcut("Ctrl+T")
        open_file_action.triggered.connect(self.open_text_file)
        file_menu.addAction(open_file_action)
        file_menu.addSeparator()
        customize_action = QAction("&Customize...", self)
        file_menu.addAction(customize_action)
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        # PLAY
        play_menu = menubar.addMenu("&Play")
        play_action = QAction("&Play", self)
        play_action.setShortcut("Space")
        play_menu.addAction(play_action)
        # VIEW
        view_menu = menubar.addMenu("&View")
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
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction(QAction("📂", self, toolTip="Open", triggered=self.open_reading_dialog))
        toolbar.addAction(QAction("💾", self, toolTip="Save"))
        toolbar.addAction(QAction("🖨️", self, toolTip="Print"))
        toolbar.addSeparator()
        # View mode buttons
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
        # Colour mode buttons
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
        toolbar.addWidget(self.stam_btn)
        toolbar.addWidget(self.modern_btn)
        toolbar.addWidget(self.tikkun_btn)
        toolbar.addSeparator()
        toolbar.addWidget(self.no_colors_btn)
        toolbar.addWidget(self.trope_colors_btn)
        toolbar.addWidget(self.symbol_colors_btn)
        toolbar.addSeparator()
        # Playback controls
        toolbar.addAction(QAction("⏮️", self, toolTip="First"))
        toolbar.addAction(QAction("◀️", self, toolTip="Previous"))
        toolbar.addAction(QAction("⏯️", self, toolTip="Play/Pause"))
        toolbar.addAction(QAction("▶️", self, toolTip="Next"))
        toolbar.addAction(QAction("⏭️", self, toolTip="Last"))
        toolbar.addSeparator()
        toolbar.addAction(QAction("🔍", self, toolTip="Search"))
        toolbar.addAction(QAction("⚙️", self, toolTip="Settings"))

    # ------------------------------------------------------------------
    # Central widget
    # ------------------------------------------------------------------
    def create_central_widget(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()

        # ── Text panel ──
        text_panel = QWidget()
        text_layout = QVBoxLayout()

        # Title labels
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

        # Torah text widget
        self.torah_text = ModernTorahTextWidget()
        self.torah_text.setPlaceholderText(
            "Select File → Open Reading to choose a Torah portion..."
        )
        # Connect word click signal to update notation panels
        self.torah_text.word_clicked.connect(self._on_word_clicked)
        text_layout.addWidget(self.torah_text)

        # Translation panel
        translation_label = QLabel("Translation:")
        translation_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        text_layout.addWidget(translation_label)
        self.translation_text = QLabel(
            "(Translation placeholder – network unavailable)"
        )
        self.translation_text.setWordWrap(True)
        self.translation_text.setStyleSheet(
            "padding: 10px; background-color: white; border: 1px solid #ccc;"
            " font-size: 14px; direction: rtl;"
        )
        self.translation_text.setMinimumHeight(60)
        self.translation_text.setTextFormat(Qt.TextFormat.RichText)
        text_layout.addWidget(self.translation_text)

        # Musical notation panel
        music_label = QLabel("Musical Notation:")
        music_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        text_layout.addWidget(music_label)
        self.music_notation = QLabel("Click a word to see its trope notation")
        self.music_notation.setStyleSheet(
            "padding: 10px; background-color: white; border: 1px solid #ccc;"
            " font-size: 16px;"
        )
        self.music_notation.setMinimumHeight(60)
        text_layout.addWidget(self.music_notation)

        text_panel.setLayout(text_layout)

        # ── Controls panel ──
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

        # Pronunciation
        pronunciation_group = QGroupBox("Pronunciation/Accent")
        pronunciation_layout = QVBoxLayout()
        self.pronunciation_combo = QComboBox()
        self.pronunciation_combo.addItems(["Sephardi", "Ashkenazi", "Yemenite"])
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

        # Trope info label (shows info about selected word)
        self.trope_info_group = QGroupBox("Selected Trope")
        trope_info_layout = QVBoxLayout()
        self.trope_info_label = QLabel("Click a word to see info")
        self.trope_info_label.setWordWrap(True)
        self.trope_info_label.setStyleSheet("font-size: 12px; padding: 4px;")
        trope_info_layout.addWidget(self.trope_info_label)
        self.trope_info_group.setLayout(trope_info_layout)
        controls_layout.addWidget(self.trope_info_group)

        controls_layout.addStretch()
        controls_panel.setLayout(controls_layout)
        controls_panel.setMaximumWidth(250)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(text_panel)
        splitter.addWidget(controls_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)

    # ------------------------------------------------------------------
    # Word click handler
    # ------------------------------------------------------------------
    def _on_word_clicked(self, word: str, group_name: str, trope_marks: list) -> None:
        """Handle a word click from the text widget.

        Updates the musical notation panel and trope info sidebar.
        """
        # Musical notation
        notation = TROPE_NOTATION.get(group_name, "—")
        marks_str = ", ".join(trope_marks) if trope_marks else "none"
        self.music_notation.setText(f"{notation}")

        # Translation area: show the word and its trope info
        group = get_trope_group(group_name)
        color_swatch = (
            f'<span style="background-color: {group.color}; '
            f'padding: 2px 8px; border: 1px solid #333;">&nbsp;</span>'
        )
        self.translation_text.setText(
            f'<div style="direction: rtl; text-align: right;">'
            f'<b style="font-size: 18px;">{word}</b><br/>'
            f'Trope: {group_name} {color_swatch}<br/>'
            f'Marks: {marks_str}</div>'
        )

        # Sidebar info
        self.trope_info_label.setText(
            f"Word: {word}\n"
            f"Group: {group_name}\n"
            f"Marks: {marks_str}\n"
            f"Color: {group.color}\n"
            f"Rank: {group.rank}"
        )

        # Update status bar
        self.statusBar().showMessage(
            f"Selected: {group_name} | Marks: {marks_str}"
        )

    # ------------------------------------------------------------------
    # Reading operations
    # ------------------------------------------------------------------
    def open_reading_dialog(self) -> None:
        dialog = OpenReadingDialog(self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted and dialog.selected_parsha:
            self.load_parsha(dialog.selected_parsha, dialog.selected_book)

    def load_parsha(self, parsha_name: str, book_name: str) -> None:
        """Load and display a parsha using the configured connector.

        This method now loads the **full** reading (all aliyot), not
        just the first one.  It uses the real trope parser to produce
        properly coloured tokens.
        """
        self.current_parsha = parsha_name
        self.current_book = book_name
        # Update titles
        self.title_label.setText(f"[{parsha_name}]")
        self.subtitle_label.setText("")
        self.book_label.setText(book_name)

        # ── Fetch FULL text (all aliyot) ──
        try:
            # Always use get_parasha for the full reading
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

        # Reset notation panels
        self.translation_text.setText(
            "(Translation placeholder – network unavailable)"
        )
        self.music_notation.setText("Click a word to see its trope notation")
        self.trope_info_label.setText("Click a word to see info")

        # Status bar
        word_count = len(tokens)
        self.statusBar().showMessage(
            f"Loaded: {parsha_name} ({book_name}) | "
            f"{word_count} words | "
            f"View: {self.current_view_mode.title()} | "
            f"Color: {self.current_color_mode.replace('_', ' ').title()}"
        )

    def set_view_mode(self, mode: str) -> None:
        self.current_view_mode = mode
        self.torah_text.set_view_mode(mode)
        self.modern_btn.setChecked(mode == "modern")
        self.stam_btn.setChecked(mode == "stam")
        self.tikkun_btn.setChecked(mode == "tikkun")
        self.statusBar().showMessage(
            f"View: {mode.replace('_', ' ').title()} | "
            f"Color: {self.current_color_mode.replace('_', ' ').title()}"
        )

    def set_color_mode(self, mode: str) -> None:
        self.current_color_mode = mode
        self.torah_text.set_color_mode(mode)
        self.no_colors_btn.setChecked(mode == "no_colors")
        self.trope_colors_btn.setChecked(mode == "trope_colors")
        self.symbol_colors_btn.setChecked(mode == "symbol_colors")
        self.statusBar().showMessage(
            f"View: {self.current_view_mode.replace('_', ' ').title()} | "
            f"Color: {mode.replace('_', ' ').title()}"
        )

    # ------------------------------------------------------------------
    # File open operation
    # ------------------------------------------------------------------
    def open_text_file(self) -> None:
        """Open a local Tanach text file (UTF-8 encoded)."""
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
            return

        # Tokenise with the real parser
        tokens = tokenise(text)
        self.torah_text.set_tokens(tokens)

        import os
        base_name = os.path.basename(file_path)
        self.title_label.setText(f"[{base_name}]")
        self.subtitle_label.setText("")
        self.book_label.setText("Local File")
        self.translation_text.setText("")
        self.music_notation.setText("Click a word to see its trope notation")
        self.current_parsha = base_name
        self.current_book = "Local File"
        self.statusBar().showMessage(
            f"Loaded local file: {base_name} | "
            f"{len(tokens)} words | "
            f"View: {self.current_view_mode.title()} | "
            f"Color: {self.current_color_mode.replace('_', ' ').title()}"
        )
