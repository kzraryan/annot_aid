from __future__ import annotations
import streamlit as st

from annot_aid.controller.state import init_state
from annot_aid.db.duckdb_adapter import DuckDBAdapter
from annot_aid.config import AXES
from annot_aid.controller import state as S

st.set_page_config(page_title="annot_aid – Biomarker → LOINC", layout="wide")
init_state()
adapter = DuckDBAdapter()
st.session_state.setdefault("adapter", adapter)

st.title("annot_aid – Biomarker → LOINC Annotation")

# Summary KPIs
with st.spinner("Loading data..."):
    queue_df = adapter.get_biomarker_queue()

total = len(queue_df)
axes_filled = sum(
    1 for _, row in queue_df.iterrows()
    if any(S.get_axes(str(row["BIOMARKER_ID"])).get(ax) for ax in AXES)
)
loincs_matched = sum(
    1 for _, row in queue_df.iterrows()
    if S.get_selected_loincs(str(row["BIOMARKER_ID"]))
)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("Total Biomarkers", total)
with k2:
    st.metric("Axes Filled", axes_filled)
with k3:
    st.metric("LOINCs Matched", loincs_matched)
with k4:
    pct = int(loincs_matched / total * 100) if total else 0
    st.metric("Progress", f"{pct}%")

st.divider()

# Workflow guide
st.markdown("""
### Annotation Workflow

1. **Overview** — Browse the biomarker queue, see current progress, jump to any biomarker
2. **Axis Editor** — Narrow LOINC candidates by selecting axis values (Component, Property, System, etc.)
3. **LOINC Matcher** — Search for and select matching LOINC codes, set confidence, add rationale
""")

if st.button("Get Started →", type="primary", use_container_width=True):
    st.switch_page("pages/1_Overview.py")
