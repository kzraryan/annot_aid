from __future__ import annotations
from typing import Iterable, Optional, Sequence, Tuple, List
import os

import pandas as pd

from .base import FilterParams, normalize_axes_dict


class DuckDBAdapter:
    """DuckDB-backed adapter using real duckdb SQL where available.

    - Lazily imports duckdb to avoid hard dependency for tests.
    - If duckdb is unavailable, falls back to pandas CSV filtering (kept minimal).
    - For demo, loads CSVs into an in-memory DuckDB and pushes filters server-side.
    """

    def __init__(self, loinc_path: str = "data/loinc_small.csv", bio_path: str = "data/biomarkers.csv", db_path: Optional[str] = None):
        self._loinc_path = loinc_path
        self._bio_path = bio_path
        self._db_path = db_path  # if provided, persists a duckdb database file
        self._conn = None
        self._fallback_loinc: Optional[pd.DataFrame] = None
        self._fallback_bio: Optional[pd.DataFrame] = None
        self._demo_initialized = False

    # --- Connection and schema setup ---
    def _ensure_conn(self):
        if self._conn is not None:
            return
        try:
            import duckdb  # type: ignore
        except Exception as e:
            self._conn = None
            return
        # Connect (in-memory by default)
        self._conn = duckdb.connect(self._db_path or ":memory:")
        # Create or replace views from CSVs
        self._conn.execute("CREATE OR REPLACE VIEW loinc AS SELECT * FROM read_csv_auto(?, HEADER=TRUE)", [self._loinc_path])
        self._conn.execute("CREATE OR REPLACE VIEW biomarkers AS SELECT * FROM read_csv_auto(?, HEADER=TRUE)", [self._bio_path])
        # Create persistence tables if not exist
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS biomarker_axes (
                biomarker_id VARCHAR,
                axis VARCHAR,
                value VARCHAR
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS biomarker_loincs (
                biomarker_id VARCHAR,
                loinc_num VARCHAR,
                confidence INTEGER,
                rationale VARCHAR
            )
            """
        )
        # Seed small demo rows once (idempotent)
        if not self._demo_initialized:
            self._conn.execute("INSERT INTO biomarker_axes BY NAME SELECT * FROM (SELECT '1' AS biomarker_id, 'Component' AS axis, component AS value FROM loinc LIMIT 1) ON CONFLICT DO NOTHING")
            # Insert two demo loincs with confidence 100 for biomarker 1 if none exist
            self._conn.execute(
                """
                INSERT INTO biomarker_loincs
                SELECT '1' AS biomarker_id, loinc_num::VARCHAR, 100 AS confidence, 'Demo rationale' AS rationale
                FROM loinc
                WHERE loinc_num IN (
                    SELECT loinc_num FROM loinc ORDER BY loinc_num LIMIT 2
                )
                AND NOT EXISTS (
                    SELECT 1 FROM biomarker_loincs b WHERE b.biomarker_id='1'
                )
                """
            )
            self._demo_initialized = True

    # --- Fallback pandas loaders ---
    @property
    def _loinc_df(self) -> pd.DataFrame:
        if self._fallback_loinc is None:
            self._fallback_loinc = pd.read_csv(self._loinc_path)
        return self._fallback_loinc

    @property
    def _bio_df(self) -> pd.DataFrame:
        if self._fallback_bio is None:
            self._fallback_bio = pd.read_csv(self._bio_path)
        return self._fallback_bio

    # --- Query building helpers ---
    def _build_loinc_where(self, params: Optional[FilterParams]) -> Tuple[str, List]:
        if not params:
            return "", []
        axes = normalize_axes_dict(params.axes)
        where = []
        args: List = []
        # Text search across multiple columns
        if params.text:
            q = f"%{params.text.strip()}%"
            text_cols = [
                "long_name", "component", "property", "time", "system", "scale", "method", "loinc_num",
            ]
            ors = " OR ".join([f"{c} ILIKE ?" for c in text_cols])
            where.append(f"({ors})")
            args.extend([q] * len(text_cols))
        # Axis filters
        for col, values in axes.items():
            if values:
                placeholders = ",".join(["?"] * len(values))
                where.append(f"{col.lower()} IN ({placeholders})")
                args.extend(values)
        # Deprecated toggle
        if not params.include_deprecated:
            where.append("COALESCE(deprecated, false) = false")
        if not where:
            return "", []
        return " WHERE " + " AND ".join(where), args

    # --- Public API ---
    def get_loinc_candidates(self, params: Optional[FilterParams] = None) -> pd.DataFrame:
        self._ensure_conn()
        if self._conn is None:
            # Fallback: minimal pandas filtering (no heavy copies)
            df = self._loinc_df
            if params is None:
                return df
            # Apply simple boolean masks equivalent to server-side filters
            from ..model.filtering import apply_filters
            return apply_filters(df, text=params.text, axes=normalize_axes_dict(params.axes), include_deprecated=params.include_deprecated)
        where_sql, args = self._build_loinc_where(params)
        sql = (
            "SELECT loinc_num, long_name, component, property, time, system, scale, method, class, status, deprecated "
            "FROM loinc" + where_sql + " ORDER BY class, component, long_name"
        )
        res = self._conn.execute(sql, args).fetch_df()
        return res

    # --- Persistence API ---
    def upsert_axes(self, biomarker_id: str, axes: dict[str, list[str]]) -> None:
        self._ensure_conn()
        if self._conn is None:
            # fallback: no duckdb, do nothing (file adapter should handle persistence in file mode)
            return
        # delete and insert
        self._conn.execute("DELETE FROM biomarker_axes WHERE biomarker_id = ?", [str(biomarker_id)])
        rows = []
        from .base import AXES as _AXES
        for axis, values in normalize_axes_dict(axes).items():
            for v in values:
                rows.append((str(biomarker_id), axis, str(v)))
        if rows:
            self._conn.execute("INSERT INTO biomarker_axes (biomarker_id, axis, value) VALUES (?, ?, ?)", rows)

    def upsert_loincs(self, biomarker_id: str, loinc_conf: dict[str, int], rationale: str) -> None:
        self._ensure_conn()
        if self._conn is None:
            return
        self._conn.execute("DELETE FROM biomarker_loincs WHERE biomarker_id = ?", [str(biomarker_id)])
        rows = []
        for ln, conf in loinc_conf.items():
            c = int(max(1, min(100, int(conf)))) if pd.notna(conf) else 100
            rows.append((str(biomarker_id), str(ln), c, str(rationale or "")))
        if rows:
            self._conn.execute("INSERT INTO biomarker_loincs (biomarker_id, loinc_num, confidence, rationale) VALUES (?, ?, ?, ?)", rows)

    def load_saved_axes(self, biomarker_id: str) -> dict[str, list[str]]:
        self._ensure_conn()
        if self._conn is None:
            return {k: [] for k in ["Component", "Property", "Time", "System", "Scale", "Method"]}
        df = self._conn.execute("SELECT axis, value FROM biomarker_axes WHERE biomarker_id = ?", [str(biomarker_id)]).fetch_df()
        out: dict[str, list[str]] = {k: [] for k in ["Component", "Property", "Time", "System", "Scale", "Method"]}
        if df.empty:
            return out
        for axis, grp in df.groupby("axis"):
            out[str(axis)] = grp["value"].dropna().astype(str).tolist()
        return out

    def load_saved_loincs(self, biomarker_id: str):
        self._ensure_conn()
        if self._conn is None:
            return [], {}, ""
        df = self._conn.execute("SELECT loinc_num, confidence, rationale FROM biomarker_loincs WHERE biomarker_id = ?", [str(biomarker_id)]).fetch_df()
        if df.empty:
            return [], {}, ""
        loincs = df["loinc_num"].astype(str).tolist()
        conf = {str(r.loinc_num): int(r.confidence) for r in df.itertuples(index=False)}
        rationale = df["rationale"].dropna().astype(str).head(1).tolist()
        return loincs, conf, (rationale[0] if rationale else "")

    def get_biomarker_queue(self) -> pd.DataFrame:
        self._ensure_conn()
        if self._conn is None:
            return self._bio_df
        sql = "SELECT id, description FROM biomarkers ORDER BY id"
        return self._conn.execute(sql).fetch_df()

    def get_loinc_by_nums(self, nums: Iterable[str]) -> pd.DataFrame:
        s = [str(x) for x in nums]
        if not s:
            # Fast-empty
            self._ensure_conn()
            if self._conn is None:
                return self._loinc_df.iloc[0:0]
            return self._conn.execute(
                "SELECT loinc_num, long_name, component, property, time, system, scale, method, class, status, deprecated FROM loinc WHERE 1=0"
            ).fetch_df()
        self._ensure_conn()
        if self._conn is None:
            return self._loinc_df[self._loinc_df["loinc_num"].astype(str).isin(set(s))]
        placeholders = ",".join(["?"] * len(s))
        sql = (
            "SELECT loinc_num, long_name, component, property, time, system, scale, method, class, status, deprecated FROM loinc "
            f"WHERE loinc_num IN ({placeholders})"
        )
        return self._conn.execute(sql, s).fetch_df()
