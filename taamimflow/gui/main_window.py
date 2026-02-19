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

Changes in this version (V10 – core/audio integration):

* **Preserved from V9:** TropeNotationPanel, trope_parser tokenise,
  transliteration, word_clicked handler, pronunciation change handler,
  trope info sidebar, expanded note_map, safe fallback imports.
* **New:** Safe fallback imports for ``core.cantillation``
  (``extract_tokens_with_notes``, ``TokenFull``) and ``audio``
  (``AudioEngine``, ``ConcatAudioEngine``).
* **New:** :meth:`load_parsha` uses ``extract_tokens_with_notes`` when
  available, falling back transparently to the legacy ``tokenise``.
* **New:** :meth:`_get_audio_engine` lazily constructs an
  ``AudioEngine`` or ``ConcatAudioEngine`` depending on config and
  tradition.  :meth:`_play_current` collects notes from all loaded
  tokens and plays them.  :meth:`_stop_playback` stops a running
  engine.
* **New:** Play menu and toolbar playback buttons are wired to real
  callbacks instead of placeholder actions.
* **New:** Per-word audio: clicking a word in the text widget
  triggers :meth:`_play_word_audio` if audio is enabled.
* **New:** :meth:`open_reading_dialog` passes the selected reading
  type, triennial cycle, date and diaspora setting from the dialog.
* **New:** The status bar shows the current cycle when triennial
  reading is active.
"""

from __future__ import annotations

import inspect
import logging
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
    QMessageBox,
)
from PyQt6.QtGui import QAction, QFont, QColor, QPalette
from PyQt6.QtCore import Qt, QSize, QDate, QThread, pyqtSignal, QObject

from ..config import get_app_config
from ..connectors import get_default_connector
from ..connectors.base import BaseConnector
from .text_widget import ModernTorahTextWidget, build_verse_metadata
from .open_reading_dialog import OpenReadingDialog
from .notation_widget import TropeNotationPanel
from ..utils.trope_parser import tokenise, Token, GROUPS, get_trope_group
from ..utils.sedrot_parser import (
    get_aliyah_boundaries,
    get_parsha_start,
    get_book_name_for_reading,
    get_option_type,
    get_haftarah_refs,
    get_maftir_refs,
)

logger = logging.getLogger(__name__)

# ── Optional imports with safe fallbacks ──────────────────────────────────────

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

# ── NEW: core.cantillation – full TokenFull pipeline ──────────────────────────
# Falls back gracefully to the legacy trope_parser.tokenise if not yet present.
try:
    from ..core.cantillation import extract_tokens_with_notes, TokenFull
    _HAS_CORE_CANTILLATION = True
except ImportError:
    _HAS_CORE_CANTILLATION = False
    TokenFull = None  # type: ignore[assignment,misc]

    def extract_tokens_with_notes(text, style="Sephardi"):  # type: ignore[misc]
        """Fallback: wraps the legacy tokenise function."""
        return tokenise(text)

# ── NEW: audio engines ─────────────────────────────────────────────────────────
# AudioEngine   = Milestone 10 MVP (sinus-wave synthesiser, always available).
# ConcatAudioEngine = Milestone 10.2 (concatenative synthesis, optional).
# Both are imported with safe fallbacks so the GUI starts even without pydub.
try:
    from ..audio.audio_engine import AudioEngine, Note as _AudioNote
    _HAS_AUDIO_ENGINE = True
except ImportError:
    _HAS_AUDIO_ENGINE = False
    AudioEngine = None  # type: ignore[assignment,misc]
    _AudioNote = None  # type: ignore[assignment,misc]

try:
    from ..audio.concat_audio import ConcatAudioEngine
    _HAS_CONCAT_AUDIO = True
except ImportError:
    _HAS_CONCAT_AUDIO = False
    ConcatAudioEngine = None  # type: ignore[assignment,misc]


# ── Background audio worker ────────────────────────────────────────────────────

class _AudioWorker(QObject):
    """Runs audio synthesis and playback for a fixed note list.

    Signals
    -------
    finished : emitted when playback has completed or was stopped.
    error    : emitted with an error message string on failure.
    """

    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, engine, notes: list, tempo: float, volume: float) -> None:
        super().__init__()
        self._engine = engine
        self._notes = notes
        self._tempo = tempo
        self._volume = volume
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            if self._cancelled:
                return
            seg = self._engine.synthesise(self._notes, self._tempo, self._volume)
            if not self._cancelled:
                self._engine.play(seg)
        except Exception as exc:  # pragma: no cover
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class _WordByWordWorker(QObject):
    """Plays tokens one word at a time, like TropeTrainer.

    Plays each token's notes sequentially. Emits ``word_started(index)``
    before each word so the GUI can highlight it. Playback is blocking
    per word so the loop advances naturally.

    Signals
    -------
    word_started(int) : index of the token now being played.
    finished          : emitted when all words are done or cancelled.
    error(str)        : emitted on exception.
    """

    word_started = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        engine,
        tokens: list,
        start_index: int,
        tempo: float,
        volume: float,
        note_fn,          # callable(token) → List[Note]
    ) -> None:
        super().__init__()
        self._engine = engine
        self._tokens = tokens
        self._start_index = max(0, start_index)
        self._tempo = tempo
        self._volume = volume
        self._get_notes = note_fn
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            for i in range(self._start_index, len(self._tokens)):
                if self._cancelled:
                    break
                tok = self._tokens[i]
                self.word_started.emit(i)
                notes = self._get_notes(tok)
                if notes and not self._cancelled:
                    seg = self._engine.synthesise(notes, self._tempo, self._volume)
                    if seg and not self._cancelled:
                        self._engine.play(seg)   # blocking until word finishes
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


# ──────────────────────────────────────────────────────────────────────────────
# MainWindow
# ──────────────────────────────────────────────────────────────────────────────

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
        # New: track reading-type, cycle, diaspora from open-reading dialog
        self.current_cycle: int = 0
        self.current_reading_type: str = "Torah"
        self.current_holiday_option: str | None = None
        self.current_diaspora: bool = True
        # NEW: store last loaded tokens (TokenFull or Token) for audio
        self._current_tokens: list = []
        # NEW: background audio thread bookkeeping
        self._audio_thread: QThread | None = None
        self._audio_worker = None   # _AudioWorker or _WordByWordWorker
        # NEW: word-by-word playback state (TropeTrainer behaviour)
        self._current_word_index: int = 0   # which token is playing/selected
        self._is_playing: bool = False
        # Load configuration and connector
        self._config = get_app_config()
        connector_config = self._config.get("connector", default={})
        self.connector: BaseConnector = get_default_connector(connector_config)
        # Build UI
        self.init_ui()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

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
    # Menu bar  (V5 structure preserved + play actions wired in V10)
    # ------------------------------------------------------------------

    def create_menu_bar(self) -> None:
        """Create the application menu bar."""
        menubar = self.menuBar()

        # FILE ──────────────────────────────────────────────────────────
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

        # PLAY ─────────────────────────────────────────────────────────
        # V10: actions are now connected to real playback methods
        play_menu = menubar.addMenu("&Play")

        play_action = QAction("&Play", self)
        play_action.setShortcut("Space")
        play_action.triggered.connect(self._play_current)
        play_menu.addAction(play_action)

        stop_action = QAction("&Stop", self)
        stop_action.setShortcut("Escape")
        stop_action.triggered.connect(self._stop_playback)
        play_menu.addAction(stop_action)

        play_menu.addSeparator()

        # Tradition sub-menu
        tradition_menu = play_menu.addMenu("Tradition")
        for trad in ("Sephardi", "Ashkenazi", "Yemenite"):
            act = QAction(trad, self)
            act.triggered.connect(
                lambda checked, t=trad: self._set_tradition(t)
            )
            tradition_menu.addAction(act)

        # VIEW ──────────────────────────────────────────────────────────
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
        # Colour mode sub-menu (V5 descriptive labels preserved)
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

        # HELP ──────────────────────────────────────────────────────────
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------------
    # Customisation  (from V5 – fully preserved)
    # ------------------------------------------------------------------

    def open_customize_dialog(self) -> None:
        """Open the colour customisation dialog."""
        if not _HAS_CUSTOMIZE_DIALOG:
            QMessageBox.information(
                self,
                "Customize",
                "The customize_dialog module is not available.\n"
                "Please ensure customize_dialog.py is in the gui package.",
            )
            return

        current_colors: Dict[str, str]
        if hasattr(self.torah_text, "trope_colors") and isinstance(
            self.torah_text.trope_colors, dict
        ):
            current_colors = self.torah_text.trope_colors
        else:
            current_colors = DEFAULT_TROPE_COLORS.copy()
        dialog = CustomizeColorsDialog(current_colors, self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            new_colors = dialog.get_colors()
            if hasattr(self.torah_text, "trope_colors") and isinstance(
                self.torah_text.trope_colors, dict
            ):
                for k, v in new_colors.items():
                    self.torah_text.trope_colors[k] = v
            if hasattr(self.torah_text, "update_display"):
                try:
                    self.torah_text.update_display()
                except Exception:
                    pass
            self.set_color_mode("trope_colors")
            self.statusBar().showMessage(
                "Colours updated | View: "
                + self.current_view_mode.replace("_", " ").title()
                + " | Color: Trope Colors"
            )

    # ------------------------------------------------------------------
    # Toolbar  (V5 structure with explicit tooltips preserved;
    #           V10: playback buttons connected to real callbacks)
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

        # Add view / colour widgets
        toolbar.addWidget(self.stam_btn)
        toolbar.addWidget(self.modern_btn)
        toolbar.addWidget(self.tikkun_btn)
        toolbar.addSeparator()
        toolbar.addWidget(self.no_colors_btn)
        toolbar.addWidget(self.trope_colors_btn)
        toolbar.addWidget(self.symbol_colors_btn)
        toolbar.addSeparator()

        # ── Playback controls – V10: connected to real methods ──────────
        self._act_first = QAction("⏮️", self, toolTip="First Verse")
        self._act_first.triggered.connect(self._play_first)
        toolbar.addAction(self._act_first)

        self._act_prev = QAction("◀️", self, toolTip="Previous Word")
        self._act_prev.triggered.connect(self._play_prev)
        toolbar.addAction(self._act_prev)

        self._act_play = QAction("⏯️", self, toolTip="Play / Pause (Space)")
        self._act_play.triggered.connect(self._play_current)
        toolbar.addAction(self._act_play)

        self._act_stop = QAction("⏹️", self, toolTip="Stop (Esc)")
        self._act_stop.triggered.connect(self._stop_playback)
        toolbar.addAction(self._act_stop)

        self._act_next = QAction("▶️", self, toolTip="Next Word")
        self._act_next.triggered.connect(self._play_next)
        toolbar.addAction(self._act_next)

        self._act_last = QAction("⏭️", self, toolTip="Last Verse")
        self._act_last.triggered.connect(self._play_last)
        toolbar.addAction(self._act_last)

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

        # ── Text panel ──────────────────────────────────────────────────
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

        # Modern Torah text widget (+ word_clicked signal from V8)
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

        # ── Controls panel ──────────────────────────────────────────────
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
        # V10: changing the melody also updates the audio tradition
        self.melody_combo.currentTextChanged.connect(self._on_melody_changed)
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

        # NEW V10: audio engine status indicator
        self.audio_status_label = QLabel(self._audio_status_text())
        self.audio_status_label.setWordWrap(True)
        self.audio_status_label.setStyleSheet(
            "font-size: 10px; color: #555; padding: 4px;"
        )
        controls_layout.addWidget(self.audio_status_label)

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
        """Handle word click: show notation, transliteration, and play audio.

        Updates the musical notation panel (staff + notes + syllables),
        the translation area, the sidebar trope info group, and (V10)
        triggers per-word audio playback when an audio engine is present.
        """
        # ── Transliterate the Hebrew word to Latin syllables ──
        table = get_pronunciation_table(self.current_pronunciation)
        syllables = transliterate_word(word, table)

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

        # ── V10: play audio for this word ──────────────────────────────
        self._play_word_audio(word, group_name, trope_marks)

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
    # V10: Melody combo change → update tradition for audio engine
    # ------------------------------------------------------------------

    def _on_melody_changed(self, text: str) -> None:
        """Derive the audio tradition from the selected melody string."""
        lower = text.lower()
        if "ashkenazi" in lower:
            self.current_pronunciation = "Ashkenazi"
        elif "yemenite" in lower or "yemeni" in lower:
            self.current_pronunciation = "Yemenite"
        else:
            self.current_pronunciation = "Sephardi"
        self.pronunciation_combo.setCurrentText(self.current_pronunciation)

    # ------------------------------------------------------------------
    # Reading operations  (V8 preserved + NEW reading-type dispatch)
    # ------------------------------------------------------------------

    def open_reading_dialog(self) -> None:
        """Open the complete reading selection dialog."""
        dialog = OpenReadingDialog(self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted and dialog.selected_parsha:
            cycle: int = getattr(dialog, "cycle", 0)
            if cycle == 0 and hasattr(dialog, "triennial_checkbox"):
                if dialog.triennial_checkbox.isChecked():
                    cycle = dialog.cycle_spinbox.value()

            reading_type = getattr(dialog, "reading_type", "Torah")

            selected_date: QDate = getattr(
                dialog, "selected_date", None
            ) or QDate.currentDate()
            diaspora: bool = getattr(dialog, "diaspora", True)
            if hasattr(dialog, "diaspora_radio"):
                diaspora = dialog.diaspora_radio.isChecked()

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

        V10 change: tokenisation now delegates to
        ``extract_tokens_with_notes`` when ``core.cantillation`` is
        available.  The legacy ``tokenise`` is used as fallback so
        that all existing display logic continues to work unchanged.

        :param parsha_name: The name of the parsha selected.
        :param book_name: The name of the book or category.
        :param reading_type: ``"Torah"``, ``"Haftarah"`` or ``"Maftir"``.
        :param cycle: Triennial cycle (0 = annual, 1–3).
        :param date: The date selected in the dialog.
        :param diaspora: Whether to use the Diaspora calendar.
        :param holiday_option: For holiday readings, the specific sub-option
            name chosen by the user (e.g. ``"Day 8 (Weekday)"`` for Pesach).
        """
        # Store current selection
        self.current_parsha = parsha_name
        self.current_book = book_name
        self.current_cycle = cycle
        self.current_reading_type = reading_type
        self.current_diaspora = diaspora
        self.current_holiday_option = holiday_option

        # Update titles
        if holiday_option:
            title_text = f"[{parsha_name}: {holiday_option}]"
        else:
            title_text = f"[{parsha_name}]"
        self.title_label.setText(title_text)
        self.subtitle_label.setText(
            f"{reading_type}" + (f" – Cycle {cycle}" if cycle else "")
        )

        # Determine the actual book name from sedrot.xml
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

        # ── Fetch text based on reading type ──────────────────────────
        text = ""
        try:
            rt = reading_type.lower()
            if rt == "haftarah":
                refs = get_haftarah_refs(parsha_name, option_name=holiday_option)
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
                try:
                    text = self.connector.get_parasha(parsha_name, cycle=cycle)
                except Exception:
                    if hasattr(self.connector, "get_parasha_partial"):
                        text = self.connector.get_parasha_partial(parsha_name, cycle=cycle)
                    else:
                        text = ""

        except Exception:
            text = ""

        # ── V10: Tokenise – prefer core.cantillation, fall back to legacy ──
        tokens = self._tokenise_text(text)
        self._current_tokens = tokens  # store for audio playback

        # ── Build verse/chapter/aliyah metadata ──────────────────────
        verse_metadata = self._extract_verse_metadata(
            parsha_name, tokens, reading_type, cycle, holiday_option
        )
        if verse_metadata:
            self.torah_text.set_tokens_with_metadata(tokens, verse_metadata)
        else:
            self.torah_text.set_tokens(tokens)

        # Generate translation and music notation overview (V5 method)
        self.update_translation_and_music(tokens)

        # Reset notation panel (user must click a word)
        self.notation_panel.clear()
        self.notation_panel.set_verse_text("")
        self.trope_info_label.setText("Click a word to see info")

        # Update status bar
        cycle_info = f" | Cycle: {cycle}" if cycle else ""
        diaspora_info = "Diaspora" if diaspora else "Israel"
        engine_info = "♪ " + ("core" if _HAS_CORE_CANTILLATION else "legacy")
        self.statusBar().showMessage(
            f"Loaded: {parsha_name} ({book_name}) | {len(tokens)} words | "
            f"Type: {reading_type} | {diaspora_info}{cycle_info} | "
            f"{engine_info} | "
            f"View: {self.current_view_mode.title()} | "
            f"Color: {self.current_color_mode.replace('_', ' ').title()}"
        )

    # ------------------------------------------------------------------
    # V10: Unified tokenisation helper
    # ------------------------------------------------------------------

    def _tokenise_text(self, text: str) -> list:
        """Tokenise *text* using the best available engine.

        Returns ``TokenFull`` objects when ``core.cantillation`` is
        present, otherwise falls back to legacy ``Token`` objects from
        ``trope_parser.tokenise``.  Both types expose the same
        attributes used by the GUI (``word``, ``group_name``,
        ``verse_end``, etc.).

        FIX V10 (P1): ``extract_tokens_with_notes`` erwartet ``style_name``
        nicht ``style``, und ``xml_path`` ist jetzt optional (wird intern
        via ``find_data_file`` automatisch lokalisiert).
        """
        if not text:
            return []
        if _HAS_CORE_CANTILLATION:
            try:
                # style_name ist der korrekte Parameter-Name in cantillation.py
                # xml_path ist optional – cantillation.py lokalisiert tropedef.xml
                # automatisch via find_data_file()
                style = self.current_pronunciation  # "Sephardi" / "Ashkenazi" / "Yemenite"
                return extract_tokens_with_notes(text, style_name=style)
            except Exception as exc:
                logger.warning(
                    "core.cantillation failed (%s), falling back to trope_parser", exc
                )
        return tokenise(text)

    # ------------------------------------------------------------------
    # V10: Audio engine factory
    # ------------------------------------------------------------------

    def _get_audio_engine(self):
        """Return a suitable audio engine instance or *None*.

        FIX V10.1: Die ``audio.enabled``-Config-Abfrage ist entfernt.
        Die Engine wird immer zurückgegeben wenn pydub verfügbar ist –
        ohne manuelle Config-Änderung.  Nur wenn weder AudioEngine noch
        ConcatAudioEngine importierbar sind, wird None zurückgegeben.

        Reihenfolge:
        1. ConcatAudioEngine (mit Samples falls vorhanden, sonst Sinus-Fallback)
        2. AudioEngine       (reiner Sinus-Generator)
        3. None              (pydub komplett fehlt)
        """
        tradition = self.current_pronunciation  # "Sephardi" / "Ashkenazi" / "Yemenite"

        if _HAS_CONCAT_AUDIO and ConcatAudioEngine is not None:
            try:
                return ConcatAudioEngine(tradition=tradition)
            except Exception as exc:
                logger.debug("ConcatAudioEngine unavailable: %s", exc)

        if _HAS_AUDIO_ENGINE and AudioEngine is not None:
            try:
                return AudioEngine()
            except Exception as exc:
                logger.debug("AudioEngine unavailable: %s", exc)

        return None

    # ------------------------------------------------------------------
    # V10: Set audio tradition from menu
    # ------------------------------------------------------------------

    def _set_tradition(self, tradition: str) -> None:
        """Update the current pronunciation / tradition."""
        self.current_pronunciation = tradition
        self.pronunciation_combo.setCurrentText(tradition)
        self.statusBar().showMessage(f"Tradition set to: {tradition}")

    # ------------------------------------------------------------------
    # V10.1: Note-Fallback Generator
    # ------------------------------------------------------------------

    def _get_notes_for_token(self, tok) -> list:
        """Gibt die Noten eines Tokens zurück.

        Falls keine echten Noten vorhanden sind (tropedef.xml nicht
        geladen), werden synthetische Fallback-Noten aus der
        Tropen-Gruppe berechnet. So ist immer ein Ton hörbar.

        Fallback-Pitches pro Tropen-Rang (MIDI):
          Rang 0 (Sof Pasuk)   → C5  (72)
          Rang 1 (Etnachta)    → G4  (67)
          Rang 2 (Zakef etc.)  → E4  (64)
          Rang 3 (Tipeha etc.) → D4  (62)
          Rang 4 (Munach etc.) → C4  (60)
          Unknown              → A3  (57)
        """
        # echte Noten vorhanden?
        notes = getattr(tok, 'notes', None)
        if notes:
            return list(notes)

        # Fallback: Sinus-Ton passend zur Tropen-Gruppe
        if not _HAS_AUDIO_ENGINE or _AudioNote is None:
            return []

        group_name = getattr(tok, 'group_name', 'Unknown')
        rank_map = {
            "Sof Pasuk": 72, "Etnachta": 67,
            "Segol": 64, "Zakef": 64, "Zakef Gadol": 64, "Shalshelet": 64,
            "Tipeha": 62, "Revia": 62, "Tevir": 62, "Pashta": 62,
            "Yetiv": 62, "Zarqa": 62, "Geresh": 62, "Gershayim": 62,
            "Pazer": 62, "Qarney Para": 62, "Telisha Gedola": 62,
            "Munach": 60, "Mahpakh": 60, "Merkha": 60, "Merkha Kefula": 60,
            "Darga": 60, "Qadma": 60, "Telisha Qetana": 60,
            "Yerah Ben Yomo": 60, "Ole": 60, "Iluy": 60, "Dehi": 60,
        }
        pitch = rank_map.get(group_name, 57)
        duration = 0.75 if getattr(tok, 'verse_end', False) else 0.5
        return [_AudioNote(pitch=pitch, duration=duration)]

    # ------------------------------------------------------------------
    # V10.1: Playback – TropeTrainer-Verhalten
    # ------------------------------------------------------------------

    def _play_current(self) -> None:
        """Starte Wort-für-Wort-Wiedergabe ab dem aktuell markierten Wort.

        Wie in TropeTrainer:
        - Wenn noch nicht gespielt wird: starte ab Anfang (oder letztem
          angeklickten Wort).
        - Jedes Wort wird einzeln synthetisiert und abgespielt.
        - Das aktuell spielende Wort wird im Text hervorgehoben.
        - Klick auf ein Wort während des Spielens springt zu diesem Wort.
        """
        if not self._current_tokens:
            self.statusBar().showMessage("Bitte zuerst eine Lesung öffnen.")
            return

        engine = self._get_audio_engine()
        if engine is None:
            self.statusBar().showMessage(
                "Audio nicht verfügbar – pydub installieren: pip install pydub"
            )
            return

        self._stop_playback()
        self._is_playing = True

        tempo = (self.speed_slider.value() / 100.0) * 120.0
        volume = self.volume_slider.value() / 100.0
        start = self._current_word_index

        self._audio_thread = QThread()
        self._audio_worker = _WordByWordWorker(
            engine=engine,
            tokens=self._current_tokens,
            start_index=start,
            tempo=tempo,
            volume=volume,
            note_fn=self._get_notes_for_token,
        )
        self._audio_worker.moveToThread(self._audio_thread)
        self._audio_thread.started.connect(self._audio_worker.run)
        self._audio_worker.finished.connect(self._audio_thread.quit)
        self._audio_worker.finished.connect(self._on_playback_finished)
        self._audio_worker.error.connect(self._on_playback_error)
        # Wort-Highlighting während Wiedergabe
        self._audio_worker.word_started.connect(self._on_word_playing)
        self._audio_thread.start()

        self.statusBar().showMessage(
            f"▶ Wiedergabe ab Wort {start + 1}/{len(self._current_tokens)} | "
            f"Tempo: {tempo:.0f} BPM | Lautstärke: {int(volume * 100)}%"
        )

    def _stop_playback(self) -> None:
        """Stoppe laufende Wiedergabe."""
        self._is_playing = False
        if self._audio_worker is not None:
            self._audio_worker.cancel()
        if self._audio_thread is not None and self._audio_thread.isRunning():
            self._audio_thread.quit()
            self._audio_thread.wait(2000)
        self._audio_thread = None
        self._audio_worker = None

    def _on_word_playing(self, index: int) -> None:
        """Wird aufgerufen wenn ein neues Wort beginnt zu spielen.

        Aktualisiert _current_word_index und hebt das Wort im Text hervor.
        """
        self._current_word_index = index
        # Scrollposition merken, Highlighting setzen, GUI aktualisieren
        self.torah_text.highlight_word_at_index(index)
        QApplication.processEvents()

    def _play_word_audio(
        self, word: str, group_name: str, trope_marks: list
    ) -> None:
        """Wort wurde angeklickt: Setze aktuellen Index und starte/springe.

        TropeTrainer-Verhalten:
        - Wenn Play läuft: springe zu diesem Wort (setze Index, Worker merkt es).
        - Wenn Play nicht läuft: spiele nur dieses eine Wort.
        """
        # Finde Index des Wortes in der Token-Liste
        new_index = None
        for i, tok in enumerate(self._current_tokens):
            tok_word = getattr(tok, 'word', '')
            if tok_word == word:
                new_index = i
                break

        if new_index is None:
            return  # Wort nicht in Token-Liste gefunden

        self._current_word_index = new_index

        engine = self._get_audio_engine()
        if engine is None:
            return

        if self._is_playing:
            # Play läuft bereits → Stoppe und starte neu ab diesem Wort
            # (Worker startet mit _current_word_index als Startpunkt)
            self._play_current()
            return

        # Play läuft nicht → Spiele nur dieses eine Wort
        notes = self._get_notes_for_token(self._current_tokens[new_index])
        if not notes:
            return

        tempo = (self.speed_slider.value() / 100.0) * 120.0
        volume = self.volume_slider.value() / 100.0

        self._stop_playback()
        self._audio_thread = QThread()
        self._audio_worker = _AudioWorker(engine, notes, tempo, volume)
        self._audio_worker.moveToThread(self._audio_thread)
        self._audio_thread.started.connect(self._audio_worker.run)
        self._audio_worker.finished.connect(self._audio_thread.quit)
        self._audio_worker.finished.connect(self._on_playback_finished)
        self._audio_worker.error.connect(self._on_playback_error)
        self._audio_thread.start()

    # Navigation
    def _play_first(self) -> None:
        """Springe zum ersten Wort und spiele."""
        if self._current_tokens:
            self._current_word_index = 0
            self.torah_text.highlight_word_at_index(0)
            if self._is_playing:
                self._play_current()
            else:
                self.statusBar().showMessage("Zum ersten Wort gesprungen.")

    def _play_prev(self) -> None:
        """Gehe ein Wort zurück."""
        if self._current_tokens:
            self._current_word_index = max(0, self._current_word_index - 1)
            self.torah_text.highlight_word_at_index(self._current_word_index)
            if self._is_playing:
                self._play_current()
            else:
                self.statusBar().showMessage(f"Wort {self._current_word_index + 1}/{len(self._current_tokens)}")

    def _play_next(self) -> None:
        """Gehe ein Wort vor."""
        if self._current_tokens:
            self._current_word_index = min(
                len(self._current_tokens) - 1, self._current_word_index + 1
            )
            self.torah_text.highlight_word_at_index(self._current_word_index)
            if self._is_playing:
                self._play_current()
            else:
                self.statusBar().showMessage(f"Wort {self._current_word_index + 1}/{len(self._current_tokens)}")

    def _play_last(self) -> None:
        """Springe zum letzten Wort."""
        if self._current_tokens:
            self._current_word_index = len(self._current_tokens) - 1
            self.torah_text.highlight_word_at_index(self._current_word_index)
            if self._is_playing:
                self._play_current()

    def _on_playback_finished(self) -> None:
        self._is_playing = False
        self.statusBar().showMessage("▪ Wiedergabe beendet.")

    def _on_playback_error(self, message: str) -> None:
        self._is_playing = False
        logger.error("Audio playback error: %s", message)
        self.statusBar().showMessage(f"Audio-Fehler: {message}")

    # ------------------------------------------------------------------
    # V10: Audio status helper
    # ------------------------------------------------------------------

    def _audio_status_text(self) -> str:
        """Zeige den tatsächlichen Audio-Status (pydub-Check)."""
        parts = []
        # Tokenizer
        if _HAS_CORE_CANTILLATION:
            parts.append("✅ core.cantillation")
        else:
            parts.append("⚠️ legacy tokeniser")
        # Audio Engine – prüfe ob pydub wirklich importierbar ist
        try:
            import pydub  # noqa: F401
            have_pydub = True
        except ImportError:
            have_pydub = False

        if have_pydub and _HAS_CONCAT_AUDIO:
            parts.append("✅ ConcatAudio (pydub)")
        elif have_pydub and _HAS_AUDIO_ENGINE:
            parts.append("✅ AudioEngine (pydub)")
        elif _HAS_AUDIO_ENGINE or _HAS_CONCAT_AUDIO:
            parts.append("⚠️ pydub fehlt – pip install pydub")
        else:
            parts.append("⚠️ kein Audio")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # About dialog  (V10: added)
    # ------------------------------------------------------------------

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Ta'amimFlow",
            "<b>Ta'amimFlow</b> – Torah Cantillation Trainer<br/>"
            "A modern reimplementation of TropeTrainer.<br/><br/>"
            f"<b>Engine:</b> {'core.cantillation (M9)' if _HAS_CORE_CANTILLATION else 'trope_parser (legacy)'}<br/>"
            f"<b>Audio:</b> {'ConcatAudio (M10.2)' if _HAS_CONCAT_AUDIO else 'AudioEngine MVP' if _HAS_AUDIO_ENGINE else 'unavailable'}<br/>"
            "<br/>Built with PyQt6 · Python",
        )

    # ------------------------------------------------------------------
    # Verse / Chapter / Aliyah metadata extraction  (NEW in V9)
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
    }

    @classmethod
    def _lookup_parsha_start(
        cls, parsha_name: str
    ) -> Optional[Tuple[int, int, int]]:
        """Look up (book_num, chapter, verse) for a parsha name."""
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
        tokens: List,
        reading_type: str,
        cycle: int,
        holiday_option: str | None = None,
    ) -> List[dict]:
        """Derive per-token verse/chapter/aliyah metadata.

        Strategy order:
        0. sedrot.xml (primary)
        1. Connector get_structured_parasha
        2. Connector get_verse_ranges
        3. Built-in parsha lookup table
        4. Absolute fallback
        """
        if not tokens:
            return []

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

        total_verses = max(1, sum(1 for t in tokens if getattr(t, "verse_end", False)))
        num_aliyot = 7 if reading_type.lower() == "torah" else 1

        # Strategy 0: sedrot.xml
        try:
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
                    aliyah_boundaries=xml_boundaries,
                    book_num=book_num,
                )
        except Exception:
            pass

        # Strategy 1: connector supplies structured data
        try:
            if hasattr(self.connector, "get_structured_parasha"):
                data = self.connector.get_structured_parasha(parsha_name, cycle=cycle)
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

        # Strategy 2: connector supplies verse-range data
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

        # Strategy 3: built-in parsha lookup table
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

        # Strategy 4: absolute fallback
        return build_verse_metadata(
            tokens,
            starting_chapter=1,
            starting_verse=1,
            aliyah_boundaries=_even_aliyah_boundaries(total_verses, num_aliyot),
            book_num=0,
        )

    # ------------------------------------------------------------------
    # View / colour mode
    # ------------------------------------------------------------------

    def set_view_mode(self, mode: str) -> None:
        """Set the view mode and update the display and toggle states."""
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
        """Set the colour mode and update the display and toggle states."""
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
    # File open operation  (V5 preserved + improved with real parser)
    # ------------------------------------------------------------------

    def open_text_file(self) -> None:
        """Prompt the user to open a local Tanach text file (UTF-8 encoded)."""
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

        # V10: use _tokenise_text for best available engine
        tokens = self._tokenise_text(text)
        self._current_tokens = tokens
        self.torah_text.set_tokens(tokens)

        base_name = os.path.basename(file_path)
        self.title_label.setText(f"[{base_name}]")
        self.subtitle_label.setText("")
        self.book_label.setText("Local File")
        self.translation_text.setText("")
        self.music_notation.setText("")
        self.current_parsha = base_name
        self.current_book = "Local File"

        self.update_translation_and_music(tokens)

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

        Legacy placeholder retained for backward compatibility.
        Prefer :meth:`_tokenise_text` for all new code.
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

        Accepts ``TokenFull``, legacy ``Token`` objects, or
        ``(word, trope_group, symbol)`` tuples for backward compat.
        """
        if not tokens:
            self.translation_text.setText("")
            self.music_notation.setText("")
            return

        words: List[str] = []
        groups: List[str] = []
        for t in tokens:
            if isinstance(t, tuple):
                words.append(t[0])
                groups.append(t[1])
            else:
                words.append(t.word)
                groups.append(t.group_name)

        translation_snippet = " ".join(words[:40])
        self.translation_text.setText(
            f"{translation_snippet}\n\n(Translation placeholder – network unavailable)"
        )

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
        self.music_notation.setText(" ".join(notes))

    # ------------------------------------------------------------------
    # Cleanup on close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Ensure background audio thread is stopped before closing."""
        self._stop_playback()
        super().closeEvent(event)
