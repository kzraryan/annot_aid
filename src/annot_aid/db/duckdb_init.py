from __future__ import annotations
from typing import Optional
import os


def init_db(db_path: str = "annot_aid.duckdb", loinc_csv: str = "data/loinc.csv", biomarkers_csv: str = "data/biomarkers.csv", overwrite: bool = False) -> None:
    """
    One-time initializer to create a physical DuckDB database file with required tables and
    load demo data from CSVs. This is intentionally separate from runtime adapter code
    to avoid creating tables in live code.

    Parameters:
    - db_path: Path to the DuckDB database file to create/use.
    - loinc_csv: CSV path containing LOINC demo data (columns must match loinc schema).
    - biomarkers_csv: CSV path containing biomarker demo data (id, description).
    - overwrite: If True, remove existing db_path file and recreate from scratch.
    """
    import duckdb  # type: ignore

    if overwrite and os.path.exists(db_path):
        os.remove(db_path)

    con = duckdb.connect(db_path)

    # Domain tables
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS loinc (
            loinc_num VARCHAR,
            long_common_name VARCHAR,
            component VARCHAR,
            property VARCHAR,
            time VARCHAR,
            system VARCHAR,
            scale VARCHAR,
            method VARCHAR,
            class VARCHAR,
            status VARCHAR,
            deprecated BOOLEAN
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS biomarkers (
            id VARCHAR,
            description VARCHAR
        )
        """
    )

    # Selection tables with audit fields and logical delete flag
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS biomarker_axes_sel (
            biomarker_id VARCHAR,
            axis VARCHAR,
            value VARCHAR,
            user_id VARCHAR,
            updt_dt_tm TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active_ind INTEGER DEFAULT 1
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS biomarker_loincs_sel (
            biomarker_id VARCHAR,
            loinc_num VARCHAR,
            confidence INTEGER,
            rationale VARCHAR,
            user_id VARCHAR,
            updt_dt_tm TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active_ind INTEGER DEFAULT 1
        )
        """
    )

    # Load demo data only if empty
    cnt = con.execute("SELECT COUNT(*) FROM loinc").fetchone()[0]
    if cnt == 0:
        con.execute("INSERT INTO loinc SELECT * FROM read_csv_auto(?, HEADER=TRUE)", [loinc_csv])

    cntb = con.execute("SELECT COUNT(*) FROM biomarkers").fetchone()[0]
    if cntb == 0:
        con.execute("INSERT INTO biomarkers SELECT * FROM read_csv_auto(?, HEADER=TRUE)", [biomarkers_csv])

    # Optional helpful indexes (not required but beneficial)
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_loinc_num ON loinc(loinc_num)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_bm_axes ON biomarker_axes_sel(biomarker_id, axis, value)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_bm_loincs ON biomarker_loincs_sel(biomarker_id, loinc_num)")
    except Exception:
        # DuckDB 1.0+ supports CREATE INDEX; ignore if older or not supported
        pass

    con.close()


__all__ = ["init_db"]
