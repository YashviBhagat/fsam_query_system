"""
main.py — FastAPI Backend Server
==================================

ENDPOINTS:
──────────
GET  /          → health check
GET  /alloys    → list all alloys in database
GET  /stats     → database statistics
POST /query     → SQL only pipeline
POST /sql       → raw SQL + results (debug)
POST /ask       → smart router (SQL + RAG combined)
POST /upload    → upload user PDF to ChromaDB
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.query.answer_generator import generate_answer
from backend.query.sql_generator    import generate_sql
from backend.query.fuzzy_matcher    import get_all_alloys
from backend.query.router           import route_question

# ── Create FastAPI app ────────────────────────────────────────
app = FastAPI(
    title       = "FSAM Query System",
    description = "Query Friction Stir Additive Manufacturing research papers using natural language",
    version     = "1.0.0"
)

# ── CORS Middleware ───────────────────────────────────────────
# Allows Streamlit (port 8501) to talk to FastAPI (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_methods     = ["*"],
    allow_credentials = True,
    allow_headers     = ["*"],
)


# ── Request / Response Models ─────────────────────────────────

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    question: str
    answer:   str
    sql:      str | None
    rows:     int
    error:    str | None

class SQLRequest(BaseModel):
    question: str

class SQLResponse(BaseModel):
    question: str
    sql:      str | None
    columns:  list[str]
    results:  list[list]
    error:    str | None

class AskRequest(BaseModel):
    question:    str
    search_user: bool = False
    # search_user = True when user has uploaded a paper

class AskResponse(BaseModel):
    question:     str
    route:        str           # "sql", "rag", or "both"
    final_answer: str
    sql_answer:   str | None
    rag_answer:   str | None
    sql:          str | None
    rows:         int
    passages:     list[dict]
    error:        str | None


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/")
def health_check():
    """Confirms server is running."""
    return {
        "status":  "ok",
        "message": "FSAM Query System is running",
        "version": "1.0.0"
    }


@app.get("/alloys")
def get_alloys():
    """Returns all unique alloy names in database."""
    try:
        alloys = get_all_alloys()
        return {"alloys": alloys, "count": len(alloys)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
def get_stats():
    """Returns database statistics for Streamlit sidebar."""
    try:
        conn   = sqlite3.connect("data/processed/fsam_data.db")
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM papers")
        total_papers = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT base_alloy) FROM papers
            WHERE base_alloy IS NOT NULL
        """)
        total_alloys = cursor.fetchone()[0]

        cursor.execute("""
            SELECT process_category, COUNT(*) as count
            FROM papers
            WHERE process_category IS NOT NULL
            GROUP BY process_category
            ORDER BY count DESC
        """)
        processes = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) FROM papers WHERE hardness_min IS NOT NULL")
        hardness_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM papers WHERE uts_min IS NOT NULL")
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


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """
    SQL only pipeline.
    question → fuzzy_matcher → sql_generator → SQLite → answer
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

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
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

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


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    """
    Smart router endpoint — decides SQL, RAG, or both.

    Difference from /query:
    /query → always SQL only
    /ask   → router decides SQL, RAG, or both

    Use /ask for all Streamlit queries.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = route_question(
            request.question,
            search_user = request.search_user
        )

        return AskResponse(
            question     = result["question"],
            route        = result["route"],
            final_answer = result.get("final_answer") or "",
            sql_answer   = result.get("sql_answer"),
            rag_answer   = result.get("rag_answer"),
            sql          = result.get("sql"),
            rows         = result.get("rows", 0),
            passages     = result.get("passages", []),
            error        = result.get("error")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF and add it to ChromaDB user collection.

    After uploading → send search_user=True in /ask requests
    to include uploaded paper in RAG search.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code = 400,
            detail      = "Only PDF files are accepted"
        )

    try:
        # Read uploaded bytes
        pdf_bytes = await file.read()

        # Get user ChromaDB collection
        from backend.database.chroma_client import get_collections
        _, user_collection = get_collections()

        # Process and store in ChromaDB
        from backend.embeddings.embedder import process_uploaded_pdf
        result = process_uploaded_pdf(
            pdf_bytes,
            file.filename,
            user_collection
        )

        return {
            "filename":     file.filename,
            "paper_id":     result.get("paper_id"),
            "chunks_added": result.get("added_chunks", 0),
            "status":       result.get("status"),
            "message":      (
                f"Successfully processed {file.filename}. "
                f"Added {result.get('added_chunks', 0)} chunks. "
                f"Now send search_user=true in /ask requests."
            )
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))