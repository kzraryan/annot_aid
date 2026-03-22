from __future__ import annotations
import streamlit as st
import pandas as pd

from annot_aid.controller import state as S
from annot_aid.db.base import AXES, FilterParams
from annot_aid.model.filtering import AXIS_COLS, apply_filters

S.init_state()
adapter = st.session_state.get("adapter")
if adapter is None:
    from annot_aid.db.duckdb_adapter import DuckDBAdapter
    adapter = DuckDBAdapter()
    st.session_state["adapter"] = adapter

st.title("LOINC Matcher")

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
    if st.button("← Prev", disabled=(idx == 0), use_container_width=True, key="nav_prev"):
        st.session_state["idx"] = idx - 1
        st.rerun()
with nav_label:
    st.markdown(f"<div style='text-align:center; padding-top:6px;'><b>{idx + 1}</b> of <b>{total}</b></div>", unsafe_allow_html=True)
with nav_next:
    if st.button("Next →", disabled=(idx == total - 1), use_container_width=True, key="nav_next"):
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

# Pull any persisted axes into session state (for filter pre-fill)
try:
    saved_axes = adapter.load_saved_axes(bid)
    if any(saved_axes.get(ax) for ax in AXES):
        S.set_axes(bid, saved_axes)
except Exception:
    pass

# Pull any persisted LOINCs into session state
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
# Include manually-added codes not found in the DB
found_nums = set(selected_df["LOINC_NUM"].astype(str)) if not selected_df.empty else set()
missing_nums = sel_set - found_nums
if missing_nums:
    missing_rows = pd.DataFrame({"LOINC_NUM": sorted(missing_nums), "LONG_COMMON_NAME": "(not in local DB)"})
    selected_df = pd.concat([selected_df, missing_rows], ignore_index=True)

if not selected_df.empty:
    confs = S.get_loinc_confidences(bid)
    for _, loinc_row in selected_df.iterrows():
        lnum = str(loinc_row["LOINC_NUM"])
        lname = str(loinc_row.get("LONG_COMMON_NAME", ""))
        lcomp = str(loinc_row.get("COMPONENT", "")) if "COMPONENT" in selected_df.columns else ""
        c_info, c_conf, c_remove = st.columns([5, 2, 1])
        with c_info:
            st.markdown(f"**{lnum}** — {lname}")
            if lcomp:
                st.caption(f"Component: {lcomp}")
        with c_conf:
            conf_val = int(confs.get(lnum, 100))
            new_conf = st.number_input(
                "Confidence", min_value=1, max_value=100, value=conf_val,
                key=f"conf_{lnum}", label_visibility="collapsed",
                help="Confidence 1–100",
            )
            if new_conf != conf_val:
                S.set_loinc_confidence(bid, lnum, int(new_conf))
        with c_remove:
            if st.button("✕", key=f"rm_{lnum}", help=f"Remove {lnum}"):
                S.toggle_loinc(bid, lnum, False)
                st.rerun()
else:
    st.info("No LOINCs selected yet. Use the browser below to add.")

saved = st.session_state.get("saved_annotations", {}).get(bid, {})
notes_default = saved.get("rationale", "")
notes = st.text_area("Rationale/Notes", value=notes_default)

if st.button("Save Selection for this Biomarker"):
    if not sel_set:
        st.warning("No LOINCs selected. Please add at least one LOINC code before saving.")
    else:
        axes_vals = S.get_axes(bid)
        S.save_annotation(bid, axes_vals, sorted(sel_set), notes)
        # persist via adapter in two tables
        errors = []
        try:
            adapter.upsert_axes(bid, axes_vals)
        except Exception as e:
            errors.append(f"Axes: {e}")
        try:
            confs = S.get_loinc_confidences(bid)
            # keep only selected ones
            confs = {k: v for k, v in confs.items() if k in sel_set}
            adapter.upsert_loincs(bid, confs, notes)
        except Exception as e:
            errors.append(f"LOINCs: {e}")
        if errors:
            st.error(f"Failed to save: {'; '.join(errors)}")
        else:
            st.success("Selection saved.")

# Bottom half: Browse LOINC codes
st.markdown("### Browse & Add LOINC Codes")

st.markdown("""
Browse the official LOINC database to find the right codes for this biomarker:

🔗 **[Open LOINC Search](https://loinc.org/search/)** (opens in new tab)  
🌲 **[Open LOINC Tree Browser](https://loinc.org/tree/)** (requires free LOINC account)
""")

st.markdown("---")

# Manual entry section
col1, col2 = st.columns([3, 1])
with col1:
    loinc_input = st.text_input(
        "Add LOINC Code", 
        placeholder="e.g., 1000-9",
        help="Enter the LOINC code from the website above"
    )
with col2:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)  # Spacer to align button
    add_button = st.button("➕ Add Code", use_container_width=True)

# Handle confirming an unknown LOINC code from a previous click
if st.session_state.get("_confirm_unknown_loinc"):
    code = st.session_state.pop("_confirm_unknown_loinc")
    S.toggle_loinc(bid, code, True)
    st.rerun()

if add_button and loinc_input:
    loinc_code = loinc_input.strip()
    if loinc_code:
        if loinc_code in sel_set:
            st.info(f"{loinc_code} is already selected.")
        else:
            # Try to find this code in our database
            try:
                found_df = adapter.get_loinc_by_nums([loinc_code])
                if not found_df.empty:
                    S.toggle_loinc(bid, loinc_code, True)
                    st.success(f"✓ Added {loinc_code}: {found_df.iloc[0]['LONG_COMMON_NAME']}")
                    st.rerun()
                else:
                    st.session_state["_pending_unknown_loinc"] = loinc_code
            except Exception as e:
                st.error(f"Error validating code: {e}")

if st.session_state.get("_pending_unknown_loinc"):
    pending_code = st.session_state["_pending_unknown_loinc"]
    st.warning(f"⚠️ LOINC code '{pending_code}' not found in the local database. Add anyway?")
    col_y, col_n = st.columns(2)
    with col_y:
        if st.button("Yes, add it anyway"):
            st.session_state.pop("_pending_unknown_loinc")
            st.session_state["_confirm_unknown_loinc"] = pending_code
            st.rerun()
    with col_n:
        if st.button("Cancel"):
            st.session_state.pop("_pending_unknown_loinc")
            st.rerun()

st.markdown("---")

# Optional: Simple search in local database
with st.expander("🔍 Search Local LOINC Database (Optional)", expanded=False):
    st.caption("Quick search in your local LOINC database. For comprehensive browsing, use the links above.")
    search_text = st.text_input("Search by name or code", key="local_search")
    
    if search_text:
        with st.spinner("Searching..."):
            base = adapter.get_loinc_candidates()
        q = search_text.lower()
        # Simple text search
        mask = (
            base["LOINC_NUM"].astype(str).str.contains(search_text, case=False, na=False) |
            base["LONG_COMMON_NAME"].astype(str).str.contains(search_text, case=False, na=False) |
            base["COMPONENT"].astype(str).str.contains(search_text, case=False, na=False)
        )
        results = base[mask].copy()
        # Relevance ranking: exact LOINC_NUM match > COMPONENT match > name match
        results["_score"] = (
            (results["LOINC_NUM"].astype(str).str.lower() == q).astype(int) * 3 +
            results["COMPONENT"].astype(str).str.contains(search_text, case=False, na=False).astype(int) * 2 +
            results["LONG_COMMON_NAME"].astype(str).str.contains(search_text, case=False, na=False).astype(int)
        )
        results = results.sort_values("_score", ascending=False).head(50)
        
        if not results.empty:
            st.caption(f"Showing {len(results)} results (max 50)")
            
            # Show as a simple table with an "Add" button for each
            for _, row in results.iterrows():
                col_a, col_b = st.columns([5, 1])
                with col_a:
                    st.markdown(
                        f"**{row['LOINC_NUM']}** - {row['LONG_COMMON_NAME']}"
                    )
                    st.caption(f"Component: {row.get('COMPONENT', 'N/A')} | Class: {row.get('CLASS', 'N/A')}")
                with col_b:
                    if str(row["LOINC_NUM"]) in sel_set:
                        st.button("✓ Added", key=f"added_{row['LOINC_NUM']}", disabled=True, use_container_width=True)
                    else:
                        if st.button("➕ Add", key=f"add_{row['LOINC_NUM']}", use_container_width=True):
                            S.toggle_loinc(bid, str(row["LOINC_NUM"]), True)
                            st.toast(f"Added {row['LOINC_NUM']}")
                            st.rerun()
                st.markdown("---")
        else:
            st.info("No results found. Try different search terms or use the LOINC website above.")

# Navigation
st.divider()
nav1, nav2 = st.columns(2)
with nav1:
    if st.button("Back to Overview", use_container_width=True):
        st.switch_page("pages/1_Overview.py")
with nav2:
    if st.button("Go to Axis Editor", use_container_width=True):
        st.switch_page("pages/2_Axis_Editor.py")
