## Milestone 8 — Offline Connector: lokale Tanach-TXT  ✅ ERLEDIGT

Stand: 2026-02-17

### Ziel
Komplett offline, schnell, kein Freeze — unabhängig von Sefaria.

### Neue Dateien
| Datei | Beschreibung |
|---|---|
| `taamimflow/connectors/local_tanach.py` | Haupt-Connector (vollständig) |
| `taamimflow/connectors/__init__.py` | Aktualisiert: Factory für `"local"` + `"sefaria"` |
| `config_default_settings.json` | Connector-Typ jetzt konfigurierbar |
| `tanach_data/README.md` | Anleitung zum Ablegen der TXT-Dateien |
| `tests/test_local_tanach.py` | 35 Tests, alle grün |

### LocalTanachConnector — Funktionen

**Kernklassen:**
- `TanachTxtFile`: Parst eine einzelne tanach.us TXT-Datei  
  → Buch-Metadaten + `chapters: Dict[int, List[str]]`
- `LocalTanachConnector(BaseConnector)`: Vollständiger Connector  
  → Index aller `.txt`-Dateien im `tanach_data/`-Ordner

**Unterstützte Referenzformate:**
- TropeTrainer: `GEN1:1-2:3`
- Dotted: `Genesis.1.1-2.3`
- Colon/Space: `Genesis 1:1-2:3`
- Einzelvers: `Genesis 1:1` / `GEN1:1`

**Öffentliche API:**
```python
conn = LocalTanachConnector(tanach_dir="tanach_data")
conn.get_text("HAB1:1-3:19")            # beliebiger Ref-String
conn.get_verse("Habakkuk", 1, 1)        # einzelner Vers
conn.get_chapter("Habakkuk", 3)         # ganzes Kapitel als Liste
conn.get_parasha("Bereshit")            # über sedrot.xml (wie SefariaConnector)
conn.list_available_books()             # ["ecclesiastes", "habakkuk", "ruth", ...]
conn.get_book_info("Habakkuk")          # Metadaten-Dict
conn.reload_index()                     # Ordner neu einlesen
```

**Unterstützte Formate (alle drei tanach.us-Varianten):**
- `Tanach with Ta'amei Hamikra` (volle Kantillation + Vokale) ← Empfehlung
- `Tanach with Text Only` (Konsonanten, keine Vokale)
- `Miqra according to the Masorah` (mit HTML-Markup → automatisch bereinigt)

**Konfiguration** (`config_default_settings.json`):
```json
{
  "connector": {
    "type": "local",
    "tanach_dir": "tanach_data",
    "preferred_format": "cantillation",
    "strip_cantillation": false
  }
}
```

**Performance:**
- 3 Bücher (363 Verse total) geladen in **0.003s**
- Cache verhindert doppeltes Einlesen → zweiter Zugriff **< 0.0001s**
- Kein Netzwerk, kein Thread-Freeze, sofort verfügbar

**Verwaltung des `tanach_data/` Ordners:**
- Einfach beliebige tanach.us-TXT-Dateien hineinlegen
- Auto-Indexierung über den englischen Buchnamen (Zeile 1)
- Mehrere Formate für dasselbe Buch werden korrekt priorisiert

**Fehlerbehandlung:**
- `LookupError`: Buch nicht gefunden / Vers außerhalb des Bereichs
- `ValueError`: Referenz kann nicht geparst werden
- Unbekannte Bücher → saubere Fehlermeldung mit verfügbaren Büchern

### Tests (35/35 bestanden)
```
=== 1. Reference parser    (7 Tests)  ✓ alle
=== 2. Verse cleaning      (6 Tests)  ✓ alle
=== 3. TanachTxtFile       (11 Tests) ✓ alle
=== 4. LocalTanachConnector(17 Tests) ✓ alle
=== 5. Performance         (3 Tests)  ✓ alle
```

---

