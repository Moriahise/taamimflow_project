# Ta'amimFlow — Installation & Setup

**Milestone 8: Offline Tanach Connector**  
Stand: 2026-02-17

---

## Systemanforderungen

- **Python**: 3.9 oder höher
- **Betriebssystem**: Windows, macOS, Linux
- **Festplatte**: ~100 MB für Programm + TXT-Dateien
- **Internet**: Nur für `pip install` und optionalen Sefaria-Modus

---

## Schnellinstallation (5 Minuten)

```bash
# 1. Repository klonen
git clone https://github.com/Moriahise/taamimflow_project.git
cd taamimflow_project

# 2. Dependencies installieren
pip install -r requirements.txt

# 3. Tanach-Daten herunterladen (siehe unten)
mkdir tanach_data
# → TXT-Dateien von tanach.us in diesen Ordner legen

# 4. Starten
python -m taamimflow.main
```

---

## Schritt-für-Schritt-Anleitung

### 1. Python installieren

**Windows:**
- Download von https://www.python.org/downloads/
- Bei Installation: "Add Python to PATH" anhaken!

**macOS:**
```bash
brew install python3
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip
```

**Version prüfen:**
```bash
python --version  # sollte 3.9+ sein
```

---

### 2. Repository einrichten

```bash
# Klonen
git clone https://github.com/Moriahise/taamimflow_project.git
cd taamimflow_project

# Oder: ZIP herunterladen und entpacken
```

---

### 3. Virtual Environment (empfohlen)

```bash
# Virtual Environment erstellen
python -m venv venv

# Aktivieren
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Deaktivieren (später):
deactivate
```

---

### 4. Dependencies installieren

```bash
pip install -r requirements.txt
```

**requirements.txt enthält:**
```
PyQt6>=6.4.0
PyQt6-WebEngine>=6.4.0
requests>=2.28.0
lxml>=4.9.0
# pyicu optional — nur für fortgeschrittene Transliteration
```

**Problem: PyQt6 Installation schlägt fehl?**
```bash
# Alternative: System-Packages (Linux)
sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine

# macOS:
brew install pyqt@6
```

---

### 5. Tanach-Daten herunterladen

#### Option A: Manueller Download (empfohlen)

1. Erstelle Ordner `tanach_data/` im Projektroot:
   ```bash
   mkdir tanach_data
   ```

2. Gehe zu **https://www.tanach.us/Server.aspx**

3. Für jedes Buch:
   - Klicke auf den Buchnamen
   - Wähle **"Tanach with Ta'amei Hamikra"** (empfohlen)
   - Speichere die `.txt`-Datei in `tanach_data/`

**Empfohlene Dateien für den Start:**
- Torah (5 Bücher): Genesis, Exodus, Leviticus, Numbers, Deuteronomy
- Haftarot: Isaiah, Jeremiah, Ezekiel, Hosea, Joel, Amos, etc.
- Megillot: Ruth, Esther, Song of Songs, Lamentations, Ecclesiastes

**Dateinamen-Beispiele:**
```
tanach_data/Genesis_Tanach_with_Ta_amei_Hamikra.txt
tanach_data/Exodus_Tanach_with_Ta_amei_Hamikra.txt
...
```

#### Option B: Beispieldateien (für schnellen Test)

Die drei mitgelieferten Beispieldateien sind bereits funktionsfähig:
```
tanach_data/Habakkuk_Tanach_with_Ta_amei_Hamikra.txt
tanach_data/Ruth_Miqra_according_to_the_Masorah.txt
tanach_data/Ecclesiastes_Tanach_with_Text_Only.txt
```

---

### 6. Konfiguration anpassen (optional)

Standardmäßig ist der Offline-Modus aktiviert.

**config_default_settings.json:**
```json
{
  "connector": {
    "type": "local",
    "tanach_dir": "tanach_data",
    "preferred_format": "cantillation"
  }
}
```

**Für Sefaria (Online-Modus):**
```json
{
  "connector": {
    "type": "sefaria"
  }
}
```

Siehe **CONFIG_GUIDE.md** für alle Optionen.

---

### 7. Erste Schritte

```bash
# Programm starten
python -m taamimflow.main

# Tests ausführen (optional)
python tests/test_local_tanach.py

# Verfügbare Bücher anzeigen
python -c "
from taamimflow.connectors.local_tanach import LocalTanachConnector
conn = LocalTanachConnector(tanach_dir='tanach_data')
print('Verfügbare Bücher:', conn.list_available_books())
"
```

---

## Fehlerbehebung

### Problem: "ModuleNotFoundError: No module named 'PyQt6'"

**Lösung:**
```bash
pip install PyQt6 PyQt6-WebEngine
```

---

### Problem: "FileNotFoundError: tanach_data not found"

**Lösung:**
```bash
# Ordner erstellen
mkdir tanach_data

# Mindestens eine TXT-Datei hineinlegen
# Siehe Schritt 5: Tanach-Daten herunterladen
```

---

### Problem: "No books indexed" oder leere Liste

**Ursachen:**
1. `tanach_data/` Ordner ist leer
2. Dateien haben falsches Format (keine tanach.us TXT-Dateien)
3. Falscher Pfad in config

**Lösung:**
```bash
# Prüfe Ordnerinhalt
ls -la tanach_data/

# Prüfe erste Zeile einer Datei (sollte Buchname sein)
head -1 tanach_data/*.txt

# Debug-Modus aktivieren
# In config_default_settings.json:
{
  "advanced": {
    "debug_mode": true,
    "log_level": "DEBUG"
  }
}
```

---

### Problem: "Hebrew text not displaying correctly"

**Lösung:**
```bash
# Windows: Installiere SBL Hebrew Font
# Download von: https://www.sbl-site.org/educational/biblicalfonts.aspx

# macOS/Linux: Installiere Ezra SIL
sudo apt install fonts-sil-ezra  # Linux
brew install font-ezra-sil       # macOS
```

---

### Problem: UI friert beim Laden ein (Sefaria-Modus)

**Ursache:** Synchrone Netzwerk-Anfragen blockieren UI-Thread  
**Lösung:** Wechsel zu Offline-Modus:

```json
{
  "connector": { "type": "local" }
}
```

Oder warte auf Milestone 6 (Async Loading).

---

## Entwickler-Setup

### Code-Struktur
```
taamimflow/
├── config/           # Konfiguration
├── connectors/       # Text-Quellen (Sefaria, Local)
│   ├── base.py
│   ├── sefaria.py
│   └── local_tanach.py    ← NEU in Milestone 8
├── data/             # XML-Parser (sedrot, tropedef)
├── gui/              # PyQt6 UI
├── utils/            # Helper (paths, refs, trope_parser)
└── main.py           # Entry point

tanach_data/          # Lokale TXT-Dateien
tests/                # Test-Suite
```

### Tests ausführen
```bash
# Alle Tests
python -m pytest tests/

# Nur LocalTanachConnector
python tests/test_local_tanach.py

# Mit Coverage
pip install pytest-cov
pytest --cov=taamimflow tests/
```

### Pre-Commit Hooks (optional)
```bash
pip install pre-commit
pre-commit install

# Hooks in .pre-commit-config.yaml:
# - black (Formatting)
# - flake8 (Linting)
# - mypy (Type checking)
```

---

## Performance-Tipps

### Große Datenmengen (50+ Bücher)

**Empfehlung:** Cache aktivieren
```json
{
  "advanced": {
    "cache_enabled": true
  }
}
```

### Langsame Festplatte (HDD)

**Empfehlung:** Nur benötigte Bücher im `tanach_data/` Ordner

### Mehrere Formate pro Buch

**Beispiel:**
```
tanach_data/Genesis_Ta_amei_Hamikra.txt
tanach_data/Genesis_Text_Only.txt
```

**Config:**
```json
{
  "connector": {
    "preferred_format": "cantillation"  # Ta_amei wird bevorzugt
  }
}
```

---

## Upgrade von älteren Versionen

### Von TropeTrainer 3.2
- TropeTrainer verwendete proprietäre Datenformate
- Ta'amimFlow nutzt offene Standards (tanach.us, WLC)
- Migration: Keine — neue Daten herunterladen

### Von Milestone 1-7 (pre-LocalTanachConnector)
```bash
# 1. Neue Dateien aus Milestone 8 einspielen
cp milestone8/taamimflow/connectors/local_tanach.py taamimflow/connectors/
cp milestone8/taamimflow/connectors/__init__.py taamimflow/connectors/
cp milestone8/config_default_settings.json .

# 2. tanach_data/ Ordner erstellen
mkdir tanach_data

# 3. TXT-Dateien herunterladen (siehe Schritt 5)

# 4. Config anpassen
# connector.type = "local" setzen
```

---

## Nächste Schritte

Nach erfolgreicher Installation:

1. **Open Reading Dialog**: File → Open Reading → Wähle Parasha
2. **View Modes testen**: Modern / STAM / Tikkun
3. **Color Modes**: Trope Colors / Symbol Colors / No Color
4. **Weitere Bücher hinzufügen**: Lade mehr TXT-Dateien herunter

**Roadmap:**
- Milestone 9: Trope Extraction (Farben pro Tropen-Gruppe)
- Milestone 10: Audio Engine (MVP Cantillation Synthesis)
- Milestone 11: Übungsmodus mit Progress Tracking

---

## Support & Community

- **GitHub Issues**: https://github.com/Moriahise/taamimflow_project/issues
- **Dokumentation**: Siehe README.md, CONFIG_GUIDE.md
- **Original TropeTrainer**: Archive verfügbar (nur Windows XP VM)

---

## Lizenz

Ta'amimFlow: [Deine Lizenz hier]  
Tanach-Daten (tanach.us): Public Domain (Westminster Leningrad Codex)  
SBL Hebrew Font: SIL Open Font License
