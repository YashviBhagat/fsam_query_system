import sqlite3
import os
import pandas as pd
from backend.etl.flatten import flatten_all_papers

# Where the database file will be saved
DB_PATH = "data/processed/fsam_data.db"


def get_connection() -> sqlite3.Connection:
    """Creates a connection to the SQLite database."""
    os.makedirs("data/processed", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    return conn


def write_to_database(rows: list[dict]) -> None:
    """
    Takes flattened rows and writes them into SQLite.
    Replaces table completely on every run — always fresh data.
    """
    df = pd.DataFrame(rows)
    conn = get_connection()

    # Write DataFrame directly to SQLite
    # if_exists='replace' = drop and recreate table every time
    df.to_sql(
        name      = "papers",   # table name in SQLite
        con       = conn,
        if_exists = "replace",  # fresh data every run
        index     = False       # don't write row numbers
    )

    conn.close()
    print(f"✅ Saved {len(rows)} papers to {DB_PATH}")


def verify_database() -> None:
    """
    Reads back from the database and prints a summary.
    Confirms everything saved correctly.
    """
    conn = get_connection()
    #cursor is the tool you use to actually execute SQL commands through the connection.
    cursor = conn.cursor()

    # Count total rows
    cursor.execute("SELECT COUNT(*) FROM papers")
    total = cursor.fetchone()[0]
    print(f"\n📊 Database Summary:")
    print(f"   Total papers: {total}")

    # Show all column names
    cursor.execute("PRAGMA table_info(papers)")
    columns = cursor.fetchall()
    print(f"   Total columns: {len(columns)}")

    # Show sample data
    print(f"\n--- Sample: 3 papers ---")
    cursor.execute("""
        SELECT paper_id, base_alloy, process_category,
               hardness_min, hardness_max, hardness_unit,
               rotation_speed_min, rotation_speed_unit
        FROM papers
        LIMIT 3
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(f"  {row}")

    # Test a real filter query
    print(f"\n--- Test Query: papers with hardness > 100 HV ---")
    cursor.execute("""
        SELECT paper_id, base_alloy, hardness_min, hardness_unit
        FROM papers
        WHERE hardness_min > 100
        ORDER BY hardness_min DESC
    """)
    results = cursor.fetchall()
    for row in results:
        print(f"  {row}")
    print(f"  Found: {len(results)} papers")

    conn.close()


if __name__ == "__main__":
    print("=" * 50)
    print("Step 1: Flatten all JSON files...")
    print("=" * 50)
    rows = flatten_all_papers()

    print("\n" + "=" * 50)
    print("Step 2: Write to SQLite database...")
    print("=" * 50)
    write_to_database(rows)

    print("\n" + "=" * 50)
    print("Step 3: Verify database...")
    print("=" * 50)
    verify_database()