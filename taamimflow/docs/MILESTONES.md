# Ta’amimFlow – Milestones & Change Log

Stand: 2026-02-16  
Ziel: TropTrainer → Ta’amimFlow (modern, modular, erweiterbar, Sefaria + lokale Tanach-TXT)

---

## Milestone 1 — Projekt-Grundstruktur (Repo bootstrapped)

**Erreicht**
- Neues Python-Paket `taamimflow/` mit klarer Modulstruktur:
  - `config/` (Settings)
  - `data/` (XML-Parser)
  - `connectors/` (Textquellen – Sefaria/Offline/Plugins)
  - `gui/` (PyQt UI)
  - `utils/` (Hebräisch/Text/Audio/Paths)
- Startpunkt: `python -m taamimflow.main`

**Ergebnis**
- Repo ist GitHub-ready, sauberer Einstiegspunkt, klar erweiterbar.

---

## Milestone 2 — GUI Skeleton (funktionierendes Fenster + Modi)

**Erreicht**
- PyQt6 GUI startet stabil.
- Toolbar / Menüs:
  - Open Reading
  - View Modes: Modern / STAM / Tikkun
  - Color Modes: No Color / Trope Colors / Symbol Colors
- `ModernTorahTextWidget` zeigt Text an (Modern) + STAM-Strip + Tikkun-2-Spalten.

**Wichtigste Fixes**
- PyQt6 Import-Fix: `QAction` gehört zu `PyQt6.QtGui`, nicht `QtWidgets`.
- Dialog result: `QDialog.DialogCode.Accepted` statt `QDialog.Accepted` (PyQt6-API).

---

## Milestone 3 — Daten-/Pfadproblem gelöst (Root vs. Package)

**Problem**
- `sedrot.xml` & andere XML-Dateien lagen je nach Setup im Root oder in `taamimflow/`.
- Folge: Parasha-Liste leer / FileNotFound.

**Erreicht**
- Neuer Helper: `taamimflow/utils/paths.py`
  - `find_data_file(filename)` sucht in:
    1) Current Working Directory
    2) Repo-Root
    3) Package-Root (`taamimflow/`)
    4) utils-Dir
- `OpenReadingDialog` lädt `sedrot.xml` robust über `find_data_file()`.

**Ergebnis**
- Parasha-Liste erscheint zuverlässig.

---

## Milestone 4 — Sefaria-Connector repariert (Refs + verschachtelte Texte)

**Probleme**
1) `sedrot.xml` nutzt TropeTrainer-Refs wie `GEN1:1-2:3`
   - Sefaria erwartet i.d.R. „dotted refs“ wie `Genesis.1.1-2.3`
2) Sefaria liefert manchmal verschachtelte Listen (`he: [[...],[...]]`) statt flacher Liste.

**Erreicht**
- Neuer Helper: `taamimflow/utils/refs.py`
  - `normalize_ref("GEN1:1-2:3")` → `Genesis.1.1-2.3`
  - Nur wenn Pattern passt → sonst unverändert (non-breaking).
- `SefariaConnector.get_text()`:
  - normalisiert Ref automatisch
  - flacht `he/text` rekursiv ab (flatten)
- `SefariaConnector.get_parasha()`:
  - findet `sedrot.xml` via `find_data_file()`

**Ergebnis**
- Text kann aus Sefaria geladen werden (wenn Internet verfügbar).

---

## Milestone 5 — Windows-Install stabilisiert (Dependencies)

**Problem**
- `pyicu` buildet native, scheitert oft auf Windows ohne ICU/pkg-config.

**Erreicht**
- `pyicu` in `requirements.txt` als OPTIONAL markiert (auskommentiert),
  damit Standard-Install nicht blockiert.

---

## Aktueller Status (Bekanntes Verhalten)

### 1) Laden dauert lange / UI “Keine Rückmeldung”
Ursache: Netzwerkabruf passiert aktuell **synchron im UI-Thread**.
→ Wenn Sefaria langsam ist, friert das Fenster ein.

### 2) Sefaria Text enthält HTML/Tags (`<b>`, `&thinsp;` etc.)
Ursache: Sefaria Responses enthalten teils Markup/Entities.
→ Muss vor Anzeige bereinigt werden.

---

## Nächste Milestones (Roadmap / Prioritäten)

### Milestone 6 — “No-Freeze Loading” (Async + Progress + Timeout)
- Netzwerkabruf in Worker-Thread (Qt: `QThread`/`QRunnable`/`QtConcurrent`)
- UI zeigt Progress (“Loading…”) + Cancel
- Timeout + Retry + Fehlerdialog statt Crash

### Milestone 7 — “Sefaria Clean Text” (ohne Tags)
- HTML tags entfernen + Entities unescapen:
  - `re.sub(r"<[^>]+>", "", text)`
  - `html.unescape(text)`
- Optional: Konfig-Schalter `strip_html=true`

### Milestone 8 — Offline Connector: lokale Tanach-TXT
- `LocalTanachConnector`:
  - liest `.txt` aus einem konfigurierten Ordner
  - Mapping: Buchname → Datei
  - Referenzparser: Buch/Chapter/Verse
- Ziel: komplett unabhängig von Sefaria, schnell, kein Freeze.

### Milestone 9 — Echte Cantillation (Trope Extraction)
- Unicode Te’amim (U+0591–U+05AF) pro Wort extrahieren
- Trope → Gruppe → Farbe/Symbol
- Verbindung zu `tropedef.xml` (Melodie/Pattern)

### Milestone 10 — Audio Engine (MVP)
- Erstes Ziel: “play trope sequence” (Notes/Duration)
- Später: echte Synthese / Concatenation + Traditionen

---

## Dateien im Root (Ist-Zustand)
- `sedrot.xml`, `training.xml`, `tropedef.xml`, `tropenames.xml`, …
- Zusätzlich im Package (optional/ok): gleiche XMLs möglich, da `find_data_file()` robust sucht.

---

## Quick Test Commands (Windows)
- Start:
  - `python -m taamimflow.main`
- sedrot-Check:
  - `python -c "from taamimflow.utils.paths import find_data_file; print(find_data_file('sedrot.xml'))"`
- Ref-Check:
  - `python -c "from taamimflow.utils.refs import normalize_ref; print(normalize_ref('GEN1:1-2:3'))"`

---
