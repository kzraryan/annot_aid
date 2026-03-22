from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import Iterable, Dict, List, Tuple

from annot_aid.config import AXES
from annot_aid.controller import state as S

# ---------- Session / adapter ----------
S.init_state()
adapter = st.session_state.get("adapter")
if adapter is None:
    from annot_aid.db.duckdb_adapter import DuckDBAdapter
    adapter = DuckDBAdapter()
    st.session_state["adapter"] = adapter

# ---------- Helpers ----------
def ensure_state():
    st.session_state.setdefault("idx", 0)
    st.session_state.setdefault("axes", {})
    st.session_state.setdefault("selected_loincs", {})
    st.session_state.setdefault("loinc_confidences", {})
    st.session_state.setdefault("saved_annotations", {})

def _listify(x: Iterable) -> List[str]:
    return [str(v).strip() for v in (x or []) if str(v).strip()]

def compact_with_hover(values: Iterable[str]) -> Tuple[str, str]:
    v = _listify(values)
    if not v:
        return "—", ""
    if len(v) == 1:
        return v[0], v[0]
    return f"{v[0]} + {len(v)-1}", ", ".join(v)

def html_chip(text: str, tooltip: str) -> str:
    tip = (tooltip or text or "—").replace("'", "&#39;").replace('"', "&quot;")
    txt = (text or "—").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f"<span title='{tip}' "
        "style='display:inline-block; max-width:100%; padding:1px 6px; "
        "margin:1px; border:1px solid #e5e7eb; border-radius:9999px; "
        "font-size:0.80em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>"
        f"{txt}</span>"
    )

# ---------- UI ----------
ensure_state()
st.title("Overview")

queue_df: pd.DataFrame = adapter.get_biomarker_queue()
if queue_df.empty:
    st.warning("No biomarkers found in queue.")
    st.stop()

# KPIs
total_biomarkers = len(queue_df)
submitted_count = len(st.session_state.get("saved_annotations", {}))
ka, kb = st.columns([1,1])
with ka: st.metric("Total biomarkers", total_biomarkers)
with kb: st.metric("Submitted", submitted_count)

st.markdown("## Biomarkers")
st.caption("Hover on any axis or LOINC chip to see all selected values.")

# Search and filter controls
filter_col, search_col = st.columns([2, 3])
with filter_col:
    status_filter = st.radio(
        "Status", ["All", "Not Started", "In Progress", "Complete"],
        horizontal=True, label_visibility="collapsed",
    )
with search_col:
    search_query = st.text_input("Search biomarkers", placeholder="Type to filter by name...", label_visibility="collapsed")

# Apply filters to queue
filtered_df = queue_df.copy()
if search_query:
    filtered_df = filtered_df[filtered_df["BIOMARKER"].astype(str).str.contains(search_query, case=False, na=False)]
if status_filter != "All":
    def _status(bid):
        has_axes = any(_listify(S.get_axes(bid).get(ax)) for ax in AXES)
        has_loincs = bool(S.get_selected_loincs(bid))
        if has_loincs:
            return "Complete"
        elif has_axes:
            return "In Progress"
        return "Not Started"
    filtered_df = filtered_df[filtered_df["BIOMARKER_ID"].astype(str).map(_status) == status_filter]

# Pagination
PAGE_SIZE = 25
total_filtered = len(filtered_df)
total_pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
current_page = st.session_state.get("overview_page", 0)
current_page = max(0, min(current_page, total_pages - 1))

pg_prev, pg_info, pg_next = st.columns([1, 3, 1])
with pg_prev:
    if st.button("← Prev Page", disabled=(current_page == 0), use_container_width=True, key="pg_prev"):
        st.session_state["overview_page"] = current_page - 1
        st.rerun()
with pg_info:
    st.markdown(
        f"<div style='text-align:center; padding-top:6px;'>Showing {total_filtered} biomarkers — Page <b>{current_page + 1}</b> of <b>{total_pages}</b></div>",
        unsafe_allow_html=True,
    )
with pg_next:
    if st.button("Next Page →", disabled=(current_page >= total_pages - 1), use_container_width=True, key="pg_next"):
        st.session_state["overview_page"] = current_page + 1
        st.rerun()

page_start = current_page * PAGE_SIZE
page_end = min(page_start + PAGE_SIZE, total_filtered)
page_df = filtered_df.iloc[page_start:page_end]

st.divider()

current_idx = int(st.session_state.get("idx", 0))
current_idx = max(0, min(current_idx, max(0, len(queue_df) - 1)))

# Column width rebalanced (14 cols total: 1 bio + 4 meta + 6 axes + 1 loincs + 2 buttons)
col_spec = [2.8, 1.0, 0.9, 0.9, 1.0, 0.9, 0.9, 0.9, 0.9, 0.9, 1.2, 1.6, 0.7, 0.7]

# Header
hdr = st.columns(col_spec)
with hdr[0]:  st.markdown("**Biomarker (ID)**")
with hdr[1]:  st.markdown("**Organ**")
with hdr[2]:  st.markdown("**Level**")
with hdr[3]:  st.markdown("**Sublevel**")
with hdr[4]:  st.markdown("**Test**")
with hdr[5]:  st.markdown("**COMP**")
with hdr[6]:  st.markdown("**PROP**")
with hdr[7]:  st.markdown("**TIME**")
with hdr[8]:  st.markdown("**SYSTEM**")
with hdr[9]:  st.markdown("**SCALE**")
with hdr[10]: st.markdown("**METHOD**")
with hdr[11]: st.markdown("**LOINCs**")
with hdr[12]: st.markdown("**Axes**")
with hdr[13]: st.markdown("**Match**")

st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

AXIS_EDITOR_PAGE = "pages/2_Axis_Editor.py"
LOINC_MATCHER_PAGE = "pages/3_LOINC_Matcher.py"
_hydration_warning = st.empty()

for i, row in page_df.iterrows():
    bid         = str(row["BIOMARKER_ID"])
    name        = str(row.get("BIOMARKER", "")) or "—"
    organ       = str(row.get("ORGAN", "")) or "—"
    level       = str(row.get("LEVEL", "")) or "—"
    sublevel    = str(row.get("SUBLEVEL", "")) or "—"
    test_method = str(row.get("TEST_METHOD", "")) or "—"

    # Hydrate once
    if bid not in st.session_state["axes"]:
        try:
            saved_axes = adapter.load_saved_axes(bid)
            if any(_listify(saved_axes.get(ax)) for ax in AXES):
                S.set_axes(bid, saved_axes)
        except Exception as e:
            if "_hydration_errors" not in st.session_state:
                st.session_state["_hydration_errors"] = []
            st.session_state["_hydration_errors"].append(f"axes for {bid}: {e}")
    if bid not in st.session_state["selected_loincs"]:
        try:
            loincs, confs, _ = adapter.load_saved_loincs(bid)
            if loincs:
                st.session_state["selected_loincs"].setdefault(bid, set()).update(map(str, loincs))
                st.session_state["loinc_confidences"][bid] = {str(k): int(v) for k, v in (confs or {}).items()}
        except Exception as e:
            if "_hydration_errors" not in st.session_state:
                st.session_state["_hydration_errors"] = []
            st.session_state["_hydration_errors"].append(f"loincs for {bid}: {e}")

    axes_vals: Dict[str, List[str]] = S.get_axes(bid) or {}
    loincs = sorted(S.get_selected_loincs(bid) or [])

    # Chips
    axis_chip_html: Dict[str, str] = {}
    for ax in AXES:
        disp, tip = compact_with_hover(axes_vals.get(ax))
        axis_chip_html[ax] = html_chip(disp, tip if tip else disp)

    loinc_disp, loinc_tip = compact_with_hover(loincs)
    loinc_html = html_chip(loinc_disp, loinc_tip if loinc_tip else loinc_disp)

    with st.container(border=True):
        cols = st.columns(col_spec)

        with cols[0]:
            title = f"**{name}**  \n<span style='color:gray; font-size:0.85em;'>ID {bid}</span>"
            st.markdown(title, unsafe_allow_html=True)

        with cols[1]:  st.markdown(organ)
        with cols[2]:  st.markdown(level)
        with cols[3]:  st.markdown(sublevel)
        with cols[4]:  st.markdown(test_method)

        with cols[5]:  st.markdown(axis_chip_html.get("COMPONENT", "—"),  unsafe_allow_html=True)
        with cols[6]:  st.markdown(axis_chip_html.get("PROPERTY", "—"),   unsafe_allow_html=True)
        with cols[7]:  st.markdown(axis_chip_html.get("TIME_ASPCT", "—"), unsafe_allow_html=True)
        with cols[8]:  st.markdown(axis_chip_html.get("SYSTEM", "—"),     unsafe_allow_html=True)
        with cols[9]:  st.markdown(axis_chip_html.get("SCALE_TYP", "—"),  unsafe_allow_html=True)
        with cols[10]: st.markdown(axis_chip_html.get("METHOD_TYP", "—"), unsafe_allow_html=True)

        with cols[11]:
            st.markdown(loinc_html, unsafe_allow_html=True)

        # Axis editor button
        with cols[12]:
            if st.button("Axes", key=f"axis_btn_{i}", help="Edit LOINC axis filters", use_container_width=True):
                st.session_state["idx"] = int(i)
                st.session_state["current_biomarker_id"] = bid
                st.switch_page(AXIS_EDITOR_PAGE)

        # LOINC matcher button
        with cols[13]:
            if st.button("Match", key=f"loinc_btn_{i}", help="Match LOINC codes", use_container_width=True):
                st.session_state["idx"] = int(i)
                st.session_state["current_biomarker_id"] = bid
                st.switch_page(LOINC_MATCHER_PAGE)

# Show hydration errors if any occurred
if st.session_state.get("_hydration_errors"):
    _hydration_warning.warning(f"Some saved data could not be loaded ({len(st.session_state['_hydration_errors'])} errors). Check database connection.")
    del st.session_state["_hydration_errors"]
