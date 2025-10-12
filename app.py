from __future__ import annotations
import os
import streamlit as st
import pandas as pd

from annot_aid.db.file_adapter import FileAdapter
from annot_aid.db.base import FilterParams, AXES
from annot_aid.controller.state import init_state


st.set_page_config(page_title="annot_aid – Biomarker → LOINC", layout="wide")
init_state()

# Choose adapter (database-agnostic). For demo, default to file adapter.
adapter_name = st.query_params.get("db", "file") if hasattr(st, 'query_params') else "file"
adapter_name = (adapter_name or "file").lower()
if adapter_name == "file":
    adapter = FileAdapter()
elif adapter_name == "duckdb":
    try:
        from annot_aid.db.duckdb_adapter import DuckDBAdapter
        adapter = DuckDBAdapter()
    except Exception as e:
        st.warning("DuckDB not available; falling back to file adapter")
        adapter = FileAdapter()
elif adapter_name == "snowflake":
    try:
        from annot_aid.db.snowflake_adapter import SnowflakeAdapter
        adapter = SnowflakeAdapter()  # implementation likely placeholder
    except Exception:
        st.warning("Snowflake adapter not available; falling back to file adapter")
        adapter = FileAdapter()
else:
    st.warning(f"Unknown adapter '{adapter_name}', defaulting to file adapter")
    adapter = FileAdapter()

st.session_state.setdefault("adapter", adapter)  # store to reuse across pages

st.title("annot_aid – Biomarker → LOINC Annotation")
st.write("Use the sidebar to navigate between Overview, Axis Editor, and LOINC Matcher.")

# Display small summary from data
queue_df = adapter.get_biomarker_queue()
loinc_df = adapter.get_loinc_candidates(FilterParams())

st.subheader("Dataset Snapshot")
col1, col2 = st.columns(2)
with col1:
    st.caption("Biomarker queue (first 5)")
    st.dataframe(queue_df.head(5), use_container_width=True)
with col2:
    st.caption("LOINC terms (first 5)")
    show_cols = [c for c in ["loinc_num", "long_name", "component", "property", "time", "system", "scale", "method", "class", "status", "deprecated"] if c in loinc_df.columns]
    st.dataframe(loinc_df.head(5)[show_cols], use_container_width=True)

st.info("Navigate to pages via the sidebar ➜")
