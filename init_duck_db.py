import duckdb
import os
from pathlib import Path

# Ensure data folder exists
os.makedirs("data", exist_ok=True)

# Connect to (or create) a DuckDB database file
con = duckdb.connect("data/annot_aid.duckdb")

con.execute(Path("init_duck_db.sql").read_text(encoding="utf-8"))

print("Database and tables created successfully!")
