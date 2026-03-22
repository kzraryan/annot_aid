# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

annot_aid is a Streamlit app for biomarker-to-LOINC annotation with a human-in-the-loop workflow. Users browse a biomarker queue, narrow LOINC candidates via axis filters and text search, select matching LOINC codes, and persist their annotations. The app is database-agnostic through an adapter layer.

## Commands

```bash
# Install (editable, with optional extras)
python -m pip install -e .                    # base: pandas, streamlit, duckdb
python -m pip install -e ".[snowflake]"       # adds snowflake-connector-python

# Initialize DuckDB (loads CSVs into data/annot_aid.duckdb)
python init_duck_db.py

# Run the Streamlit app
python -m streamlit run app.py

# Run all tests
python -m pytest -q

# Run a single test file or test
python -m pytest tests/test_filtering.py -q
python -m pytest tests/test_filtering.py::test_text_filter -q
```

## Architecture

### Database Adapter Layer (`src/annot_aid/db/`)

`base.py` defines the `DBAdapter` Protocol and `FilterParams` dataclass. All adapters implement the same interface:
- **Read**: `get_biomarker_queue()`, `get_loinc_candidates(FilterParams)`, `get_loinc_by_nums(nums)`
- **Write**: `upsert_axes()`, `upsert_loincs()`, `load_saved_axes()`, `load_saved_loincs()`

`duckdb_adapter.py` is the primary adapter. It connects to a DuckDB file (default `data/annot_aid.duckdb`), uses schema `MAPPING`, and builds parameterized SQL with `ILIKE` text search and `IN` axis filters. Axis column names and search fields are driven by `config.toml`.

`snowflake_adapter.py` mirrors the DuckDB adapter for Snowflake (lazy import of connector).

### DuckDB Schema (`init_duck_db.sql`)

Schema `MAPPING` with tables:
- `LOINC` — loaded from `data/loinc.csv`, filtered to CLASSTYPE 1 (LAB) and 2 (CLIN)
- `BIOMARKERS` — loaded from `data/biomarkers.csv` with auto-generated `BIOMARKER_ID`
- `BIOMARKER_AXES_SEL` — user axis selections (soft-delete via `ACTIVE_IND`)
- `BIOMARKER_LOINCS_SEL` — user LOINC selections with confidence and rationale

All persistence uses soft-delete (`ACTIVE_IND = 0/1`) with `UPDT_DT_TM` timestamps and `USER_ID` tracking.

### Configuration (`config.toml` → `src/annot_aid/config.py`)

`config.toml` defines the canonical LOINC axes list under `[annot_aid].loinc_axes` and the DuckDB path. `config.py` loads this at import time and exports `AXES` as a tuple used by filtering and adapters. Defaults are hardcoded if config is missing.

### Filtering (`src/annot_aid/model/filtering.py`)

Pure-pandas filtering used by the file adapter path. `apply_filters()` combines text search (substring across multiple columns), axis-based `isin()` filtering, and deprecated-row exclusion. The DuckDB adapter does equivalent filtering in SQL.

### Streamlit Pages (`pages/`)

Three-page layout navigated via sidebar:
1. **Overview** — biomarker queue table, axes-filled count, selected LOINCs per biomarker
2. **Axis Editor** — multi-select widgets for each LOINC axis; persists via adapter
3. **LOINC Matcher** — text/axis/deprecated filters, hierarchical browser (class → component), checkbox selection, confidence slider, rationale textarea

Session state keys: `adapter`, `queue` (biomarker DataFrame), `idx` (current row), `axes`, `selected_loincs`, `saved_annotations`.

### Environment Variables

- `ANNOT_AID_DUCKDB_PATH` — override DuckDB file location (default: `data/annot_aid.duckdb`)
- `ANNOT_AID_USER` — user ID for audit columns (default: `"default"`)

### Adapter Selection

URL query param `?db=file|duckdb|snowflake` forces an adapter. Without it, the app uses DuckDB if `data/annot_aid.duckdb` exists, otherwise falls back to file adapter.
