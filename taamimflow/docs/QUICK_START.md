# Ta'amimFlow — Quick Start (Milestone 8)

## 3-Schritt-Installation

```bash
# 1. Clone & Install
git clone https://github.com/Moriahise/taamimflow_project.git
cd taamimflow_project
pip install -r requirements.txt

# 2. Tanach-Daten einrichten
mkdir tanach_data
# → Lade TXT-Dateien von https://www.tanach.us/ herunter
# → Speichere sie in tanach_data/

# 3. Starten
python -m taamimflow.main
```

## Konfiguration umschalten

**Offline (Standard — empfohlen):**
```json
{ "connector": { "type": "local" } }
```

**Online (Sefaria API):**
```json
{ "connector": { "type": "sefaria" } }
```

## Verfügbare Bücher prüfen

```bash
python -c "
from taamimflow.connectors.local_tanach import LocalTanachConnector
conn = LocalTanachConnector(tanach_dir='tanach_data')
print(conn.list_available_books())
"
```

## Tests

```bash
python tests/test_local_tanach.py
# Erwartetes Ergebnis: 35/35 Tests grün
```

## Dokumentation

- **Vollständige Installation**: siehe INSTALLATION.md
- **Alle Config-Optionen**: siehe CONFIG_GUIDE.md
- **Milestone-Details**: siehe MILESTONE_8_DONE.md
