from __future__ import annotations
import streamlit as st
import pandas as pd

from annot_aid.controller import state as S
from annot_aid.db.base import AXES

S.init_state()
adapter = st.session_state.get("adapter")
if adapter is None:
    from annot_aid.db.file_adapter import FileAdapter
    adapter = FileAdapter()
    st.session_state["adapter"] = adapter

st.title("Axis Editor")

queue_df = adapter.get_biomarker_queue()
if queue_df.empty:
    st.warning("No biomarkers found in queue.")
    st.stop()

# Biomarker selector (dropdown)
idx = st.session_state.get("idx", 0)
idx = max(0, min(int(idx), len(queue_df)-1))
biomarker_labels = [f"{row.description} (ID {row.id})" for _, row in queue_df.iterrows()]
sel = st.selectbox(
    "Choose biomarker",
    options=list(range(len(queue_df))),
    index=idx,
    format_func=lambda i: biomarker_labels[i],
)
if sel != idx:
    st.session_state["idx"] = int(sel)
    st.rerun()

biomarker = queue_df.iloc[st.session_state["idx"]]
bid = str(biomarker["id"]) 

st.subheader(f"Biomarker: {biomarker['description']} (ID {bid})")

# Load any persisted axes for this biomarker into session state
try:
    saved_axes = adapter.load_saved_axes(bid)
    if any(saved_axes.get(ax) for ax in AXES):
        S.set_axes(bid, saved_axes)
except Exception:
    pass

# build options from existing LOINC table values for each axis
loinc_df = adapter.get_loinc_candidates()
axis_options = {
    "Component": sorted(loinc_df["component"].dropna().astype(str).unique().tolist()),
    "Property": sorted(loinc_df["property"].dropna().astype(str).unique().tolist()),
    "Time": sorted(loinc_df["time"].dropna().astype(str).unique().tolist()),
    "System": sorted(loinc_df["system"].dropna().astype(str).unique().tolist()),
    "Scale": sorted(loinc_df["scale"].dropna().astype(str).unique().tolist()),
    "Method": sorted(loinc_df["method"].dropna().astype(str).unique().tolist()),
}

current = S.get_axes(bid)

with st.form("axes_form", clear_on_submit=False):
    cols = st.columns(2)
    selections = {}
    for i, axis in enumerate(AXES):
        with cols[i % 2]:
            options = axis_options[axis]
            sel = st.multiselect(axis, options=options, default=current.get(axis, []), key=f"axis_{axis}")
            selections[axis] = sel
            st.text_input(f"Selected {axis}", value="; ".join(sel), disabled=True, key=f"axis_ro_{axis}")
    saved = st.form_submit_button("Save Axes")

if saved:
    S.set_axes(bid, selections)
    try:
        adapter.upsert_axes(bid, selections)
    except Exception:
        pass
    st.success("Axes saved.")

col1, col2 = st.columns(2)
with col1:
    if st.button("Back to Overview"):
        st.switch_page("pages/1_Overview.py")
with col2:
    if st.button("Go to LOINC Matcher"):
        st.switch_page("pages/3_LOINC_Matcher.py")
