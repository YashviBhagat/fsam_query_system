"""
run_etl.py — Rebuild the Database
===================================
Run this script whenever you:
- Add new JSON papers to data/raw/json/
- Fix existing JSON files
- Change flatten.py schema

Usage:
    python scripts/run_etl.py
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.etl.db_writer import write_to_database
from backend.etl.flatten import flatten_all_papers
import pandas as pd

print("=" * 55)
print("FSAM ETL Pipeline")
print("=" * 55)

print("\n[Step 1] Loading and flattening JSON files...")
rows = flatten_all_papers()

print("\n[Step 2] Writing to database...")
write_to_database(rows)

print("\n[Step 3] Exporting CSV...")
df = pd.DataFrame(rows)
os.makedirs("data/exports", exist_ok=True)
df.to_csv("data/exports/fsam_flat.csv", index=False, encoding="utf-8-sig")
print(f"✅ CSV saved to data/exports/fsam_flat.csv")

print("\n" + "=" * 55)
print("✅ ETL complete. Database is ready.")
print("   Run scripts/run_backend.py to start the server.")
print("=" * 55)