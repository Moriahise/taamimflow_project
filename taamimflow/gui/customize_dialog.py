"""Color customisation dialog for Ta'amimFlow.

This module provides a simple dialog allowing the user to adjust
the highlight colours used for each trope group.  It mirrors the
functionality of the ``CustomizeColorsDialog`` from the original
TropeTrainer example supplied by the user.  Colours are selected
via drop‑down lists showing a swatch and colour name.  The dialog
returns a dictionary mapping trope group names to the chosen
hexadecimal colour strings when accepted.

The list of trope groups presented here covers the principal
categories used in the text display.  Additional groups defined
internally by :class:`ModernTorahTextWidget` will fall back to
their default colours if not present in the returned mapping.

"""

from __future__ import annotations

from typing import Dict

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QCheckBox,
)
from PyQt6.QtGui import QColor


# A default set of colours for the primary trope groups.  These
# defaults are deliberately simple; they can be overridden by the
# application when constructing the dialog.  The groups listed here
# correspond to those exposed in the customise UI; any missing
# groups will retain their existing colours.
DEFAULT_TROPE_COLORS: Dict[str, str] = {
    "Sof Pasuk": "#00FFFF",      # Aqua/Cyan
    "Zakef Katon": "#FFFF00",    # Yellow
    "Tevir": "#FFFFFF",          # White
    "Geresh": "#FFFFFF",         # White
    "Telisha Gedola": "#FFFFFF", # White
    "Pazer": "#FFFFFF",          # White
    "Karne Fara": "#FFFFFF",     # White
    "End of Book": "#808080",    # Gray
    "Etnachta": "#FF00FF",       # Fuchsia/Magenta
    "Revia": "#FFFFFF",          # White
    "Segol": "#FFFFFF",          # White
    "Gershayim": "#FFFFFF",      # White
    "Zakef Gadol": "#FFFFFF",    # White
    "Shalshelet": "#FFFFFF",     # White
    "End of Aliyah": "#0000FF",  # Blue
}


class CustomizeColorsDialog(QDialog):
    """Dialog allowing the user to pick highlight colours for each trope.

    The dialog presents a two‑column grid of drop‑down lists.  Each
    list contains a set of colour names accompanied by a swatch to
    aid selection.  The initial selection is populated from the
    ``current_colors`` mapping passed to the constructor.  When the
    user clicks OK, ``get_colors()`` can be used to retrieve the
    updated mapping.

    :param current_colors: Mapping of trope names to hex colour
        strings.  Missing entries will fall back to
        ``DEFAULT_TROPE_COLORS``.
    :param parent: Parent widget for the dialog.
    """

    def __init__(self, current_colors: Dict[str, str] | None = None, parent=None) -> None:
        super().__init__(parent)
        # Start with defaults and overlay any provided colours
        self.colors: Dict[str, str] = DEFAULT_TROPE_COLORS.copy()
        if current_colors:
            for k, v in current_colors.items():
                if k in self.colors:
                    self.colors[k] = v
        self.color_combos: Dict[str, QComboBox] = {}
        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle("Customize Colours")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        main_layout = QVBoxLayout()
        # --- Colour selection ---
        colors_group = QGroupBox("Select highlight colours for trope groups")
        colors_layout = QGridLayout()
        # Define groups in two columns for nicer layout
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
        # Colour options: show a selection of common colours.  The
        # display string begins with a box character to preview the colour.
        colour_options = {
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
        }
        # Helper to populate a combo for a given trope
        def create_combo(trope_name: str) -> QComboBox:
            combo = QComboBox()
            for name, hex_code in colour_options.items():
                combo.addItem(f"■ {name}", hex_code)
            # Set the current selection to the existing colour
            current = self.colors.get(trope_name, DEFAULT_TROPE_COLORS.get(trope_name, "#FFFFFF"))
            for i in range(combo.count()):
                if combo.itemData(i) == current:
                    combo.setCurrentIndex(i)
                    break
            # Update the background of the combo itself
            self.update_combo_style(combo)
            combo.currentIndexChanged.connect(lambda: self.update_combo_style(combo))
            return combo
        # Populate the grid
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
        # --- Elision / melody smoothing ---
        melody_group = QGroupBox("Melody smoothing")
        melody_layout = QVBoxLayout()
        self.elision_checkbox = QCheckBox("Enable Elision")
        melody_layout.addWidget(self.elision_checkbox)
        elision_text = QLabel(
            "Elision omits the upbeat note of a trope when the following word is accented on its first syllable.\n"
            "When enabled, the omitted note is appended to the previous word if it has a servant trope."
        )
        elision_text.setWordWrap(True)
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

    def update_combo_style(self, combo: QComboBox) -> None:
        """Apply the selected colour to the combo's background."""
        colour = combo.currentData()
        # Set both background and text colour for readability
        combo.setStyleSheet(f"QComboBox {{ background-color: {colour}; color: black; }}")

    def get_colors(self) -> Dict[str, str]:
        """Return the selected colours as a mapping.

        Only groups present in the UI are returned.  Missing
        groups should retain their previous values.
        """
        result: Dict[str, str] = {}
        for trope, combo in self.color_combos.items():
            result[trope] = combo.currentData()
        return result