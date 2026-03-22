from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol, Tuple
import pandas as pd

from ..config import AXES


@dataclass(frozen=True)
class FilterParams:
    text: str = ""
    axes: Dict[str, List[str]] = None
    include_deprecated: bool = False


class DBAdapter(Protocol):
    """Abstract DB adapter interface to keep app database-agnostic.
    """

    def get_loinc_candidates(self, params: FilterParams | None = None) -> pd.DataFrame:
        """Return LOINC candidates as a DataFrame with standard columns.

        Required columns: loinc_num, long_common_name, component, property, time, system, scale, method, class, status, deprecated
        """
        ...

    def get_biomarker_queue(self) -> pd.DataFrame:
        """Return biomarker queue with columns: id, description"""
        ...

    def get_loinc_by_nums(self, nums: Iterable[str]) -> pd.DataFrame:
        """Return subset of LOINC table for specific loinc_num values."""
        ...

    # --- Persistence API ---
    def upsert_axes(self, biomarker_id: str, axes: Dict[str, List[str]]) -> None:
        """Replace axes rows for biomarker_id in persistent store."""
        ...

    def upsert_loincs(self, biomarker_id: str, loinc_conf: Dict[str, int], rationale: str) -> None:
        """Replace selected LOINCs for biomarker_id with confidences and rationale (1–100)."""
        ...

    def load_saved_axes(self, biomarker_id: str) -> Dict[str, List[str]]:
        """Load persisted axes for biomarker_id."""
        ...

    def load_saved_loincs(self, biomarker_id: str) -> Tuple[List[str], Dict[str, int], str]:
        """Return (loincs, confidences_map, rationale) for biomarker_id."""
        ...


def normalize_axes_dict(axes: Optional[Dict[str, Iterable[str]]]) -> Dict[str, List[str]]:
    axes = axes or {}
    out: Dict[str, List[str]] = {}
    for k in AXES:
        v = axes.get(k) or []
        out[k] = list(dict.fromkeys([str(x).strip() for x in v if str(x).strip()]))
    return out
