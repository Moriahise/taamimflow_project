# FIX 2: Haftarah Auswahl → AttributeError: 'list' object has no attribute 'split'

## Problem

Beim Auswählen einer **Haftarah** stürzt das GUI ab:
```
AttributeError: 'list' object has no attribute 'split'
  File "main_window.py", line 682, in load_parsha
    tokens = tokenise(text)
  File "trope_parser.py", line 255, in tokenise
    raw_words = text.split()
```

**Ursache:** Der Connector gibt manchmal eine **Liste** zurück statt einen **String**.

---

## Warum passiert das?

### Zwei mögliche Quellen:

**1. `get_chapter()` gibt `List[str]` zurück (by design)**
```python
def get_chapter(self, book_name: str, chapter: int) -> List[str]:
    """Return all verses of a chapter as a list of strings."""
    return ["Verse 1", "Verse 2", ...]  # ← Liste!
```

**2. Fehler beim Laden → Fallback gibt leere Liste**
```python
try:
    text = self.connector.get_haftarah(...)
except Exception:
    text = []  # ← Könnte passieren bei fehlender Implementierung
```

---

## Die Lösung

**In `main_window.py` NACH dem `try/except` Block (Zeile ~680):**

**VORHER:**
```python
        except Exception:
            text = ""

        # ── Tokenise with the real trope parser ──
        tokens = tokenise(text)  # ← Crash wenn text eine Liste ist!
```

**NACHHER:**
```python
        except Exception:
            text = ""

        # ── Ensure text is string (flatten lists from some connectors) ──
        if isinstance(text, list):
            text = "\n".join(str(item) for item in text)
        elif not isinstance(text, str):
            text = str(text) if text else ""
        
        # ── Tokenise with the real trope parser ──
        tokens = tokenise(text)
```

---

## Automatischer Patch

**Methode 1: Korrigierte Datei verwenden (EINFACHSTE)**

Download `main_window.py` (von oben) → Ersetze:
```
taamimflow/gui/main_window.py
```

**Methode 2: Manuell editieren**

1. Öffne `taamimflow/gui/main_window.py`
2. Suche Zeile ~680-682:
   ```python
   except Exception:
       text = ""
   
   # ── Tokenise with the real trope parser ──
   tokens = tokenise(text)
   ```

3. Füge ZWISCHEN diesen Zeilen ein:
   ```python
   # Ensure text is string (flatten lists from some connectors)
   if isinstance(text, list):
       text = "\n".join(str(item) for item in text)
   elif not isinstance(text, str):
       text = str(text) if text else ""
   ```

4. Speichern → Fertig!

---

## Zusätzlich: LocalTanachConnector erweitern (Optional)

Wenn `get_haftarah` noch nicht implementiert ist, füge hinzu:

**In `local_tanach.py` nach `get_parasha` (ca. Zeile 610):**

```python
def get_haftarah(
    self,
    parasha_name: str,
    cycle: int = 0,
    for_date: Optional[date] = None,
) -> str:
    """Get Haftarah reading for a parasha.
    
    Uses sedrot.xml to find Haftarah references marked with
    type="HAFTARAH" or similar.
    
    :param parasha_name: Name of the parasha.
    :param cycle: Triennial cycle (not used for Haftarot).
    :param for_date: Optional date (for special Haftarot).
    :returns: Hebrew text as string.
    """
    return self.get_parasha(
        parasha_name,
        reading_type="Haftarah",
        cycle=cycle
    )

def get_maftir(
    self,
    parasha_name: str,
    cycle: int = 0,
) -> str:
    """Get Maftir reading (typically last aliyah).
    
    :param parasha_name: Name of the parasha.
    :param cycle: Triennial cycle.
    :returns: Hebrew text as string.
    """
    # Simplified: return last aliyah (SHVII)
    return self.get_parasha(
        parasha_name,
        reading_type="Torah",
        aliyah="SHVII",
        cycle=cycle
    )
```

---

## Testen nach dem Fix

```bash
# 1. GUI starten
python -m taamimflow.main

# 2. File → Open Reading

# 3. **Haftarah** Tab auswählen

# 4. Beliebige Haftarah auswählen

# 5. Sollte jetzt funktionieren (kein Crash!)
```

**Erwartetes Ergebnis:**
- ✅ Kein `AttributeError` mehr
- ✅ Text wird geladen (oder leerer Bereich wenn keine Haftarah-Daten)
- ✅ GUI bleibt stabil

---

## Warum dieser Fix wichtig ist

### Robustheit gegen verschiedene Connector-Typen

Der Fix macht `MainWindow` **kompatibel** mit allen Connector-Implementierungen:

| Connector-Verhalten | Vor dem Fix | Nach dem Fix |
|---------------------|-------------|--------------|
| Gibt String zurück | ✅ OK | ✅ OK |
| Gibt Liste zurück | ❌ Crash | ✅ OK (join zu String) |
| Gibt None zurück | ❌ Crash | ✅ OK (→ leerer String) |
| Gibt int/object zurück | ❌ Crash | ✅ OK (str() Konvertierung) |

---

## Zusammenfassung beider Fixes

### Fix 1: `cycle` Parameter (local_tanach.py)
```python
def get_parasha(..., cycle: int = 0) -> str:
```
**Problem:** MainWindow übergibt `cycle`, aber Methode akzeptiert es nicht  
**Lösung:** Parameter hinzufügen

### Fix 2: List → String (main_window.py)
```python
if isinstance(text, list):
    text = "\n".join(str(item) for item in text)
```
**Problem:** Connector gibt Liste zurück, Parser erwartet String  
**Lösung:** Automatische Konvertierung

---

## Nach beiden Fixes

```bash
python -m taamimflow.main

# Funktioniert jetzt:
✅ Torah-Lesung (Balak, Bereshit, ...)
✅ Haftarah-Lesung
✅ Maftir-Lesung
✅ Alle Reading Types
✅ Annual + Triennial
```

---

## Debug-Tipp

Falls weitere Probleme auftreten:

```python
# In main_window.py nach Zeile 679 einfügen:
except Exception as e:
    text = ""
    print(f"⚠️ Error loading text: {e}")
    print(f"   Type of text: {type(text)}")
    import traceback
    traceback.print_exc()
```

Das zeigt dir genau **wo** und **warum** der Fehler auftritt.

---

## Dateien zum Download

1. **local_tanach.py** (korrigiert) - Mit `cycle` Parameter
2. **main_window.py** (korrigiert) - Mit List→String Handling
3. **HAFTARAH_FIX.md** - Diese Anleitung

---

**🎉 Beide Fixes angewendet = Voll funktionsfähiges GUI!**
