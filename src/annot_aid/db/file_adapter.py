from __future__ import annotations
from pathlib import Path
from typing import Iterable, Optional
import pandas as pd

from .base import DBAdapter, FilterParams, normalize_axes_dict
from ..model.filtering import apply_filters


class FileAdapter:
    """File-backed adapter using small demo CSVs/Parquet.

    Expects data/biomarkers.csv and data/loinc_small.csv in repo root.
    Also persists user data in two CSV 'tables':
      - data/saved_axes.csv: biomarker_id, axis, value
      - data/saved_loincs.csv: biomarker_id, loinc_num, confidence, rationale
    """

    def __init__(self, root: Optional[str | Path] = None):
        self.root = Path(root or ".").resolve()
        self._bio = None
        self._loinc = None
        self._axes_path = self.root / "data" / "saved_axes.csv"
        self._loincs_path = self.root / "data" / "saved_loincs.csv"

    @property
    def bio(self) -> pd.DataFrame:
        if self._bio is None:
            self._bio = pd.read_csv(self.root / "data" / "biomarkers.csv")
        return self._bio

    @property
    def loinc(self) -> pd.DataFrame:
        if self._loinc is None:
            self._loinc = pd.read_csv(self.root / "data" / "loinc_small.csv")
        return self._loinc

    def get_loinc_candidates(self, params: FilterParams | None = None) -> pd.DataFrame:
        df = self.loinc
        if params is None:
            return df
        return apply_filters(df, text=params.text, axes=normalize_axes_dict(params.axes), include_deprecated=params.include_deprecated)

    def get_biomarker_queue(self) -> pd.DataFrame:
        return self.bio

    def get_loinc_by_nums(self, nums: Iterable[str]) -> pd.DataFrame:
        s = set(str(x) for x in nums)
        if not s:
            return self.loinc.iloc[0:0]
        return self.loinc[self.loinc["loinc_num"].astype(str).isin(s)]

    # --- Persistence helpers (CSV-backed) ---
    def _read_axes(self) -> pd.DataFrame:
        if not self._axes_path.exists():
            return pd.DataFrame(columns=["biomarker_id", "axis", "value"])  # empty
        return pd.read_csv(self._axes_path)

    def _read_loincs(self) -> pd.DataFrame:
        if not self._loincs_path.exists():
            return pd.DataFrame(columns=["biomarker_id", "loinc_num", "confidence", "rationale"])  # empty
        df = pd.read_csv(self._loincs_path)
        # coerce types
        if not df.empty:
            df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(100).astype(int)
            df["loinc_num"] = df["loinc_num"].astype(str)
            df["biomarker_id"] = df["biomarker_id"].astype(str)
        return df

    def upsert_axes(self, biomarker_id: str, axes: dict[str, list[str]]) -> None:
        biomarker_id = str(biomarker_id)
        axes_df = self._read_axes()
        # remove existing rows for this biomarker
        if not axes_df.empty:
            axes_df = axes_df[axes_df["biomarker_id"].astype(str) != biomarker_id]
        # build new rows
        rows = []
        for axis, values in normalize_axes_dict(axes).items():
            for v in values:
                rows.append({"biomarker_id": biomarker_id, "axis": axis, "value": v})
        new_df = pd.DataFrame(rows, columns=["biomarker_id", "axis", "value"]) if rows else pd.DataFrame(columns=["biomarker_id", "axis", "value"]) 
        out = pd.concat([axes_df, new_df], ignore_index=True)
        out.to_csv(self._axes_path, index=False)

    def upsert_loincs(self, biomarker_id: str, loinc_conf: dict[str, int], rationale: str) -> None:
        biomarker_id = str(biomarker_id)
        loinc_df = self._read_loincs()
        # remove existing rows for this biomarker
        if not loinc_df.empty:
            loinc_df = loinc_df[loinc_df["biomarker_id"].astype(str) != biomarker_id]
        rows = []
        for ln, conf in loinc_conf.items():
            rows.append({
                "biomarker_id": biomarker_id,
                "loinc_num": str(ln),
                "confidence": int(max(1, min(100, int(conf)))) if pd.notna(conf) else 100,
                "rationale": rationale or "",
            })
        new_df = pd.DataFrame(rows, columns=["biomarker_id", "loinc_num", "confidence", "rationale"]) if rows else pd.DataFrame(columns=["biomarker_id", "loinc_num", "confidence", "rationale"]) 
        out = pd.concat([loinc_df, new_df], ignore_index=True)
        out.to_csv(self._loincs_path, index=False)

    def load_saved_axes(self, biomarker_id: str) -> dict[str, list[str]]:
        biomarker_id = str(biomarker_id)
        df = self._read_axes()
        if df.empty:
            return {k: [] for k in ["Component", "Property", "Time", "System", "Scale", "Method"]}
        sub = df[df["biomarker_id"].astype(str) == biomarker_id]
        out: dict[str, list[str]] = {k: [] for k in ["Component", "Property", "Time", "System", "Scale", "Method"]}
        for axis, grp in sub.groupby("axis"):
            out[str(axis)] = grp["value"].dropna().astype(str).tolist()
        return out

    def load_saved_loincs(self, biomarker_id: str):
        biomarker_id = str(biomarker_id)
        df = self._read_loincs()
        if df.empty:
            return [], {}, ""
        sub = df[df["biomarker_id"].astype(str) == biomarker_id]
        loincs = sub["loinc_num"].astype(str).tolist()
        conf = {str(r.loinc_num): int(r.confidence) for r in sub.itertuples(index=False)}
        rationale = sub["rationale"].dropna().astype(str).head(1).tolist()
        return loincs, conf, (rationale[0] if rationale else "")
