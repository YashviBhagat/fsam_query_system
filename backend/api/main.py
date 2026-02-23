"""
main.py — FastAPI Backend Server
==================================

WHY THIS FILE EXISTS:
─────────────────────
This is the bridge between your Streamlit UI and your query pipeline.
It runs as a server on port 8000 and listens for questions.

ENDPOINTS:
──────────
GET  /          → health check (is server running?)
GET  /alloys    → list all alloys in database
POST /query     → main endpoint (question → answer)
POST /sql       → returns raw SQL + results (for debugging)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.query.answer_generator import generate_answer
from backend.query.sql_generator import generate_sql
from backend.query.fuzzy_matcher import get_all_alloys

# ── Create FastAPI app ───────────────────────────────────────
app = FastAPI(
    title       = "FSAM Query System",
    description = "Query Friction Stir Additive Manufacturing research papers using natural language",
    version     = "1.0.0"
)

# ── CORS Middleware ──────────────────────────────────────────
# This allows Streamlit (port 8501) to talk to FastAPI (port 8000)
# Without this, browser blocks cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # allow all origins
    allow_methods     = ["*"],   # allow GET, POST, etc.
    allow_credentials = True,
    allow_headers     = ["*"],
)


# ── Request/Response Models ──────────────────────────────────
# Pydantic models define exactly what data comes IN and goes OUT
# FastAPI uses these for automatic validation

class QueryRequest(BaseModel):
    """What the user sends to /query"""
    question: str               # the natural language question

class QueryResponse(BaseModel):
    """What /query sends back"""
    question: str               # original question
    answer:   str               # natural language answer
    sql:      str | None        # SQL that was generated
    rows:     int               # number of results found
    error:    str | None        # error message if something failed

class SQLRequest(BaseModel):
    """What the user sends to /sql"""
    question: str

class SQLResponse(BaseModel):
    """What /sql sends back"""
    question: str
    sql:      str | None
    columns:  list[str]
    results:  list[list]
    error:    str | None


# ── Endpoints ────────────────────────────────────────────────

@app.get("/")
def health_check():
    """
    Health check endpoint.
    Call this to confirm server is running.

    Returns: {"status": "ok", "message": "FSAM Query System is running"}
    """
    return {
        "status":  "ok",
        "message": "FSAM Query System is running",
        "version": "1.0.0"
    }


@app.get("/alloys")
def get_alloys():
    """
    Returns all unique alloy names in the database.
    Streamlit uses this to show a dropdown of available alloys.

    Returns: {"alloys": ["AA6061", "AA7075", ...], "count": 25}
    """
    try:
        alloys = get_all_alloys()
        return {
            "alloys": alloys,
            "count":  len(alloys)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """
    MAIN ENDPOINT — natural language question → answer.

    FLOW:
    1. Receives question from Streamlit
    2. Passes to fuzzy_matcher → finds alloy
    3. Passes to sql_generator → generates SQL
    4. Runs SQL on database
    5. Passes to answer_generator → formats answer
    6. Returns answer to Streamlit

    Example request:
    {
        "question": "What is the hardness of AA6061?"
    }

    Example response:
    {
        "question": "What is the hardness of AA6061?",
        "answer":   "AA6061 hardness ranges from 43.8 to 110.0 HV...",
        "sql":      "SELECT paper_id, base_alloy...",
        "rows":     11,
        "error":    null
    }
    """
    if not request.question.strip():
        raise HTTPException(
            status_code = 400,
            detail      = "Question cannot be empty"
        )

    try:
        result = generate_answer(request.question)
        return QueryResponse(
            question = result["question"],
            answer   = result["answer"],
            sql      = result["sql"],
            rows     = result["rows"],
            error    = result["error"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sql", response_model=SQLResponse)
def get_sql(request: SQLRequest):
    """
    Debug endpoint — returns raw SQL and results without formatting.
    Useful for developers to see exactly what SQL was generated.

    Example request:
    {
        "question": "What is hardness of AA6061?"
    }

    Example response:
    {
        "sql":     "SELECT paper_id...",
        "columns": ["paper_id", "base_alloy", "hardness_min"],
        "results": [["paper_27", "AA6061", 86.3], ...]
    }
    """
    if not request.question.strip():
        raise HTTPException(
            status_code = 400,
            detail      = "Question cannot be empty"
        )

    try:
        result = generate_sql(request.question)
        return SQLResponse(
            question = result["question"],
            sql      = result["sql"],
            columns  = result["columns"],
            results  = [list(row) for row in result["results"]],
            error    = result["error"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
def get_stats():
    """
    Returns database statistics.
    Streamlit uses this for the dashboard/stats page.

    Returns counts of papers, alloys, processes etc.
    """
    try:
        conn   = sqlite3.connect("data/processed/fsam_data.db")
        cursor = conn.cursor()

        # Total papers
        cursor.execute("SELECT COUNT(*) FROM papers")
        total_papers = cursor.fetchone()[0]

        # Unique alloys
        cursor.execute("""
            SELECT COUNT(DISTINCT base_alloy)
            FROM papers
            WHERE base_alloy IS NOT NULL
        """)
        total_alloys = cursor.fetchone()[0]

        # Papers per process
        cursor.execute("""
            SELECT process_category, COUNT(*) as count
            FROM papers
            WHERE process_category IS NOT NULL
            GROUP BY process_category
            ORDER BY count DESC
        """)
        processes = {row[0]: row[1] for row in cursor.fetchall()}

        # Hardness coverage
        cursor.execute("""
            SELECT COUNT(*) FROM papers
            WHERE hardness_min IS NOT NULL
        """)
        hardness_count = cursor.fetchone()[0]

        # UTS coverage
        cursor.execute("""
            SELECT COUNT(*) FROM papers
            WHERE uts_min IS NOT NULL
        """)
        uts_count = cursor.fetchone()[0]

        conn.close()

        return {
            "total_papers":   total_papers,
            "total_alloys":   total_alloys,
            "processes":      processes,
            "hardness_count": hardness_count,
            "uts_count":      uts_count,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))