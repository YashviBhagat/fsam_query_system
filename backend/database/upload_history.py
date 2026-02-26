"""
upload_history.py — Track Uploaded Papers
==========================================
ONE JOB ONLY: Save and retrieve upload history from SQLite.

WHY SEPARATE FILE?
───────────────────
Keeps database logic separate from API logic.
Same pattern as db_writer.py for your main database.
"""

import sqlite3
import os
from datetime import datetime
from pathlib  import Path

# History stored in same folder as main database
HISTORY_DB = "data/processed/upload_history.db"


def init_history_db():
    """
    Creates upload_history table if it doesn't exist.
    Called once when server starts.

    CREATE TABLE IF NOT EXISTS:
    → Safe to call multiple times
    → Only creates table on first run
    """

    os.makedirs("data/processed", exist_ok=True)

    conn   = sqlite3.connect(HISTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS upload_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            filename     TEXT    NOT NULL,
            paper_id     TEXT    NOT NULL,
            chunks_added INTEGER DEFAULT 0,
            file_size_mb REAL    DEFAULT 0,
            uploaded_at  TEXT    NOT NULL
        )
    """)
    # INTEGER PRIMARY KEY AUTOINCREMENT = auto-incrementing ID
    # TEXT NOT NULL = required field
    # DEFAULT 0 = use 0 if no value provided

    conn.commit()
    conn.close()


def save_upload(filename: str,
                paper_id: str,
                chunks_added: int,
                file_size_mb: float) -> dict:
    """
    Saves one upload record to history.
    Called by FastAPI /upload endpoint after successful upload.

    Returns the saved record as a dict.
    """

    uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    # strftime = string format time
    # "%Y-%m-%d %H:%M" = "2026-02-26 14:30"

    conn   = sqlite3.connect(HISTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO upload_history
            (filename, paper_id, chunks_added, file_size_mb, uploaded_at)
        VALUES
            (?, ?, ?, ?, ?)
    """, (filename, paper_id, chunks_added, file_size_mb, uploaded_at))
    # ? = parameterized query (safe from SQL injection)
    # Values passed as tuple match the ? placeholders

    conn.commit()

    # Get the ID of the record we just inserted
    record_id = cursor.lastrowid
    conn.close()

    return {
        "id":           record_id,
        "filename":     filename,
        "paper_id":     paper_id,
        "chunks_added": chunks_added,
        "file_size_mb": round(file_size_mb, 2),
        "uploaded_at":  uploaded_at
    }


def get_all_history() -> list[dict]:
    """
    Returns all upload history records.
    Most recent first (ORDER BY id DESC).

    Called by FastAPI GET /history endpoint.
    """

    # Initialize DB if it doesn't exist yet
    init_history_db()

    conn   = sqlite3.connect(HISTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, filename, paper_id, chunks_added,
               file_size_mb, uploaded_at
        FROM   upload_history
        ORDER  BY id DESC
    """)
    # ORDER BY id DESC = newest first

    rows = cursor.fetchall()
    conn.close()

    # Convert rows to list of dicts
    history = []
    for row in rows:
        history.append({
            "id":           row[0],
            "filename":     row[1],
            "paper_id":     row[2],
            "chunks_added": row[3],
            "file_size_mb": row[4],
            "uploaded_at":  row[5]
        })

    return history


def delete_history(record_id: int) -> bool:
    """
    Deletes one record from history by ID.
    Called by FastAPI DELETE /history/{id} endpoint.
    Returns True if deleted, False if not found.
    """

    conn   = sqlite3.connect(HISTORY_DB)
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM upload_history WHERE id = ?",
        (record_id,)
    )

    deleted = cursor.rowcount > 0
    # rowcount = number of rows affected
    # > 0 means something was deleted

    conn.commit()
    conn.close()

    return deleted