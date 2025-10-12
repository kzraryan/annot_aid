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

st.title("Overview")

queue_df = adapter.get_biomarker_queue()
if queue_df.empty:
    st.warning("No biomarkers found in queue.")
    st.stop()

# KPIs at the top: total biomarkers and submitted count
total_biomarkers = len(queue_df)
submitted_count = len(st.session_state.get("saved_annotations", {}))
col_a, col_b = st.columns(2)
with col_a:
    st.metric("Total biomarkers", total_biomarkers)
with col_b:
    st.metric("Submitted", submitted_count)

# Helper to format "first + N" and tooltip text
def summarize_list(values: list[str]) -> tuple[str, str]:
    vals = [str(v) for v in values if str(v).strip()]
    if not vals:
        return "—", ""
    if len(vals) == 1:
        return vals[0], vals[0]
    return f"{vals[0]} + {len(vals) - 1}", "; ".join(vals)

# Build a single-select list using a radio control (no checkbox column)
# Create summary labels with the same info as the table
records = []
labels = []
for _, row in queue_df.iterrows():
    bid = str(row["id"])  # biomarker id
    desc = str(row.get("description", ""))
    axes_vals = S.get_axes(bid)
    loincs = sorted(S.get_selected_loincs(bid))

    # Build record (optional for future use)
    rec = {
        "ID": bid,
        "Biomarker": desc,
    }
    axis_summaries = []
    for axis in AXES:
        summary, _ = summarize_list(axes_vals.get(axis, []))
        rec[axis] = summary
        axis_summaries.append(f"{axis}: {summary}")
    loinc_summary, _ = summarize_list(loincs)
    rec["LOINCs"] = loinc_summary
    records.append(rec)

    # Compose a concise single-line label
    label = f"{desc} (ID {bid})  |  " + "  •  ".join(axis_summaries) + f"  |  LOINCs: {loinc_summary}"
    labels.append(label)

# Single list with per-row action icon buttons
current_idx = int(st.session_state.get("idx", 0))
current_idx = max(0, min(current_idx, len(records) - 1))

st.markdown("---")
st.subheader("Biomarkers")
# Table-like structure with columns: Biomarker | Axes | LOINCs | 🧭 | 🧬
header = st.columns([4, 4, 2, 0.5, 0.5])
with header[0]:
    st.markdown("**Biomarker**")
with header[1]:
    st.markdown("**Axes**")
with header[2]:
    st.markdown("**LOINCs**")
with header[3]:
    st.markdown("**🧭**")
with header[4]:
    st.markdown("**🧬**")

for i, row in queue_df.iterrows():
    bid = str(row["id"])  # biomarker id
    # Pull any persisted data into session state (once per render)
    if bid not in st.session_state.get("axes", {}):
        try:
            saved_axes = adapter.load_saved_axes(bid)
            if any(saved_axes.get(ax) for ax in AXES):
                S.set_axes(bid, saved_axes)
        except Exception:
            pass
    if bid not in st.session_state.get("selected_loincs", {}):
        try:
            loincs, confs, _ = adapter.load_saved_loincs(bid)
            if loincs:
                st.session_state["selected_loincs"].setdefault(bid, set()).update(map(str, loincs))
                st.session_state["loinc_confidences"][bid] = {str(k): int(v) for k, v in confs.items()}
        except Exception:
            pass

    axes_vals = S.get_axes(bid)
    loincs = sorted(S.get_selected_loincs(bid))
    axes_summary_parts = []
    for axis in AXES:
        vals = [v for v in axes_vals.get(axis, []) if str(v).strip()]
        if vals:
            if len(vals) == 1:
                axes_summary_parts.append(f"{axis}: {vals[0]}")
            else:
                axes_summary_parts.append(f"{axis}: {vals[0]} + {len(vals)-1}")
    axes_summary = "; ".join(axes_summary_parts) if axes_summary_parts else "—"
    loinc_summary = "—" if not loincs else (loincs[0] if len(loincs)==1 else f"{loincs[0]} + {len(loincs)-1}")

    is_sel = (i == current_idx)
    c_bio, c_axes, c_loincs, c_axisbtn, c_matchbtn = st.columns([4, 4, 2, 0.5, 0.5])
    with c_bio:
        label = f"{row['description']} (ID {bid})"
        st.markdown(f"**{label}**" if is_sel else label)
    with c_axes:
        st.markdown(axes_summary)
    with c_loincs:
        st.markdown(loinc_summary)
    with c_axisbtn:
        if st.button("🧭", key=f"axis_btn_{i}", help="Open Axis Editor for this biomarker"):
            st.session_state["idx"] = int(i)
            st.switch_page("pages/2_Axis_Editor.py")
    with c_matchbtn:
        if st.button("🧬", key=f"match_btn_{i}", help="Open LOINC Matcher for this biomarker"):
            st.session_state["idx"] = int(i)
            st.switch_page("pages/3_LOINC_Matcher.py")
