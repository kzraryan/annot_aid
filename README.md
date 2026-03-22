# annot_aid

Annotation made simple — with humans guiding the loop.

## Overview
annot_aid aims to make data annotation simple and efficient, with humans guiding the loop. This repo now includes a minimal, working Streamlit application for biomarker → LOINC annotation with a database‑agnostic adapter layer and basic tests.

## Stack
- Language: Python 3.11+
- UI: Streamlit
- Data: pandas DataFrame over small demo CSVs in data/
- DB adapters: file (demo), duckdb (physical DB file), optional snowflake (lazy imports)
- Packaging: pyproject.toml (setuptools)

## Requirements
- Python 3.11+
- Recommended: virtual environment per project

Install dependencies:
- python -m pip install --upgrade pip
- python -m pip install -e .[duckdb,snowflake]  # extras optional; the demo uses only base deps

## Setup
1. Clone the repository
   - git clone <REPO_URL>
   - cd annot_aid
2. (Optional) Create and activate a venv
   - python -m venv .venv
   - .\.venv\Scripts\Activate.ps1
3. Install dependencies
   - python -m pip install --upgrade pip
   - python -m pip install -e .  # base deps (pandas, streamlit)
   - Optional: python -m pip install -e .[duckdb,snowflake]

## Configuration
- Project-level constants are centralized in config.toml at the repository root.
- Axes: set annot_aid.axes to control the canonical list and order of LOINC axes shown in the UI and used in filtering.

Example config.toml:

```
[annot_aid]
axes = [
  "Component",
  "Property",
  "Time",
  "System",
  "Scale",
  "Method",
]
```

If config.toml is missing or malformed, safe defaults are used.

## Run
- Streamlit app (development):
  - python -m streamlit run app.py
  - Use the sidebar to navigate to Overview, Axis Editor, and LOINC Matcher.

- Database (DuckDB)
  - By default, the app prefers a DuckDB database at data/annot_aid.duckdb if present.
  - You can override the path via environment variable ANNOT_AID_DUCKDB_PATH.
    - Example (PowerShell): $Env:ANNOT_AID_DUCKDB_PATH = "C:\\path\\to\\your.db"
  - If no valid DuckDB is found, the app falls back to the demo file adapter (CSV-based).

- Adapter selection
  - You can force the adapter via URL query param db=file|duckdb|snowflake.
    - Examples:
      - http://localhost:8501/?db=duckdb
      - http://localhost:8501/?db=file
  - When not specified, the app auto-selects DuckDB if data/annot_aid.duckdb exists, otherwise uses the file adapter.
  - The DuckDB adapter reads/writes only to the physical DB file; no CSV fallback at runtime.

## Scripts
No scripts are currently defined.

- TODO: Document available scripts or task runner commands (e.g., make, npm scripts, rye/poetry/pipenv tasks, justfile, invoke, fabric, tox, hatch, cargo, etc.).

## Environment Variables
- ANNOT_AID_USER_ID (optional): user identifier recorded in DuckDB audit columns when saving axes/LOINC selections. Defaults to "demo" if not set.

Example (PowerShell):
- $Env:ANNOT_AID_USER_ID = "alice"

## Tests
- Install pytest (in venv or user-site):
  - python -m pip install --upgrade pytest
- Run tests:
  - python -m pytest -q
- The suite covers:
  - FileAdapter loading and basic filtering
  - Filtering utility for text/axes/deprecated logic

## Project Structure
Current tree:

```
annot_aid/
├─ LICENSE
└─ README.md
```

As the project grows, consider adopting a clear structure (src/ layout for libraries, app/ or services/ for apps, tests/ for test suites, configs in config/ or .github/workflows for CI).

## Contributing
Contributions are welcome once the initial codebase is established. Please open an issue to discuss major changes. A CONTRIBUTING.md file can be added later.

## License
This project is licensed under the MIT License. See the LICENSE file for details.

© 2025 Md Kamruz Zaman Rana
