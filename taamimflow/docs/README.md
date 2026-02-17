# tanach_data — Lokale Tanach-Textdateien

Dieser Ordner enthält die lokalen Tanach-Textdateien für Ta'amimFlow.

## Dateien ablegen

Einfach die `.txt`-Dateien in diesen Ordner legen.  
Ta'amimFlow erkennt sie **automatisch** — kein weiteres Setup nötig.

## Unterstützte Formate (alle von tanach.us)

| Dateiname-Muster              | Beschreibung                            | Cantillation |
|-------------------------------|-----------------------------------------|:------------:|
| `*_Ta_amei_Hamikra*`          | Vollständige Te'amim + Vokale           | ✅           |
| `*_Text_Only*`                | Konsonanten-Text ohne Vokale/Tropen     | ❌           |
| `*_Miqra_according_to_Masorah*` | Masorah-Variante mit Te'amim          | ✅           |

### Empfehlung
Lade die Dateien mit **Ta'amei Hamikra** herunter – sie enthalten die  
vollständigen Kantillationszeichen, die Ta'amimFlow benötigt.

## Download-Quelle

**tanach.us** — alle Dateien sind öffentlich verfügbar:
```
https://www.tanach.us/Server.aspx?*Books*
```

Klicke auf „Text Files" → wähle das gewünschte Format → lade jedes Buch herunter.

Alternativ: Die gesamte Sammlung als ZIP ist manchmal unter  
`https://www.tanach.us/Download.xml` verfügbar.

## Dateiformat (intern)

Ta'amimFlow erwartet folgende Struktur (tanach.us Standard):

```
Genesis                          ← Zeile 1: Englischer Buchname
בראשית                           ← Zeile 2: Hebräischer Buchname
Tanach with Ta'amei Hamikra      ← Zeile 3: Quellname
https://www.tanach.us/...        ← Zeile 4: URL

בראשית



Chapter 1

בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים ...
וְהָאָ֗רֶץ הָיְתָ֥ה תֹ֙הוּ֙ ...
```

- Ein Vers pro Zeile
- Kapitelwechsel durch `Chapter N`
- Leerzeilen werden ignoriert

## Konfiguration

In `config_default_settings.json`:

```json
{
    "connector": {
        "type": "local",
        "tanach_dir": "tanach_data",
        "preferred_format": "cantillation"
    }
}
```

| Option                | Werte                                          | Standard        |
|-----------------------|------------------------------------------------|-----------------|
| `type`                | `"local"` / `"sefaria"`                        | `"sefaria"`     |
| `tanach_dir`          | Pfad zum Ordner mit den .txt-Dateien           | `"tanach_data"` |
| `preferred_format`    | `"cantillation"` / `"text_only"` / `"masorah"` / `"any"` | `"cantillation"` |
| `strip_cantillation`  | `true` / `false`                               | `false`         |

## Schnelltest

```bash
python -c "
from taamimflow.connectors.local_tanach import LocalTanachConnector
conn = LocalTanachConnector(tanach_dir='tanach_data')
print('Verfügbare Bücher:', conn.list_available_books())
print(conn.get_verse('Genesis', 1, 1))
"
```

## Mitgelieferte Beispieldateien

Die folgenden Dateien sind im Repo als Beispiel enthalten:

- `Habakkuk_Ta_amei_Hamikra.txt`  
- `Ecclesiastes_Text_Only.txt`  
- `Ruth_Miqra_according_to_Masorah.txt`

Sie decken alle drei Formate ab und ermöglichen sofortiges Testen.
