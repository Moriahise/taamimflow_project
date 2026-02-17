# Config-Änderungen: Alt → Neu (Milestone 8)

## Zusammenfassung

Die neue Config behält **alle bestehenden Settings** und fügt den neuen **Connector-Bereich** hinzu.

---

## Neue Bereiche

### ✅ NEU: `connector` (Milestone 8)
```json
{
  "connector": {
    "type": "local",                    // NEU: "local" oder "sefaria"
    "tanach_dir": "tanach_data",        // NEU: Ordner für TXT-Dateien
    "preferred_format": "cantillation", // NEU: Welches Format bevorzugen
    "strip_cantillation": false,        // NEU: Vokale/Tropen entfernen
    "strip_paragraph_markers": true,    // NEU: (פ) (ס) entfernen
    "sefaria_base_url": "...",          // NEU: Sefaria API URL
    "sefaria_timeout": 30               // NEU: Timeout in Sekunden
  }
}
```

---

## Geänderte Bereiche

### `app`
```diff
  "app": {
-   "name": "TropTrainer 2.0",
+   "name": "Ta'amimFlow",
    "version": "1.0.0-alpha",
    "language": "de",
    "first_run": true
  }
```

### `display`
```diff
  "display": {
    "theme": "light",
    "font_size": 16,
    "hebrew_font": "SBL Hebrew",
+   "hebrew_font_fallback": "Ezra SIL, Taamey Frank CLM, Arial",  // NEU
    "show_nikud": true,
    "show_tropes": true,
    "show_translations": true,
-   "text_direction": "rtl"
+   "text_direction": "rtl",
+   "default_view_mode": "modern",                                // NEU
+   "default_color_mode": "trope_colors"                          // NEU
  }
```

### `audio`
```diff
  "audio": {
+   "enabled": false,                   // NEU (Audio noch nicht implementiert)
    "default_volume": 0.8,
    "auto_play": false,
    "auto_repeat": false,
    "speed_range": [0.5, 2.0],
    "default_speed": 1.0,
-   "audio_format": "mp3"
+   "audio_format": "mp3",
+   "tradition": "Ashkenazi",           // NEU (für Milestone 10)
+   "pitch": 0                          // NEU
  }
```

### `calendar`
```diff
  "calendar": {
    "diaspora_mode": true,
    "show_hebrew_dates": true,
    "highlight_holidays": true,
-   "week_starts_on": "saturday"
+   "week_starts_on": "saturday",
+   "triennial_cycle": false             // NEU
  }
```

### `practice`
```diff
  "practice": {
    "session_duration": 30,
    "difficulty": "intermediate",
    "show_hints": true,
    "immediate_feedback": true,
    "track_progress": true,
-   "daily_goal_minutes": 15
+   "daily_goal_minutes": 15,
+   "default_pronunciation": "Sephardi"  // NEU
  }
```

### `paths`
```diff
  "paths": {
    "audio_directory": "assets/audio",
    "data_directory": "assets/data",
    "fonts_directory": "assets/fonts",
    "user_data": "user_data",
-   "database": "database/troptrainer.db"
+   "database": "database/taamimflow.db",  // Umbenannt
+   "tanach_data": "tanach_data",          // NEU
+   "sedrot_xml": "sedrot.xml",            // NEU
+   "tropedef_xml": "tropedef.xml",        // NEU
+   "tropenames_xml": "tropenames.xml",    // NEU
+   "custom_sedrot_xml": "custom_sedrot.xml" // NEU
  }
```

### `advanced`
```diff
  "advanced": {
    "debug_mode": false,
-   "log_level": "INFO",
+   "log_level": "WARNING",              // Geändert (weniger Logs)
    "auto_update": true,
-   "telemetry": false
+   "telemetry": false,
+   "async_loading": true,               // NEU (für Milestone 6)
+   "cache_enabled": true                // NEU
  }
```

### ✅ NEU: `gui`
```json
{
  "gui": {
    "window_title": "Ta'amimFlow — Torah Cantillation Trainer",
    "window_width": 1200,
    "window_height": 800,
    "remember_window_size": true,
    "remember_last_reading": true
  }
}
```

---

## Unveränderte Bereiche

### `user` — Keine Änderungen
```json
{
  "user": {
    "current_user": null,
    "multi_user_mode": false,
    "save_progress": true
  }
}
```

---

## Migrationsanleitung

### Für bestehende Installationen:

1. **Sichere alte Config:**
   ```bash
   cp config_default_settings.json config_default_settings.json.backup
   ```

2. **Neue Config einspielen:**
   ```bash
   cp milestone8/config_default_settings.json .
   ```

3. **Tanach-Daten einrichten:**
   ```bash
   mkdir tanach_data
   # TXT-Dateien von tanach.us herunterladen
   ```

4. **Alte Einstellungen übertragen** (falls du sie angepasst hattest):
   - Öffne `config_default_settings.json.backup`
   - Kopiere deine angepassten Werte in die neue Config
   - Behalte die neuen `connector`-Einstellungen

### Für neue Installationen:

Einfach die neue `config_default_settings.json` verwenden — alles ist bereits konfiguriert!

---

## Abwärtskompatibilität

✅ **Alte Sefaria-Connector funktioniert weiterhin:**
```json
{
  "connector": { "type": "sefaria" }
}
```

✅ **Alte XML-Dateien (sedrot.xml, tropedef.xml) funktionieren unverändert**

✅ **GUI-Code erkennt neue Settings automatisch**

⚠️ **Neue Features benötigen neue Settings:**
- Offline-Modus → `connector.type = "local"` + `tanach_data/` Ordner
- Custom View Modes → `display.default_view_mode`
- Trope Color Modes → `display.default_color_mode`

---

## Schnellvergleich

| Feature | Alt (Milestone 7) | Neu (Milestone 8) |
|---------|------------------|-------------------|
| **Text-Quelle** | Nur Sefaria API | Sefaria **ODER** lokale TXT-Dateien |
| **Internet benötigt** | Ja | Nein (wenn `type="local"`) |
| **Ladezeit** | 1-5 Sekunden | < 0.01 Sekunden |
| **UI-Freeze** | Möglich | Nie (lokaler Modus) |
| **Offline-fähig** | Nein | Ja |
| **Config-Bereiche** | 7 Bereiche | 9 Bereiche (+connector, +gui) |
| **Settings gesamt** | ~30 | ~50 |

---

## Testing

Nach Config-Änderung:
```bash
# 1. JSON-Syntax prüfen
python -c "import json; json.load(open('config_default_settings.json'))"

# 2. Connector testen
python -c "
from taamimflow.connectors import get_default_connector
from taamimflow.config import get_app_config
config = get_app_config()
conn = get_default_connector(config.get('connector'))
print('Connector type:', type(conn).__name__)
"

# 3. Full Test Suite
python tests/test_local_tanach.py
```

---

## Fragen?

- Siehe **CONFIG_GUIDE.md** für detaillierte Erklärung aller Optionen
- Siehe **INSTALLATION.md** für Setup-Anleitung
- Siehe **MILESTONE_8_DONE.md** für technische Details
