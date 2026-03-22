annot_aid – Concise Dev Guidelines (updated 2025-10-12)

Scope
- This repo now contains a minimal Streamlit app for biomarker → LOINC annotation, a DB-agnostic adapter layer, tests, and demo CSV data.

Stack and layout
- Python ≥ 3.11
- UI: Streamlit
- Data handling: pandas
- Adapters (demo-ready): file; optional: duckdb, snowflake (lazy/no hard deps in tests)
- Layout (src/):
  - src/annot_aid/db/{base.py,file_adapter.py,duckdb_adapter.py,snowflake_adapter.py}
  - src/annot_aid/model/filtering.py
  - src/annot_aid/controller/state.py (Streamlit session state helpers)
  - app.py and pages/{1_Overview.py,2_Axis_Editor.py,3_LOINC_Matcher.py}
  - data/{biomarkers.csv,loinc.csv}
  - tests/{test_file_adapter.py,test_filtering.py}

Run (Windows-friendly)
- Optional venv: python -m venv .venv && .\.venv\Scripts\Activate.ps1
- Install: python -m pip install --upgrade pip && python -m pip install -e .
  - Extras (optional): python -m pip install -e .[duckdb,snowflake]
- Start app: python -m streamlit run app.py
  - Pages: Overview, Axis Editor, LOINC Matcher (via sidebar)
  - Demo data loaded from data/ CSVs
  - Adapter selection (experimental): add ?db=file|duckdb|snowflake to the URL; default=file

Testing
- Tooling: pytest (configured via pyproject; src/ is on PYTHONPATH)
- Install: python -m pip install --upgrade pytest
- Run: python -m pytest -q
- Coverage in this repo:
  - FileAdapter loads demo data and basic filtering works
  - Filtering logic for text, per-axis multis, and deprecated toggle

App behavior essentials (as implemented)
- Pages
  - Overview: table with biomarker description, axes filled count, selected LOINCs; select biomarker and navigate.
  - Axis Editor: six LOINC axes as multi-selects; read-only echo fields show semicolon-joined choices; Save Axes updates session state.
  - LOINC Matcher: top Selected LOINCs table + notes textarea + confidence slider + Save; bottom: filters (text, axes, deprecated) and hierarchical browser (class → component) with checkboxes syncing immediately.
- Session state keys
  - queue: biomarker DataFrame cached via adapter; idx: current row index
  - axes: {biomarker_id: {axis: [values]}}
  - selected_loincs: {biomarker_id: set(loinc_nums)}
  - saved_annotations: {biomarker_id: {axes, loincs, rationale, confidence}}

Database abstraction
- DB layer isolates data access. All adapters expose:
  - get_loinc_candidates(FilterParams)
  - get_biomarker_queue()
  - get_loinc_by_nums(nums)
- FileAdapter uses CSVs; DuckDB/Snowflake adapters are present with the same interface and lazily rely on pandas for the demo (swap to real backends later).

Coding notes
- Avoid large in-memory copies; filtering functions return views where possible (df.loc[mask]).
- Keep axis names canonical: Component, Property, Time, System, Scale, Method.
- Filtering utility centralizes text and axis-based narrowing to keep UI simple and DB-agnostic.

Next steps (suggested)
- Replace demo adapters with true DuckDB SQL and Snowflake queries; push filters server-side.
- Add persistence beyond session (e.g., write saved_annotations to file/DB).
- Expand tests: selection sync, session state transitions (can be factored into pure functions).
