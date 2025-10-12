from __future__ import annotations
from typing import Dict, Iterable, List, Optional
import pandas as pd

AXIS_COLS = {
    "Component": "component",
    "Property": "property",
    "Time": "time",
    "System": "system",
    "Scale": "scale",
    "Method": "method",
}

SEARCH_COLS = [
    "long_name",
    "component",
    "system",
    "property",
    "method",
    "loinc_num",
]


def _contains_any(series: pd.Series, values: List[str]) -> pd.Series:
    if not values:
        return pd.Series([True] * len(series), index=series.index)
    s = series.fillna("").astype(str).str.lower()
    vals = [v.lower() for v in values if v]
    mask = False
    for v in vals:
        mask = mask | s.str.contains(fr"\b{pd.re.escape(v)}\b", regex=True)
    return mask


def apply_filters(df: pd.DataFrame, text: str = "", axes: Optional[Dict[str, List[str]]] = None, include_deprecated: bool = False) -> pd.DataFrame:
    axes = axes or {}
    mask = pd.Series([True] * len(df), index=df.index)
    # Deprecated toggle
    if not include_deprecated and "deprecated" in df.columns:
        mask &= ~df["deprecated"].fillna(False).astype(bool)
    # Text search across columns
    if text:
        t = str(text).strip().lower()
        if t:
            sub = False
            for c in SEARCH_COLS:
                if c in df.columns:
                    sub = sub | df[c].fillna("").astype(str).str.lower().str.contains(t)
            mask &= sub
    # Axis-based filters
    for axis_name, col in AXIS_COLS.items():
        vals = axes.get(axis_name) or []
        if vals and col in df.columns:
            mask &= df[col].fillna("").astype(str).isin(vals)
    # Return a view without copying all columns unnecessarily
    return df.loc[mask]
