from __future__ import annotations
import streamlit as st
import pandas as pd

from annot_aid.controller import state as S
from annot_aid.db.base import AXES

S.init_state()
adapter = st.session_state.get("adapter")
if adapter is None:
    from annot_aid.db.duckdb_adapter import DuckDBAdapter
    adapter = DuckDBAdapter()
    st.session_state["adapter"] = adapter

st.title("Axis Editor")

with st.spinner("Loading biomarkers..."):
    queue_df = adapter.get_biomarker_queue()
if queue_df.empty:
    st.warning("No biomarkers found in queue.")
    st.stop()

# Biomarker selector with prev/next navigation
idx = st.session_state.get("idx", 0)
idx = max(0, min(int(idx), len(queue_df)-1))
total = len(queue_df)

nav_prev, nav_label, nav_next = st.columns([1, 3, 1])
with nav_prev:
    if st.button("← Prev", disabled=(idx == 0), use_container_width=True):
        st.session_state["idx"] = idx - 1
        st.rerun()
with nav_label:
    st.markdown(f"<div style='text-align:center; padding-top:6px;'><b>{idx + 1}</b> of <b>{total}</b></div>", unsafe_allow_html=True)
with nav_next:
    if st.button("Next →", disabled=(idx == total - 1), use_container_width=True):
        st.session_state["idx"] = idx + 1
        st.rerun()

biomarker_labels = [f"{row.BIOMARKER} (ID {row.BIOMARKER_ID})" for _, row in queue_df.iterrows()]
sel = st.selectbox(
    "Choose biomarker",
    options=list(range(total)),
    index=idx,
    format_func=lambda i: biomarker_labels[i],
)
if sel != idx:
    st.session_state["idx"] = int(sel)
    st.rerun()

biomarker = queue_df.iloc[st.session_state["idx"]]
bid = str(biomarker["BIOMARKER_ID"]) 

st.subheader(f"Biomarker: {biomarker['BIOMARKER']} (ID {bid})")

# Load any persisted axes for this biomarker into session state
try:
    saved_axes = adapter.load_saved_axes(bid)
    if any(saved_axes.get(ax) for ax in AXES):
        S.set_axes(bid, saved_axes)
except Exception:
    pass

# build options from existing LOINC table values for each axis (driven by config)
@st.cache_data(ttl=600, show_spinner=False)
def _get_axis_options(_adapter):
    loinc_df = _adapter.get_loinc_candidates()
    return {axis: sorted(loinc_df[axis].dropna().astype(str).unique().tolist()) for axis in AXES}

axis_options = _get_axis_options(adapter)

current = S.get_axes(bid)

with st.form("axes_form", clear_on_submit=False):
    cols = st.columns(2)
    selections = {}
    for i, axis in enumerate(AXES):
        with cols[i % 2]:
            options = axis_options[axis]
            sel = st.multiselect(axis, options=options, default=current.get(axis, []), key=f"axis_{axis}")
            selections[axis] = sel
    saved = st.form_submit_button("Save Axes")

if saved:
    S.set_axes(bid, selections)
    try:
        adapter.upsert_axes(bid, selections)
        st.success("Axes saved.")
    except Exception as e:
        st.error(f"Failed to save axes: {e}")
else:
    # Check for unsaved changes
    if any(sorted(selections.get(ax, [])) != sorted(current.get(ax, [])) for ax in AXES):
        st.warning("You have unsaved changes. Click **Save Axes** to persist.")

col1, col2 = st.columns(2)
with col1:
    if st.button("Back to Overview", use_container_width=True):
        st.switch_page("pages/1_Overview.py")
with col2:
    if st.button("Go to LOINC Matcher", use_container_width=True):
        st.switch_page("pages/3_LOINC_Matcher.py")
