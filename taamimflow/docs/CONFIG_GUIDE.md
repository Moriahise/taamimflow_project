# Ta'amimFlow — Konfigurations-Handbuch

Stand: Milestone 8 (2026-02-17)

---

## Schnellstart

### Offline-Modus (empfohlen)
```json
{
  "connector": {
    "type": "local",
    "tanach_dir": "tanach_data"
  }
}
```
→ Lege TXT-Dateien in `tanach_data/` → fertig!

### Online-Modus (Sefaria API)
```json
{
  "connector": {
    "type": "sefaria"
  }
}
```
→ Benötigt Internet, kann langsam sein / UI einfrieren

---

## Connector-Optionen (`connector`)

| Option | Typ | Standard | Beschreibung |
|--------|-----|----------|--------------|
| **`type`** | string | `"local"` | `"local"` = offline TXT-Dateien<br>`"sefaria"` = Online-API |
| **`tanach_dir`** | string | `"tanach_data"` | Ordner mit `.txt`-Dateien (nur für `type="local"`) |
| **`preferred_format`** | string | `"cantillation"` | Welches Format bevorzugen wenn mehrere Dateien für ein Buch existieren:<br>• `"cantillation"` = Ta'amei Hamikra (volle Tropen)<br>• `"text_only"` = Text Only (Konsonanten)<br>• `"masorah"` = Miqra-Masorah-Variante<br>• `"any"` = erste gefundene Datei |
| **`strip_cantillation`** | bool | `false` | Wenn `true`: Entfernt alle Vokale/Tropen aus dem Text |
| **`strip_paragraph_markers`** | bool | `true` | Entfernt (פ) und (ס) Absatzmarkierungen |
| **`sefaria_base_url`** | string | `"https://www.sefaria.org/api"` | Sefaria API-URL (nur für `type="sefaria"`) |
| **`sefaria_timeout`** | int | `30` | Timeout in Sekunden für Sefaria-Anfragen |

---

## Display-Optionen (`display`)

| Option | Typ | Standard | Beschreibung |
|--------|-----|----------|--------------|
| **`theme`** | string | `"light"` | `"light"` oder `"dark"` |
| **`font_size`** | int | `16` | Basis-Schriftgröße in Pixel |
| **`hebrew_font`** | string | `"SBL Hebrew"` | Primäre Schriftart für Hebräisch |
| **`hebrew_font_fallback`** | string | `"Ezra SIL, ..."` | Fallback-Schriften wenn primäre nicht verfügbar |
| **`show_nikud`** | bool | `true` | Vokalpunkte anzeigen |
| **`show_tropes`** | bool | `true` | Kantillationszeichen anzeigen |
| **`show_translations`** | bool | `true` | Übersetzungen anzeigen (wenn vorhanden) |
| **`text_direction`** | string | `"rtl"` | Textrichtung: `"rtl"` (rechts-nach-links) oder `"ltr"` |
| **`default_view_mode`** | string | `"modern"` | Ansichtsmodus: `"modern"`, `"stam"`, `"tikkun"` |
| **`default_color_mode`** | string | `"trope_colors"` | Farbmodus: `"no_color"`, `"trope_colors"`, `"symbol_colors"` |

---

## Audio-Optionen (`audio`)

| Option | Typ | Standard | Beschreibung |
|--------|-----|----------|--------------|
| **`enabled`** | bool | `false` | Audio-System aktivieren (Milestone 10+) |
| **`default_volume`** | float | `0.8` | Lautstärke 0.0–1.0 |
| **`auto_play`** | bool | `false` | Automatisch abspielen beim Laden |
| **`auto_repeat`** | bool | `false` | Automatisch wiederholen |
| **`speed_range`** | array | `[0.5, 2.0]` | Min/Max Abspielgeschwindigkeit |
| **`default_speed`** | float | `1.0` | Standard-Geschwindigkeit (1.0 = normal) |
| **`audio_format`** | string | `"mp3"` | Bevorzugtes Audio-Format |
| **`tradition`** | string | `"Ashkenazi"` | Tropen-Tradition: `"Ashkenazi"`, `"Sephardi"`, `"Yemenite"` |
| **`pitch`** | int | `0` | Tonhöhen-Anpassung in Halbtönen (-12 bis +12) |

---

## Kalender-Optionen (`calendar`)

| Option | Typ | Standard | Beschreibung |
|--------|-----|----------|--------------|
| **`diaspora_mode`** | bool | `true` | Diaspora-Kalender (2 Tage Jom Tov) statt Israel |
| **`show_hebrew_dates`** | bool | `true` | Hebräische Datumsanzeige |
| **`highlight_holidays`** | bool | `true` | Feiertage hervorheben |
| **`week_starts_on`** | string | `"saturday"` | Wochenanfang: `"saturday"` oder `"sunday"` |
| **`triennial_cycle`** | bool | `false` | Dreijahres-Lesezyklus (statt 1 Jahr) |

---

## Übungs-Optionen (`practice`)

| Option | Typ | Standard | Beschreibung |
|--------|-----|----------|--------------|
| **`session_duration`** | int | `30` | Standard-Übungszeit in Minuten |
| **`difficulty`** | string | `"intermediate"` | Schwierigkeit: `"beginner"`, `"intermediate"`, `"advanced"` |
| **`show_hints`** | bool | `true` | Hinweise während der Übung anzeigen |
| **`immediate_feedback`** | bool | `true` | Sofort-Feedback bei Fehlern |
| **`track_progress`** | bool | `true` | Fortschritt speichern |
| **`daily_goal_minutes`** | int | `15` | Tägliches Übungsziel in Minuten |
| **`default_pronunciation`** | string | `"Sephardi"` | Aussprache: `"Sephardi"` oder `"Ashkenazi"` |

---

## Benutzer-Optionen (`user`)

| Option | Typ | Standard | Beschreibung |
|--------|-----|----------|--------------|
| **`current_user`** | string/null | `null` | Aktueller Benutzername (null = kein Benutzer) |
| **`multi_user_mode`** | bool | `false` | Mehrere Benutzerprofile erlauben |
| **`save_progress`** | bool | `true` | Fortschritt automatisch speichern |

---

## Pfad-Optionen (`paths`)

| Option | Typ | Standard | Beschreibung |
|--------|-----|----------|--------------|
| **`audio_directory`** | string | `"assets/audio"` | Ordner für Audio-Dateien |
| **`data_directory`** | string | `"assets/data"` | Ordner für Daten-Dateien |
| **`fonts_directory`** | string | `"assets/fonts"` | Ordner für Schriftarten |
| **`user_data`** | string | `"user_data"` | Ordner für Benutzerdaten |
| **`database`** | string | `"database/taamimflow.db"` | SQLite-Datenbank-Pfad |
| **`tanach_data`** | string | `"tanach_data"` | Ordner für lokale Tanach-TXT-Dateien |
| **`sedrot_xml`** | string | `"sedrot.xml"` | Parasha-Definitionen |
| **`tropedef_xml`** | string | `"tropedef.xml"` | Tropen-Definitionen |
| **`tropenames_xml`** | string | `"tropenames.xml"` | Tropen-Namen/Transliteration |
| **`custom_sedrot_xml`** | string | `"custom_sedrot.xml"` | Benutzerdefinierte Lesungen |

---

## Erweiterte Optionen (`advanced`)

| Option | Typ | Standard | Beschreibung |
|--------|-----|----------|--------------|
| **`debug_mode`** | bool | `false` | Debug-Modus aktivieren (mehr Logging) |
| **`log_level`** | string | `"WARNING"` | Log-Level: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"` |
| **`auto_update`** | bool | `true` | Automatische Updates prüfen |
| **`telemetry`** | bool | `false` | Anonyme Nutzungsstatistik senden |
| **`async_loading`** | bool | `true` | Asynchrones Laden (verhindert UI-Freeze) |
| **`cache_enabled`** | bool | `true` | Datei-Cache aktivieren |

---

## GUI-Optionen (`gui`)

| Option | Typ | Standard | Beschreibung |
|--------|-----|----------|--------------|
| **`window_title`** | string | `"Ta'amimFlow — ..."` | Fenstertitel |
| **`window_width`** | int | `1200` | Fensterbreite in Pixel |
| **`window_height`** | int | `800` | Fensterhöhe in Pixel |
| **`remember_window_size`** | bool | `true` | Fenstergröße beim Schließen speichern |
| **`remember_last_reading`** | bool | `true` | Zuletzt geöffnete Lesung merken |

---

## Umgebungsvariable

Um eine **benutzerdefinierte Config** zu verwenden:

```bash
export TAAMIMFLOW_CONFIG=/pfad/zu/meiner_config.json
python -m taamimflow.main
```

Die benutzerdefinierte Config überschreibt nur die angegebenen Werte,  
alle anderen Werte kommen aus `config_default_settings.json`.

---

## Häufige Szenarien

### 1. Nur Konsonanten anzeigen (kein Nikud, keine Tropen)
```json
{
  "connector": { "strip_cantillation": true },
  "display": { "show_nikud": false, "show_tropes": false }
}
```

### 2. Schnellster Offline-Modus
```json
{
  "connector": { "type": "local" },
  "advanced": { "cache_enabled": true }
}
```

### 3. Sefaria mit längerer Timeout (langsame Verbindung)
```json
{
  "connector": {
    "type": "sefaria",
    "sefaria_timeout": 60
  }
}
```

### 4. Mehrere Formate im tanach_data-Ordner
Beispiel: Du hast beide `Genesis_Ta_amei_Hamikra.txt` und `Genesis_Text_Only.txt`

```json
{
  "connector": {
    "preferred_format": "cantillation"
  }
}
```
→ Ta'amei-Datei wird bevorzugt geladen

---

## Validierung

Nach Änderungen Config validieren:
```bash
python -c "import json; json.load(open('config_default_settings.json'))"
```

Wenn kein Fehler → Config ist gültig.

---

## Support

Bei Problemen mit der Config:
1. Prüfe JSON-Syntax (z.B. auf jsonlint.com)
2. Vergleiche mit `config_default_settings.json`
3. Setze `"debug_mode": true` und prüfe die Logs
4. Issue auf GitHub: https://github.com/Moriahise/taamimflow_project
