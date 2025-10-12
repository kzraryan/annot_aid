from __future__ import annotations
import streamlit as st
import pandas as pd

from annot_aid.controller import state as S
from annot_aid.db.base import AXES, FilterParams
from annot_aid.model.filtering import AXIS_COLS, apply_filters

S.init_state()
adapter = st.session_state.get("adapter")
if adapter is None:
    from annot_aid.db.file_adapter import FileAdapter
    adapter = FileAdapter()
    st.session_state["adapter"] = adapter

st.title("LOINC Matcher")

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

# Pull any persisted selections into session state
try:
    loincs, confs, rationale = adapter.load_saved_loincs(bid)
    if loincs:
        st.session_state["selected_loincs"].setdefault(bid, set()).update(map(str, loincs))
    if confs:
        st.session_state["loinc_confidences"][bid] = {str(k): int(v) for k, v in confs.items()}
    # store rationale for default
    st.session_state.setdefault("saved_annotations", {}).setdefault(bid, {}).setdefault("rationale", rationale or "")
except Exception:
    pass

# Top half: Selected LOINCs, notes, per-LOINC confidence, save
st.markdown("### Selected LOINCs")
sel_set = S.get_selected_loincs(bid)
selected_df = adapter.get_loinc_by_nums(sorted(sel_set))
if not selected_df.empty:
    show_cols = ["loinc_num", "long_name", "component", "property", "time", "system", "scale", "method", "class", "status"]
    show_cols = [c for c in show_cols if c in selected_df.columns]
    confs = S.get_loinc_confidences(bid)
    selected_df = selected_df.copy()
    selected_df["Confidence"] = selected_df["loinc_num"].astype(str).map(lambda n: int(confs.get(str(n), 100)))
    edited = st.data_editor(
        selected_df[show_cols + ["Confidence"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Confidence": st.column_config.NumberColumn(min_value=1, max_value=100, step=1, help="Confidence 1–100")
        },
        key="selected_loincs_editor",
    )
    # Persist any confidence edits back to state
    if "Confidence" in edited.columns:
        for _, r in edited.iterrows():
            S.set_loinc_confidence(bid, str(r["loinc_num"]), int(r["Confidence"]))
else:
    st.info("No LOINCs selected yet. Use the browser below to add.")

saved = st.session_state.get("saved_annotations", {}).get(bid, {})
notes_default = saved.get("rationale", "")
notes = st.text_area("Rationale/Notes", value=notes_default)

if st.button("Save Selection for this Biomarker"):
    axes_vals = S.get_axes(bid)
    S.save_annotation(bid, axes_vals, sorted(sel_set), notes)
    # persist via adapter in two tables
    try:
        adapter.upsert_axes(bid, axes_vals)
    except Exception:
        pass
    try:
        confs = S.get_loinc_confidences(bid)
        # keep only selected ones
        confs = {k: v for k, v in confs.items() if k in sel_set}
        adapter.upsert_loincs(bid, confs, notes)
    except Exception:
        pass
    st.success("Selection saved.")

st.markdown("---")

# Bottom half: Filters and hierarchical browser
st.markdown("### Candidate Browser")

axes_vals = S.get_axes(bid)

col_search, col_depr = st.columns([3, 1])
with col_search:
    text = st.text_input("Free-text search across key fields")
with col_depr:
    include_deprecated = st.toggle("Include deprecated", value=False)

f_cols = st.columns(3)
with f_cols[0]:
    comp = st.multiselect("Component", options=sorted(adapter.get_loinc_candidates().component.dropna().astype(str).unique().tolist()))
    prop = st.multiselect("Property", options=sorted(adapter.get_loinc_candidates().property.dropna().astype(str).unique().tolist()))
with f_cols[1]:
    time = st.multiselect("Time", options=sorted(adapter.get_loinc_candidates().time.dropna().astype(str).unique().tolist()))
    system = st.multiselect("System", options=sorted(adapter.get_loinc_candidates().system.dropna().astype(str).unique().tolist()))
with f_cols[2]:
    scale = st.multiselect("Scale", options=sorted(adapter.get_loinc_candidates().scale.dropna().astype(str).unique().tolist()))
    method = st.multiselect("Method", options=sorted(adapter.get_loinc_candidates().method.dropna().astype(str).unique().tolist()))

axes_filter = {
    "Component": comp,
    "Property": prop,
    "Time": time,
    "System": system,
    "Scale": scale,
    "Method": method,
}

base = adapter.get_loinc_candidates()
filtered = apply_filters(base, text=text, axes=axes_filter, include_deprecated=include_deprecated)

st.caption(f"{len(filtered)} candidate terms match filters")

# Hierarchical browser: by class -> component
for class_name, df_c in filtered.groupby("class", dropna=False):
    with st.expander(f"Class: {class_name if pd.notna(class_name) else '(none)'} ({len(df_c)})", expanded=False):
        for comp_name, df_comp in df_c.groupby("component", dropna=False):
            with st.expander(f"Component: {comp_name if pd.notna(comp_name) else '(none)'} ({len(df_comp)})", expanded=False):
                for _, r in df_comp.iterrows():
                    label = f"{r['long_name']} · {r['loinc_num']}"
                    key = f"loinc_{r['loinc_num']}"
                    checked = str(r["loinc_num"]) in sel_set
                    full_info = (
                        f"LOINC: {r['loinc_num']}\n"
                        f"Long name: {r.get('long_name','')}\n"
                        f"Class: {r.get('class','')}\n"
                        f"Component: {r.get('component','')}\n"
                        f"Property: {r.get('property','')}\n"
                        f"Time: {r.get('time','')}\n"
                        f"System: {r.get('system','')}\n"
                        f"Scale: {r.get('scale','')}\n"
                        f"Method: {r.get('method','')}\n"
                        f"Status: {r.get('status','')}"
                    )
                    new_val = st.checkbox(label, value=checked, key=key, help=full_info)
                    if new_val != checked:
                        S.toggle_loinc(bid, str(r["loinc_num"]), new_val)
                        st.rerun()
