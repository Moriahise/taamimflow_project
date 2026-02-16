"""Dialog for selecting a Torah reading.

The original TropeTrainer offered a sophisticated dialog with three
tabs (Shabbat, holidays and custom readings) and numerous options
pertaining to the calendar and diaspora/Israel differences.  For the
initial version of Ta'amimFlow we implement a streamlined dialog that
displays a list of parshiot loaded from ``sedrot.xml`` and allows the
user to select one.  Future versions can reintroduce additional tabs
and options by subclassing or extending this class.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
)

from ..data.sedrot import load_sedrot
from pathlib import Path


class OpenReadingDialog(QDialog):
    """Simplified reading selection dialog."""

    def __init__(self, parent=None, xml_path: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open Reading")
        self.resize(400, 500)
        self.selected_parasha: Optional[str] = None
        # Load sedrot
        try:
            path = xml_path or (Path(__file__).resolve().parent.parent.parent / "sedrot.xml")
            sedrot = load_sedrot(path)
        except Exception:
            sedrot = []
        self.parsha_names = [s.name for s in sedrot]
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        label = QLabel("Select a parasha:")
        layout.addWidget(label)
        self.list_widget = QListWidget()
        for parsha in self.parsha_names:
            item = QListWidgetItem(parsha)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("Open")
        ok_btn.clicked.connect(self._accept)
        button_layout.addWidget(ok_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _accept(self) -> None:
        current = self.list_widget.currentItem()
        if current:
            self.selected_parasha = current.text()
            self.accept()
        else:
            # ignore if nothing selected
            pass