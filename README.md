# Ta'amimFlow – Open‑Source Cantillation Trainer

*Reimagining the legacy of TropeTrainer for modern platforms*

## Vision

The original **TropeTrainer** was the only software to synthesize Torah
cantillation on the fly.  It combined a perpetual Jewish calendar,
multiple trope traditions, adjustable pitch and speed controls, and
support for Ashkenazic and Sephardic pronunciations【954408483416731†L74-L92】.
When its creator Thomas Buchler died and the company folded, the
application stopped working on modern systems and the source code
disappeared【954408483416731†L74-L92】【954408483416731†L74-L92】.  A
clean‑room rebuild is both legally permissible and technically
feasible【954408483416731†L74-L92】.  **Ta'amimFlow** aims to fill that
void: it is a modular, extensible platform for learning and practicing
cantillation using open data and modern technology.

This repository currently contains a **base structure** for the
project.  Many components are stubs awaiting further work, but the
fundamental architecture is in place to support future development.

## Architecture Overview

The code is organised as a Python package `taamimflow` with several
subpackages:

- **`config`** – loads and merges application settings from
  `config_default_settings.json`.  Users can override any value by
  setting the `TAAMIMFLOW_CONFIG` environment variable to point at
  their own JSON file.
- **`data`** – parsers for static XML files extracted from the
  original TropeTrainer installer.  Currently implemented parsers:
  `tropedef.xml` (trope melody definitions), `tropenames.xml`
  (transliteration tables), `sedrot.xml` (reading schedule) and
  `training.xml` (lesson metadata).
- **`connectors`** – pluggable interfaces for fetching text.  A
  default `SefariaConnector` demonstrates how to call the Sefaria
  public API, but additional connectors (e.g. local filesystem,
  preloaded texts) can be added without changing the rest of the
  program.
- **`gui`** – a PyQt6 user interface.  It includes a
  `ModernTorahTextWidget` with view and colour modes, a simple
  `OpenReadingDialog` for choosing a parasha, and a
  `MainWindow` that ties everything together.
- **`utils`** – helper modules for Hebrew text processing and audio
  playback.  The current `audio` module is a skeleton awaiting
  integration with a real synthesiser or concatenative engine.

The entry point is `taamimflow/main.py`.  Running `python -m
taamimflow.main` launches the PyQt application.

## Features

The prototype implements a minimal workflow:

1. **Open Reading** – choose a Torah portion from a list loaded from
   `sedrot.xml`.  Future versions will include holiday and custom
   readings.
2. **Fetch Text** – the default connector retrieves the Hebrew text of
   the parasha from Sefaria's API.  If network access is unavailable,
   the connector raises a `ConnectionError`; offline connectors can be
   implemented to read local files.
3. **Display Modes** – the `ModernTorahTextWidget` supports three view
   modes (modern with vowels and tropes, STAM without vowels, and
   a two‑column Tikkun view) and three colour modes (no colour,
   trope‑coloured, symbol‑coloured).  These correspond to the
   configuration of the original TropeTrainer【954408483416731†L74-L92】.

Although functional, this is only a starting point.  The long‑term
goal is to support:

- **Singing‑voice synthesis** or **audio concatenation** for
  real‑time chanting, replicating Buchler's core innovation【954408483416731†L74-L92】.
- **Perpetual calendar** with options for diaspora/Israel, triennial
  cycles and holiday readings.
- **Modular lesson system** based on `training.xml` with flashcards,
  tests and progress tracking.
- **Extensible connectors** (Sefaria, local caches, other APIs) and
  pluggable data sources (e.g. OSHB OSIS XML, user‑provided texts).
- **Web‑first implementation** using React/TypeScript and
  Progressive Web App technologies, as recommended in the technical
  roadmap【954408483416731†L74-L92】.  The Python/Qt prototype can serve
  as a reference implementation or offline desktop app.

## Installation

Install the dependencies listed in `requirements.txt`.  The GUI
requires **PyQt6** and **PyQt6‑WebEngine**.  Audio features will need
additional libraries once implemented.

```bash
python -m pip install -r requirements.txt
```

Run the application:

```bash
python -m taamimflow.main
```

## Contributing

Ta'amimFlow is a work in progress.  Contributions are welcome in
areas such as Hebrew text parsing, trope audio synthesis, calendar
calculation, and UI/UX design.  Please open issues or pull requests
to discuss features and propose improvements.  When implementing new
connectors, inherit from `BaseConnector` and register your class via
the `connector` configuration key.

## Legal

The Westminster Leningrad Codex text and traditional cantillation
melodies are in the public domain【954408483416731†L74-L92】.  This
project uses only openly licensed data and strives to avoid any
copyrighted expression from the original TropeTrainer software.  See
the file `Rebuilding TropeTrainer a complete technical and legal
roadmap.md` for an in‑depth discussion of the legal landscape.