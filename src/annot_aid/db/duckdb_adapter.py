from __future__ import annotations
from typing import Iterable, Optional, Tuple, List, Dict
import os
import pandas as pd
import duckdb

from .base import FilterParams, normalize_axes_dict
from annot_aid.config import get_config


class DuckDBAdapter:
    """DuckDB adapter using schema MAPPING; dynamic LOINC axes from config; minimal surface."""

    def __init__(self, db_path: Optional[str] = None, schema: str = "MAPPING", user_id: Optional[str] = None):
        cfg = get_config() or {}
        self._db_path = db_path or cfg.get("ANNOT_AID_DUCKDB_PATH") or os.path.join("data", "annot_aid.duckdb")
        self._schema = schema
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._user_id = user_id or os.getenv("ANNOT_AID_USER", "default")

        # Axes from config (list or dict)
        loinc_axes_cfg = cfg.get("LOINC_AXES") or ["COMPONENT","PROPERTY","TIME_ASPCT","SYSTEM","SCALE_TYP","METHOD_TYP"]
        if isinstance(loinc_axes_cfg, dict):
            self._axis_labels: List[str] = list(loinc_axes_cfg.keys())
            self._axis_to_col: Dict[str, str] = dict(loinc_axes_cfg)
        else:
            self._axis_labels = list(loinc_axes_cfg)
            self._axis_to_col = {a: a for a in self._axis_labels}

        self._text_fields: List[str] = list(cfg.get("LOINC_TEXT_FIELDS") or [])
        self._select_base: List[str] = list(cfg.get("LOINC_SELECT_BASE") or ["class"])
        self._long_name_col: str = str(cfg.get("LOINC_LONG_NAME_COL", "long_common_name"))

    # ---------------- Connection ----------------
    def _ensure_conn(self) -> None:
        if self._conn is not None:
            return
        self._conn = duckdb.connect(self._db_path)
        self._conn.execute(f"USE {self._schema}")
        required = {"LOINC","BIOMARKERS","BIOMARKER_AXES_SEL","BIOMARKER_LOINCS_SEL"}
        q = """SELECT table_name FROM information_schema.tables WHERE table_schema = ?"""
        have = set(self._conn.execute(q, [self._schema]).fetch_df()["table_name"].tolist())
        miss = sorted(list(required - have))
        if miss:
            raise RuntimeError(f"[DuckDBAdapter] Missing tables in {self._schema}: {', '.join(miss)}")

    # ---------------- WHERE builder ----------------
    def _build_loinc_where(self, params: Optional[FilterParams]) -> Tuple[str, List]:
        where: List[str] = []
        args: List = []
        if not params:
            return "", []

        # Text search
        if params.text:
            q = f"%{params.text.strip()}%"
            cols = self._text_fields or [self._long_name_col, *self._axis_to_col.values(), "loinc_num", "class"]
            ors = " OR ".join([f"{c} ILIKE ?" for c in cols])
            where.append(f"({ors})")
            args.extend([q] * len(cols))

        # Axis filters
        axes = normalize_axes_dict(params.axes)
        for label, values in (axes or {}).items():
            col = self._axis_to_col.get(str(label))
            if col and values:
                ph = ",".join(["?"] * len(values))
                where.append(f"{col} IN ({ph})")
                args.extend(list(values))


        return (" WHERE " + " AND ".join(where), args) if where else ("", [])

    # ---------------- Public APIs ----------------
    def get_loinc_candidates(self, params: Optional[FilterParams] = None) -> pd.DataFrame:
        self._ensure_conn()
        where_sql, args = self._build_loinc_where(params)
        # SELECT = loinc_num, long name, axes, extras
        cols = ["loinc_num", self._long_name_col, *self._axis_to_col.values(), *self._select_base]
        sql = f"SELECT {', '.join(cols)} FROM loinc {where_sql} ORDER BY loinc_num"
        return self._conn.execute(sql, args).fetch_df()

    def get_loinc_by_nums(self, nums: Iterable[str]) -> pd.DataFrame:
        self._ensure_conn()
        s = [str(x) for x in (nums or [])]
        if not s:
            return self._conn.execute("SELECT * FROM loinc WHERE 1=0").fetch_df()
        cols = ["loinc_num", self._long_name_col, *self._axis_to_col.values(), *self._select_base]
        ph = ",".join(["?"] * len(s))
        sql = f"SELECT {', '.join(cols)} FROM loinc WHERE loinc_num IN ({ph})"
        return self._conn.execute(sql, s).fetch_df()

    def get_biomarker_queue(self) -> pd.DataFrame:
        self._ensure_conn()
        sql = "SELECT biomarker_id, biomarker, organ, level, sublevel, test_method FROM biomarkers ORDER BY biomarker"
        return self._conn.execute(sql).fetch_df()

    # ---------------- Persistence: Axes ----------------
    def upsert_axes(self, biomarker_id: str, axes: Dict[str, List[str]]) -> None:
        self._ensure_conn()
        uid = self._user_id
        desired = {(str(k), str(v)) for k, vs in normalize_axes_dict(axes).items() for v in vs}

        cur = self._conn.execute(
            "SELECT axis, axis_value FROM biomarker_axes_sel WHERE biomarker_id = ? AND user_id = ? AND active_ind = 1",
            [str(biomarker_id), uid],
        ).fetch_df()
        existing = {(str(r.axis), str(r.axis_value)) for r in cur.itertuples(index=False)}

        to_add = sorted(desired - existing)
        to_remove = sorted(existing - desired)

        if to_remove:
            self._conn.executemany(
                "UPDATE biomarker_axes_sel SET active_ind = 0, updt_dt_tm = CURRENT_TIMESTAMP "
                "WHERE biomarker_id = ? AND user_id = ? AND axis = ? AND axis_value = ? AND active_ind = 1",
                [(str(biomarker_id), uid, a, v) for a, v in to_remove],
            )
        if to_add:
            self._conn.executemany(
                "INSERT INTO biomarker_axes_sel (biomarker_id, axis, axis_value, user_id, updt_dt_tm, active_ind) "
                "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 1)",
                [(str(biomarker_id), a, v, uid) for a, v in to_add],
            )

    # ---------------- Persistence: LOINCs ----------------
    def upsert_loincs(self, biomarker_id: str, loinc_conf: Dict[str, int], rationale: str) -> None:
        self._ensure_conn()
        uid = self._user_id
        desired = {str(k) for k in (loinc_conf or {}).keys()}

        cur = self._conn.execute(
            "SELECT loinc_num FROM biomarker_loincs_sel WHERE biomarker_id = ? AND user_id = ? AND active_ind = 1",
            [str(biomarker_id), uid],
        ).fetch_df()
        existing = set(cur["loinc_num"].astype(str).tolist())

        to_add = sorted(desired - existing)
        to_remove = sorted(existing - desired)

        if to_remove:
            self._conn.executemany(
                "UPDATE biomarker_loincs_sel SET active_ind = 0, updt_dt_tm = CURRENT_TIMESTAMP "
                "WHERE biomarker_id = ? AND user_id = ? AND loinc_num = ? AND active_ind = 1",
                [(str(biomarker_id), uid, ln) for ln in to_remove],
            )
        if to_add:
            rows = []
            for ln in to_add:
                c = loinc_conf.get(ln, 100)
                conf = int(max(1, min(100, int(c)))) if pd.notna(c) else 100
                rows.append((str(biomarker_id), ln, conf, str(rationale or ""), uid))
            self._conn.executemany(
                "INSERT INTO biomarker_loincs_sel (biomarker_id, loinc_num, confidence, rationale, user_id, updt_dt_tm, active_ind) "
                "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1)",
                rows,
            )

    # ---------------- Load selections ----------------
    def load_saved_axes(self, biomarker_id: str) -> Dict[str, List[str]]:
        self._ensure_conn()
        uid = self._user_id
        df = self._conn.execute(
            "SELECT axis, axis_value FROM biomarker_axes_sel WHERE biomarker_id = ? AND user_id = ? AND active_ind = 1",
            [str(biomarker_id), uid],
        ).fetch_df()
        out: Dict[str, List[str]] = {k: [] for k in self._axis_labels}
        for axis, grp in df.groupby("axis"):
            out[str(axis)] = grp["axis_value"].dropna().astype(str).tolist()
        return out

    def load_saved_loincs(self, biomarker_id: str):
        self._ensure_conn()
        uid = self._user_id
        df = self._conn.execute(
            "SELECT loinc_num, confidence, rationale, updt_dt_tm FROM biomarker_loincs_sel "
            "WHERE biomarker_id = ? AND user_id = ? AND active_ind = 1",
            [str(biomarker_id), uid],
        ).fetch_df()
        if df.empty:
            return [], {}, ""
        loincs = df["loinc_num"].astype(str).tolist()
        conf = {str(r.loinc_num): int(r.confidence) for r in df.itertuples(index=False)}
        df = df.sort_values("updt_dt_tm", ascending=False)
        rationale_vals = df["rationale"].dropna().astype(str).tolist()
        return loincs, conf, (rationale_vals[0] if rationale_vals else "")
