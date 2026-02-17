"""Colour customisation dialog for Ta'amimFlow.

This module provides a dialog allowing the user to adjust the
highlight colours used for each trope group.  It mirrors the
functionality of the ``CustomizeColorsDialog`` from the original
TropeTrainer.  Colours are selected via drop‑down lists showing a
swatch and colour name.  The dialog returns a dictionary mapping
trope group names to the chosen hexadecimal colour strings when
accepted.

The list of trope groups presented here covers the principal
categories used in the text display.  Additional groups defined
internally by :class:`ModernTorahTextWidget` will fall back to their
default colours if not present in the returned mapping.
"""

from __future__ import annotations

from typing import Dict

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

# Default colours for the primary trope groups.  These match the
# colour scheme of the original TropeTrainer where possible.
DEFAULT_TROPE_COLORS: Dict[str, str] = {
    "Sof Pasuk": "#00FFFF",        # Aqua/Cyan
    "Zakef Katon": "#FFFF00",      # Yellow
    "Tevir": "#FFFFFF",            # White
    "Geresh": "#FFFFFF",           # White
    "Telisha Gedola": "#FFFFFF",   # White
    "Pazer": "#FFFFFF",            # White
    "Karne Fara": "#FFFFFF",       # White
    "End of Book": "#808080",      # Gray
    "Etnachta": "#FF00FF",         # Fuchsia/Magenta
    "Revia": "#FFFFFF",            # White
    "Segol": "#FFFFFF",            # White
    "Gershayim": "#FFFFFF",        # White
    "Zakef Gadol": "#FFFFFF",      # White
    "Shalshelet": "#FFFFFF",       # White
    "End of Aliyah": "#0000FF",    # Blue
}

# Colour palette offered to the user.  A moderate set of easily
# distinguishable colours.
_COLOUR_OPTIONS: Dict[str, str] = {
    "Aqua": "#00FFFF",
    "Yellow": "#FFFF00",
    "White": "#FFFFFF",
    "Fuchsia": "#FF00FF",
    "Blue": "#0000FF",
    "Gray": "#808080",
    "Green": "#00FF00",
    "Red": "#FF0000",
    "Orange": "#FFA500",
    "Pink": "#FFC0CB",
    "Purple": "#800080",
    "Lime": "#BFFF00",
    "Gold": "#FFD700",
    "Silver": "#C0C0C0",
}


def _colour_swatch(hex_code: str, size: int = 12) -> QIcon:
    """Create a small square icon filled with the given colour."""
    px = QPixmap(size, size)
    px.fill(QColor(hex_code))
    return QIcon(px)


class CustomizeColorsDialog(QDialog):
    """Dialog allowing the user to pick highlight colours for each trope.

    The dialog presents a two‑column grid of drop‑down lists.  Each
    list contains a set of colour names accompanied by a swatch to aid
    selection.  The initial selection is populated from the
    ``current_colors`` mapping passed to the constructor.  When the
    user clicks OK, :meth:`get_colors` returns the updated mapping.

    :param current_colors: Mapping of trope names to hex colour strings.
    :param parent: Parent widget for the dialog.
    """

    def __init__(
        self,
        current_colors: Dict[str, str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.colors: Dict[str, str] = DEFAULT_TROPE_COLORS.copy()
        if current_colors:
            for k, v in current_colors.items():
                if k in self.colors:
                    self.colors[k] = v
        self.color_combos: Dict[str, QComboBox] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("Customize Colours")
        self.setModal(True)
        self.setMinimumSize(540, 440)
        main_layout = QVBoxLayout()

        # --- Colour selection ---
        colors_group = QGroupBox("Select highlight colours for trope groups")
        colors_layout = QGridLayout()
        colors_layout.setSpacing(6)

        left_column = [
            "Sof Pasuk",
            "Zakef Katon",
            "Tevir",
            "Geresh",
            "Telisha Gedola",
            "Pazer",
            "Karne Fara",
            "End of Book",
        ]
        right_column = [
            "Etnachta",
            "Revia",
            "Segol",
            "Gershayim",
            "Zakef Gadol",
            "Shalshelet",
            "End of Aliyah",
        ]

        def create_combo(trope_name: str) -> QComboBox:
            combo = QComboBox()
            for name, hex_code in _COLOUR_OPTIONS.items():
                combo.addItem(_colour_swatch(hex_code), f"  {name}", hex_code)
            current = self.colors.get(
                trope_name, DEFAULT_TROPE_COLORS.get(trope_name, "#FFFFFF")
            )
            for i in range(combo.count()):
                if combo.itemData(i) == current:
                    combo.setCurrentIndex(i)
                    break
            self._update_combo_style(combo)
            combo.currentIndexChanged.connect(lambda: self._update_combo_style(combo))
            return combo

        for row, trope in enumerate(left_column):
            label = QLabel(trope + ":")
            colors_layout.addWidget(label, row, 0)
            combo = create_combo(trope)
            self.color_combos[trope] = combo
            colors_layout.addWidget(combo, row, 1)

        for row, trope in enumerate(right_column):
            label = QLabel(trope + ":")
            colors_layout.addWidget(label, row, 2)
            combo = create_combo(trope)
            self.color_combos[trope] = combo
            colors_layout.addWidget(combo, row, 3)

        colors_group.setLayout(colors_layout)
        main_layout.addWidget(colors_group)

        # --- Melody smoothing (elision) ---
        melody_group = QGroupBox("Melody smoothing")
        melody_layout = QVBoxLayout()
        self.elision_checkbox = QCheckBox("Enable Elision")
        melody_layout.addWidget(self.elision_checkbox)
        elision_text = QLabel(
            "Elision omits the upbeat note of a trope when the following "
            "word is accented on its first syllable.\nWhen enabled, the "
            "omitted note is appended to the previous word if it has a "
            "servant trope."
        )
        elision_text.setWordWrap(True)
        elision_text.setStyleSheet("color: #555;")
        melody_layout.addWidget(elision_text)
        melody_group.setLayout(melody_layout)
        main_layout.addWidget(melody_group)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

    def _update_combo_style(self, combo: QComboBox) -> None:
        """Apply the selected colour to the combo's background."""
        colour = combo.currentData()
        if colour:
            # Pick contrasting text colour for readability
            c = QColor(colour)
            luminance = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
            text_color = "black" if luminance > 128 else "white"
            combo.setStyleSheet(
                f"QComboBox {{ background-color: {colour}; color: {text_color}; }}"
            )

    def get_colors(self) -> Dict[str, str]:
        """Return the selected colours as a mapping.

        Only groups present in the UI are returned.  Missing groups
        should retain their previous values.
        """
        result: Dict[str, str] = {}
        for trope, combo in self.color_combos.items():
            result[trope] = combo.currentData()
        return result
