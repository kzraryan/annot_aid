from __future__ import annotations
from typing import Iterable, Optional, Tuple, List, Dict
import os

import pandas as pd

from .base import FilterParams, normalize_axes_dict


class SnowflakeAdapter:
    """Snowflake-backed adapter with optional real connection.

    - Lazily imports snowflake.connector if available.
    - Connection params are read from environment variables by default and can be overridden.
    - If connection cannot be established, falls back to CSV+pandas filtering for demo.

    Expected env vars (if not passed explicitly):
      - SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, SNOWFLAKE_WAREHOUSE,
        SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA, optional SNOWFLAKE_ROLE

    Table names (can be views): loinc, biomarkers. Override via initializer.
    Columns required for loinc: loinc_num, long_name, component, property, time, system, scale, method, class, status, deprecated
    """

    def __init__(
        self,
        loinc_table: str = "LOINC",
        biomarkers_table: str = "BIOMARKERS",
        loinc_path: str = "data/loinc_small.csv",
        bio_path: str = "data/biomarkers.csv",
        conn_params: Optional[Dict[str, str]] = None,
    ):
        self._loinc_table = loinc_table
        self._biomarkers_table = biomarkers_table
        self._loinc_path = loinc_path
        self._bio_path = bio_path
        self._conn_params = conn_params or {}
        self._conn = None
        # Fallback DataFrames
        self._loinc_fallback: Optional[pd.DataFrame] = None
        self._bio_fallback: Optional[pd.DataFrame] = None

    # --- Connection ---
    def _get_conn_params(self) -> Dict[str, str]:
        if self._conn_params:
            return self._conn_params
        env = os.environ
        params = {
            "account": env.get("SNOWFLAKE_ACCOUNT", ""),
            "user": env.get("SNOWFLAKE_USER", ""),
            "password": env.get("SNOWFLAKE_PASSWORD", ""),
            "warehouse": env.get("SNOWFLAKE_WAREHOUSE", ""),
            "database": env.get("SNOWFLAKE_DATABASE", ""),
            "schema": env.get("SNOWFLAKE_SCHEMA", ""),
        }
        role = env.get("SNOWFLAKE_ROLE")
        if role:
            params["role"] = role
        return params

    def _ensure_conn(self):
        if self._conn is not None:
            return
        try:
            import snowflake.connector  # type: ignore
        except Exception:
            self._conn = None
            return
        params = self._get_conn_params()
        # Minimal validation
        if not all(params.get(k) for k in ["account", "user", "password", "warehouse", "database", "schema"]):
            self._conn = None
            return
        self._conn = snowflake.connector.connect(**params)

    # --- Fallback pandas loaders ---
    @property
    def _loinc_df(self) -> pd.DataFrame:
        if self._loinc_fallback is None:
            self._loinc_fallback = pd.read_csv(self._loinc_path)
        return self._loinc_fallback

    @property
    def _bio_df(self) -> pd.DataFrame:
        if self._bio_fallback is None:
            self._bio_fallback = pd.read_csv(self._bio_path)
        return self._bio_fallback

    # --- Query building ---
    def _build_loinc_where(self, params: Optional[FilterParams]) -> Tuple[str, List]:
        if not params:
            return "", []
        axes = normalize_axes_dict(params.axes)
        where = []
        args: List = []
        if params.text:
            q = f"%{params.text.strip()}%"
            text_cols = [
                "long_name", "component", "property", "time", "system", "scale", "method", "loinc_num",
            ]
            ors = " OR ".join([f"{c} ILIKE ?" for c in text_cols])
            where.append(f"({ors})")
            args.extend([q] * len(text_cols))
        for col, values in axes.items():
            if values:
                placeholders = ",".join(["?"] * len(values))
                where.append(f"{col} IN ({placeholders})")
                args.extend(values)
        if not params.include_deprecated:
            where.append("COALESCE(deprecated, false) = false")
        if not where:
            return "", []
        return " WHERE " + " AND ".join(where), args

    # --- API ---
    def get_loinc_candidates(self, params: Optional[FilterParams] = None) -> pd.DataFrame:
        self._ensure_conn()
        if self._conn is None:
            # Fallback: pandas filtering
            if params is None:
                return self._loinc_df
            from ..model.filtering import apply_filters
            return apply_filters(self._loinc_df, text=params.text, axes=normalize_axes_dict(params.axes), include_deprecated=params.include_deprecated)
        where_sql, args = self._build_loinc_where(params)
        sql = (
            f"SELECT loinc_num, long_name, component, property, time, system, scale, method, class, status, deprecated FROM {self._loinc_table}" +
            where_sql +
            " ORDER BY class, component, long_name"
        )
        cur = self._conn.cursor()
        try:
            cur.execute(sql, args)
            try:
                df = cur.fetch_pandas_all()
            except Exception:
                rows = cur.fetchall()
                cols = [c[0].lower() for c in cur.description]
                df = pd.DataFrame(rows, columns=cols)
        finally:
            cur.close()
        return df

    def get_biomarker_queue(self) -> pd.DataFrame:
        self._ensure_conn()
        if self._conn is None:
            return self._bio_df
        sql = f"SELECT id, description FROM {self._biomarkers_table} ORDER BY id"
        cur = self._conn.cursor()
        try:
            cur.execute(sql)
            try:
                df = cur.fetch_pandas_all()
            except Exception:
                rows = cur.fetchall()
                cols = [c[0].lower() for c in cur.description]
                df = pd.DataFrame(rows, columns=cols)
        finally:
            cur.close()
        return df

    def get_loinc_by_nums(self, nums: Iterable[str]) -> pd.DataFrame:
        s = [str(x) for x in nums]
        if not s:
            self._ensure_conn()
            if self._conn is None:
                return self._loinc_df.iloc[0:0]
            # Return empty result with correct columns
            return pd.DataFrame(columns=["loinc_num","long_name","component","property","time","system","scale","method","class","status","deprecated"])[:0]
        self._ensure_conn()
        if self._conn is None:
            return self._loinc_df[self._loinc_df["loinc_num"].astype(str).isin(set(s))]
        placeholders = ",".join(["?"] * len(s))
        sql = (
            f"SELECT loinc_num, long_name, component, property, time, system, scale, method, class, status, deprecated FROM {self._loinc_table} "
            f"WHERE loinc_num IN ({placeholders})"
        )
        cur = self._conn.cursor()
        try:
            cur.execute(sql, s)
            try:
                df = cur.fetch_pandas_all()
            except Exception:
                rows = cur.fetchall()
                cols = [c[0].lower() for c in cur.description]
                df = pd.DataFrame(rows, columns=cols)
        finally:
            cur.close()
        return df
