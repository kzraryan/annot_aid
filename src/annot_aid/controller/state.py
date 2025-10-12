from __future__ import annotations
from typing import Dict, List, Set, Any
import streamlit as st

from ..db.base import AXES


def init_state():
    st.session_state.setdefault("queue", [])
    st.session_state.setdefault("idx", 0)
    st.session_state.setdefault("axes", {})  # biomarker_id -> {axis: [values]}
    st.session_state.setdefault("selected_loincs", {})  # biomarker_id -> set(loinc_num)
    st.session_state.setdefault("loinc_confidences", {})  # biomarker_id -> {loinc_num: int 1-100}
    st.session_state.setdefault("saved_annotations", {})  # biomarker_id -> dict


def get_current_biomarker_id(queue) -> str | None:
    if not queue:
        return None
    i = st.session_state.get("idx", 0)
    i = max(0, min(int(i), len(queue) - 1))
    return str(queue[i]["id"]) if isinstance(queue, list) else str(queue.iloc[i]["id"])  # df or list


def get_axes(biomarker_id: str) -> Dict[str, List[str]]:
    axes = st.session_state["axes"].get(biomarker_id, {})
    return {k: list(axes.get(k, [])) for k in AXES}


def set_axes(biomarker_id: str, axes_values: Dict[str, List[str]]):
    st.session_state["axes"][biomarker_id] = {k: list(axes_values.get(k, [])) for k in AXES}


def get_selected_loincs(biomarker_id: str) -> Set[str]:
    return set(st.session_state["selected_loincs"].get(biomarker_id, set()))


def get_loinc_confidences(biomarker_id: str) -> Dict[str, int]:
    return dict(st.session_state["loinc_confidences"].get(biomarker_id, {}))


def set_loinc_confidence(biomarker_id: str, loinc_num: str, confidence: int):
    confidence = int(max(1, min(100, confidence)))
    confid = st.session_state["loinc_confidences"].setdefault(biomarker_id, {})
    confid[str(loinc_num)] = confidence


def toggle_loinc(biomarker_id: str, loinc_num: str, checked: bool):
    s = get_selected_loincs(biomarker_id)
    loinc_num = str(loinc_num)
    if checked:
        s.add(loinc_num)
        # initialize default confidence 100 if not set
        confid = st.session_state["loinc_confidences"].setdefault(biomarker_id, {})
        confid.setdefault(loinc_num, 100)
    else:
        s.discard(loinc_num)
        # remove confidence if present
        confid = st.session_state["loinc_confidences"].get(biomarker_id, {})
        if loinc_num in confid:
            del confid[loinc_num]
    st.session_state["selected_loincs"][biomarker_id] = s


def save_annotation(biomarker_id: str, axes_values: Dict[str, List[str]], loincs: List[str], notes: str):
    # Persist axes, selected loincs, per-loinc confidences, and rationale
    loinc_confs = get_loinc_confidences(biomarker_id)
    # Ensure we only keep confidences for currently selected loincs
    loinc_confs = {str(k): int(max(1, min(100, v))) for k, v in loinc_confs.items() if str(k) in set(map(str, loincs))}
    st.session_state["saved_annotations"][biomarker_id] = {
        "axes": {k: list(axes_values.get(k, [])) for k in AXES},
        "loincs": list(map(str, loincs)),
        "loinc_confidences": loinc_confs,
        "rationale": notes,
    }
