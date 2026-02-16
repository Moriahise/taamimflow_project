"""Comprehensive reading selection dialog.

This module implements a complete dialog for selecting Torah
readings.  It reproduces the functionality of the classic TropeTrainer
application, including separate tabs for weekly/parsha readings,
holiday readings and custom user defined readings.  Additional
controls allow the user to specify the year and location (Diaspora or
Israel) and toggle the triennial cycle.

For simplicity the list of parshiot and holidays is defined within
this module.  In a production setting these would be loaded from
``sedrot.xml`` or another data source.  The custom readings tab
includes a small table with buttons to edit each aliyah.  When the
dialog is accepted the selected parsha and book are stored on the
instance for retrieval by the main window.
"""

from __future__ import annotations

from typing import List, Tuple

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QSlider,
    QGroupBox,
    QScrollArea,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDateEdit,
)


class CustomReadingEditDialog(QDialog):
    """Dialog for editing a single custom aliyah reading.

    When invoked from the custom readings table this dialog allows the
    user to specify a book, chapter and verse range.  The design is
    intentionally minimal and does not validate the values entered.
    """

    def __init__(self, reading_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reading_name = reading_name
        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle(f"Edit {self.reading_name} reading")
        self.setModal(True)
        self.setMinimumSize(400, 200)
        layout = QVBoxLayout()
        # Select book
        book_layout = QHBoxLayout()
        book_layout.addWidget(QLabel("Select book:"))
        self.book_combo = QComboBox()
        self.book_combo.addItems([
            "- Select a book -",
            "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
        ])
        book_layout.addWidget(self.book_combo)
        layout.addLayout(book_layout)
        # Starting chapter and verse
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Starting chapter:"))
        self.start_chapter_spin = QSpinBox()
        self.start_chapter_spin.setRange(1, 50)
        start_layout.addWidget(self.start_chapter_spin)
        start_layout.addWidget(QLabel(":verse"))
        self.start_verse_spin = QSpinBox()
        self.start_verse_spin.setRange(1, 100)
        start_layout.addWidget(self.start_verse_spin)
        start_layout.addStretch()
        layout.addLayout(start_layout)
        # To chapter and verse
        to_layout = QHBoxLayout()
        to_layout.addWidget(QLabel("To chapter:"))
        self.to_chapter_spin = QSpinBox()
        self.to_chapter_spin.setRange(1, 50)
        to_layout.addWidget(self.to_chapter_spin)
        to_layout.addWidget(QLabel(":verse"))
        self.to_verse_spin = QSpinBox()
        self.to_verse_spin.setRange(1, 100)
        to_layout.addWidget(self.to_verse_spin)
        to_layout.addStretch()
        layout.addLayout(to_layout)
        # Buttons
        btn_layout = QHBoxLayout()
        set_btn = QPushButton("Set")
        set_btn.clicked.connect(self.accept)
        btn_layout.addWidget(set_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)


class OpenReadingDialog(QDialog):
    """Complete Open Reading Dialog with multiple tabs.

    This dialog replicates the full reading selection interface of the
    classic TropeTrainer.  It provides three tabs: one for weekly
    readings (Shabbat and weekday), one for holidays and special
    readings, and one for custom user defined readings.  Additional
    options beneath the tabs allow the user to choose the calendar
    year, whether to compute dates for Diaspora or Israel and whether
    to apply the triennial Torah cycle.  The class sets the
    ``selected_parsha`` and ``selected_book`` attributes when the
    ``accept_torah`` or ``accept_haftarah`` methods are invoked.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.selected_parsha: str | None = None
        self.selected_book: str | None = None
        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle("Open reading")
        self.setModal(True)
        self.setMinimumSize(720, 650)
        main_layout = QVBoxLayout()
        # Main tabs
        self.main_tabs = QTabWidget()
        self.create_shabbat_tab()
        self.create_holiday_tab()
        self.create_custom_tab()
        main_layout.addWidget(self.main_tabs)
        # Calendar/year options
        year_layout = QHBoxLayout()
        year_layout.addWidget(QLabel("Get readings for year:"))
        self.year_spinbox = QSpinBox()
        self.year_spinbox.setRange(5780, 5800)
        self.year_spinbox.setValue(QDate.currentDate().year() + 3760)  # rough conversion
        self.year_spinbox.setFixedWidth(80)
        year_layout.addWidget(self.year_spinbox)
        # Display Gregorian year range for context
        greg_year = QDate.currentDate().year()
        year_layout.addWidget(QLabel(f"({greg_year}/{greg_year + 1})"))
        year_layout.addStretch()
        # Diaspora/Israel radio buttons
        self.diaspora_radio = QRadioButton("Diaspora")
        self.diaspora_radio.setChecked(True)
        year_layout.addWidget(self.diaspora_radio)
        self.israel_radio = QRadioButton("Israel")
        year_layout.addWidget(self.israel_radio)
        # Triennial cycle checkbox and cycle spinbox
        self.triennial_checkbox = QCheckBox("Use triennial Torah cycle")
        year_layout.addWidget(self.triennial_checkbox)
        cycle_label = QLabel("Cycle for year:")
        year_layout.addWidget(cycle_label)
        self.cycle_spinbox = QSpinBox()
        self.cycle_spinbox.setRange(1, 3)
        self.cycle_spinbox.setValue(1)
        self.cycle_spinbox.setFixedWidth(50)
        year_layout.addWidget(self.cycle_spinbox)
        main_layout.addLayout(year_layout)
        # Torah/Maftir/Haftarah options
        options_tabs = QTabWidget()
        # Torah options
        torah_widget = QWidget()
        torah_layout = QHBoxLayout()
        torah_group = QGroupBox("Torah options")
        torah_group_layout = QVBoxLayout()
        self.torah_shabbas_radio = QRadioButton("Shabbas")
        self.torah_shabbas_radio.setChecked(True)
        torah_group_layout.addWidget(self.torah_shabbas_radio)
        self.torah_weekday_radio = QRadioButton("Weekday")
        torah_group_layout.addWidget(self.torah_weekday_radio)
        torah_group.setLayout(torah_group_layout)
        torah_layout.addWidget(torah_group)
        torah_layout.addStretch()
        torah_widget.setLayout(torah_layout)
        # Maftir options
        maftir_widget = QWidget()
        maftir_layout = QHBoxLayout()
        maftir_group = QGroupBox("Maftir options")
        maftir_group_layout = QVBoxLayout()
        self.maftir_shekalim_radio = QRadioButton("Shabbas Shekalim")
        self.maftir_shekalim_radio.setChecked(True)
        maftir_group_layout.addWidget(self.maftir_shekalim_radio)
        maftir_group.setLayout(maftir_group_layout)
        maftir_layout.addWidget(maftir_group)
        maftir_layout.addStretch()
        maftir_widget.setLayout(maftir_layout)
        # Haftarah options
        haftarah_widget = QWidget()
        haftarah_layout = QHBoxLayout()
        haftarah_group = QGroupBox("Haftarah options")
        haftarah_group_layout = QVBoxLayout()
        self.haftarah_most_ashkenazim_radio = QRadioButton("Shabbas Shekalim: Most Ashkenazim")
        self.haftarah_most_ashkenazim_radio.setChecked(True)
        haftarah_group_layout.addWidget(self.haftarah_most_ashkenazim_radio)
        self.haftarah_sephardim_radio = QRadioButton("Shabbas Shekalim: Sephardim and Chabad")
        haftarah_group_layout.addWidget(self.haftarah_sephardim_radio)
        haftarah_group.setLayout(haftarah_group_layout)
        haftarah_layout.addWidget(haftarah_group)
        haftarah_layout.addStretch()
        haftarah_widget.setLayout(haftarah_layout)
        options_tabs.addTab(torah_widget, "Torah options")
        options_tabs.addTab(maftir_widget, "Maftir options")
        options_tabs.addTab(haftarah_widget, "Haftarah options")
        main_layout.addWidget(options_tabs)
        # Buttons at bottom
        btn_layout = QHBoxLayout()
        self.open_torah_btn = QPushButton("Open Torah Portion")
        self.open_torah_btn.clicked.connect(self.accept_torah)
        btn_layout.addWidget(self.open_torah_btn)
        self.open_haftarah_btn = QPushButton("Open Haftarah")
        self.open_haftarah_btn.clicked.connect(self.accept_haftarah)
        btn_layout.addWidget(self.open_haftarah_btn)
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        help_btn = QPushButton("Help")
        btn_layout.addWidget(help_btn)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

    # ---- Tab creation helpers ----
    def create_shabbat_tab(self) -> None:
        """Tab 1: Shabbat & Mon./Thu. readings."""
        tab = QWidget()
        layout = QVBoxLayout()
        # Calendar/date selection
        cal_layout = QHBoxLayout()
        cal_layout.addWidget(QLabel("Date:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("MMM dd, yyyy")
        self.date_edit.setFixedWidth(120)
        cal_layout.addWidget(self.date_edit)
        # A placeholder for Hebrew date display – left blank for now
        cal_layout.addWidget(QLabel(""))
        cal_layout.addWidget(QPushButton("📅"))
        cal_layout.addStretch()
        layout.addLayout(cal_layout)
        # Scroll area for parshiot
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        parshiot_layout = QGridLayout()
        parshiot_layout.setSpacing(3)
        self.parsha_button_group = QButtonGroup(self)
        parshiot = self.get_all_parshiot()
        row = 0
        col = 0
        max_cols = 6
        current_book = None
        for parsha, book in parshiot:
            if book != current_book:
                if current_book is not None:
                    row += 1
                    col = 0
                current_book = book
                book_label = QLabel(f"<b>{book}:</b>")
                parshiot_layout.addWidget(book_label, row, 0, 1, max_cols)
                row += 1
                col = 0
            radio = QRadioButton(parsha)
            # attach extra attributes so we can access later
            radio.parsha_name = parsha
            radio.book_name = book
            self.parsha_button_group.addButton(radio)
            parshiot_layout.addWidget(radio, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        scroll_widget.setLayout(parshiot_layout)
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        tab.setLayout(layout)
        self.main_tabs.addTab(tab, "Shabbat & Mon./Thu. readings")

    def create_holiday_tab(self) -> None:
        """Tab 2: Holiday & special readings."""
        tab = QWidget()
        layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        holiday_layout = QVBoxLayout()
        self.holiday_button_group = QButtonGroup(self)
        holidays = [
            "Rosh Chodesh", "Rosh Hashanah", "Fast of Gedalia", "Yom Kippur",
            "Succos", "Hoshana Rabbah", "Shemini Atzeres", "Simchas Torah",
            "Chanukah", "Tenth of Teves", "Fast of Esther", "",
            "Purim", "Pesach", "Shavuos", "Seventeenth of Tammuz", "Tisha B'Av", "",
            "Megillas Esther", "Megillas Shir HaShirim (Song of Songs)",
            "Megillas Ruth", "Megillas Eichah (Lamentations)", "Megillas Koheles (Ecclesiastes)",
        ]
        for holiday in holidays:
            if holiday == "":
                holiday_layout.addSpacing(10)
                continue
            radio = QRadioButton(holiday)
            if "Megillas" in holiday:
                # Grey out megillot as they are not implemented here
                radio.setStyleSheet("color: gray;")
            self.holiday_button_group.addButton(radio)
            holiday_layout.addWidget(radio)
        holiday_layout.addStretch()
        scroll_widget.setLayout(holiday_layout)
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        tab.setLayout(layout)
        self.main_tabs.addTab(tab, "Holiday & special readings")

    def create_custom_tab(self) -> None:
        """Tab 3: Custom readings."""
        tab = QWidget()
        layout = QVBoxLayout()
        # Custom reading name selection
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Custom reading name:"))
        self.custom_name_combo = QComboBox()
        self.custom_name_combo.setEditable(True)
        self.custom_name_combo.addItem("- Select reading or enter new name -")
        name_layout.addWidget(self.custom_name_combo)
        save_btn = QPushButton("Save")
        name_layout.addWidget(save_btn)
        delete_btn = QPushButton("Delete")
        name_layout.addWidget(delete_btn)
        layout.addLayout(name_layout)
        # Radio buttons for reading type
        type_layout = QHBoxLayout()
        self.custom_torah_radio = QRadioButton("Torah")
        self.custom_torah_radio.setChecked(True)
        type_layout.addWidget(self.custom_torah_radio)
        self.custom_haftarah_radio = QRadioButton("Haftarah")
        type_layout.addWidget(self.custom_haftarah_radio)
        self.custom_megilla_radio = QRadioButton("Megilla")
        type_layout.addWidget(self.custom_megilla_radio)
        self.custom_high_holidays_radio = QRadioButton("High Holidays Torah")
        type_layout.addWidget(self.custom_high_holidays_radio)
        type_layout.addStretch()
        layout.addLayout(type_layout)
        # Aliyot table with edit buttons
        self.custom_table = QTableWidget()
        self.custom_table.setRowCount(8)
        self.custom_table.setColumnCount(3)
        self.custom_table.setHorizontalHeaderLabels(["Reading", "", ""])
        self.custom_table.horizontalHeader().setStretchLastSection(False)
        self.custom_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.custom_table.verticalHeader().setVisible(False)
        aliyot = [
            "Kohen", "Levi", "Shlishi", "Revii", "Chamishi", "Shishi", "Shvii", "", "Maftir",
        ]
        for i, aliyah in enumerate(aliyot):
            if aliyah == "":
                # small spacer row
                self.custom_table.setRowHeight(i, 10)
                continue
            name_item = QTableWidgetItem(aliyah)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.custom_table.setItem(i, 0, name_item)
            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(lambda checked, name=aliyah: self.edit_custom_reading(name))
            self.custom_table.setCellWidget(i, 1, edit_btn)
            clear_btn = QPushButton("Clear")
            self.custom_table.setCellWidget(i, 2, clear_btn)
        layout.addWidget(self.custom_table)
        tab.setLayout(layout)
        self.main_tabs.addTab(tab, "Custom readings")

    # ---- Helper methods ----
    def edit_custom_reading(self, reading_name: str) -> None:
        """Open the edit dialog for a custom reading."""
        dialog = CustomReadingEditDialog(reading_name, self)
        dialog.exec()

    def get_all_parshiot(self) -> List[Tuple[str, str]]:
        """Return a list of (parsha, book) tuples covering the whole Torah."""
        return [
            ("Bereshit", "Bereshit/Genesis"), ("Noach", "Bereshit/Genesis"),
            ("Lech Lecha", "Bereshit/Genesis"), ("Vayera", "Bereshit/Genesis"),
            ("Chayei Sarah", "Bereshit/Genesis"), ("Toldot", "Bereshit/Genesis"),
            ("Vayetzei", "Bereshit/Genesis"), ("Vayishlach", "Bereshit/Genesis"),
            ("Vayeshev", "Bereshit/Genesis"), ("Miketz", "Bereshit/Genesis"),
            ("Vayigash", "Bereshit/Genesis"), ("Vayechi", "Bereshit/Genesis"),
            ("Shemot", "Shemot/Exodus"), ("Va'era", "Shemot/Exodus"),
            ("Bo", "Shemot/Exodus"), ("Beshalach", "Shemot/Exodus"),
            ("Yitro", "Shemot/Exodus"), ("Mishpatim", "Shemot/Exodus"),
            ("Terumah", "Shemot/Exodus"), ("Tetzaveh", "Shemot/Exodus"),
            ("Ki Tisa", "Shemot/Exodus"), ("Vayakhel", "Shemot/Exodus"),
            ("Pekudei", "Shemot/Exodus"),
            ("Vayikra", "Vayikra/Leviticus"), ("Tzav", "Vayikra/Leviticus"),
            ("Shemini", "Vayikra/Leviticus"), ("Tazria", "Vayikra/Leviticus"),
            ("Metzora", "Vayikra/Leviticus"), ("Achrei Mot", "Vayikra/Leviticus"),
            ("Kedoshim", "Vayikra/Leviticus"), ("Emor", "Vayikra/Leviticus"),
            ("Behar", "Vayikra/Leviticus"), ("Bechukotai", "Vayikra/Leviticus"),
            ("Bamidbar", "Bamidbar/Numbers"), ("Nasso", "Bamidbar/Numbers"),
            ("Beha'alotcha", "Bamidbar/Numbers"), ("Shelach", "Bamidbar/Numbers"),
            ("Korach", "Bamidbar/Numbers"), ("Chukat", "Bamidbar/Numbers"),
            ("Balak", "Bamidbar/Numbers"), ("Pinchas", "Bamidbar/Numbers"),
            ("Matot", "Bamidbar/Numbers"), ("Masei", "Bamidbar/Numbers"),
            ("Devarim", "Devarim/Deuteronomy"), ("Va'etchanan", "Devarim/Deuteronomy"),
            ("Eikev", "Devarim/Deuteronomy"), ("Re'eh", "Devarim/Deuteronomy"),
            ("Shoftim", "Devarim/Deuteronomy"), ("Ki Teitzei", "Devarim/Deuteronomy"),
            ("Ki Tavo", "Devarim/Deuteronomy"), ("Nitzavim", "Devarim/Deuteronomy"),
            ("Vayelech", "Devarim/Deuteronomy"), ("Ha'azinu", "Devarim/Deuteronomy"),
            ("V'Zot HaBerachah", "Devarim/Deuteronomy"),
        ]

    # ---- Accept handlers ----
    def accept_torah(self) -> None:
        """Accept the dialog for a Torah portion selection."""
        current_tab = self.main_tabs.currentIndex()
        if current_tab == 0:  # Shabbat readings
            selected = self.parsha_button_group.checkedButton()
            if selected:
                self.selected_parsha = selected.parsha_name
                self.selected_book = selected.book_name
                self.accept()
        elif current_tab == 1:  # Holiday readings
            selected = self.holiday_button_group.checkedButton()
            if selected:
                self.selected_parsha = selected.text()
                self.selected_book = "Holiday"
                self.accept()
        elif current_tab == 2:  # Custom readings
            name = self.custom_name_combo.currentText()
            if name and name != "- Select reading or enter new name -":
                self.selected_parsha = name
                self.selected_book = "Custom"
                self.accept()

    def accept_haftarah(self) -> None:
        """Accept the dialog for a Haftarah selection."""
        current_tab = self.main_tabs.currentIndex()
        if current_tab == 0:
            selected = self.parsha_button_group.checkedButton()
            if selected:
                self.selected_parsha = f"{selected.parsha_name} (Haftarah)"
                self.selected_book = selected.book_name
                self.accept()
        elif current_tab == 1:
            selected = self.holiday_button_group.checkedButton()
            if selected:
                self.selected_parsha = f"{selected.text()} (Haftarah)"
                self.selected_book = "Holiday"
                self.accept()