# annot_aid

Annotation made simple — with humans guiding the loop.

## Overview
annot_aid aims to make data annotation simple and efficient, with humans guiding the loop. This repo now includes a minimal, working Streamlit application for biomarker → LOINC annotation with a database‑agnostic adapter layer and basic tests.

## Stack
- Language: Python 3.11+
- UI: Streamlit
- Data: pandas DataFrame over small demo CSVs in data/
- DB adapters: file (demo), optional duckdb and snowflake (lazy imports)
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

## Run
- Streamlit app (development):
  - python -m streamlit run app.py
  - Use the sidebar to navigate to Overview, Axis Editor, and LOINC Matcher.
  - Demo data comes from data/biomarkers.csv and data/loinc_small.csv.

- Adapter selection
  - The app defaults to the file adapter. Future adapters can be selected via URL query param db=file|duckdb|snowflake.

## Scripts
No scripts are currently defined.

- TODO: Document available scripts or task runner commands (e.g., make, npm scripts, rye/poetry/pipenv tasks, justfile, invoke, fabric, tox, hatch, cargo, etc.).

## Environment Variables
No environment variables are currently defined.

- TODO: List and describe required env vars here (names, examples, and whether they are mandatory or optional). Consider providing an example .env file.

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
