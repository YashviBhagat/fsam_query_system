"""
chroma_client.py — ChromaDB Connection
========================================
ONE JOB ONLY: Open ChromaDB and return collections.
Nothing else. No storing. No searching. Just connecting.

WHY A SEPARATE FILE?
─────────────────────
Same reason we have db_connection.py for SQLite.
Every file that needs ChromaDB imports from here.
If ChromaDB path changes → fix it in ONE place only.

TWO COLLECTIONS:
─────────────────
fsam_papers  → your 57 pre-loaded papers (permanent)
user_papers  → papers users upload at runtime

Input:  nothing
Output: (fsam_collection, user_collection)
"""

import os
import chromadb
# chromadb = vector database
# PersistentClient = saves to disk, survives restarts

from chromadb.utils import embedding_functions
# SentenceTransformerEmbeddingFunction converts text → vectors
# Uses a local AI model (no API key needed)

# ── CONSTANTS ─────────────────────────────────────────────────

# Where ChromaDB saves its files on disk
CHROMA_DIR = "chroma_db"

# Embedding model — converts text to vectors
# BAAI/bge-large-en-v1.5:
# - Free, runs locally
# - Excellent for scientific/technical text
# - Downloads automatically on first run (~1.3GB)
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"


def get_embedding_function():
    """
    Creates and returns the embedding function.

    WHAT IS AN EMBEDDING FUNCTION?
    ────────────────────────────────
    It converts text → vector (list of numbers).

    "The grain size decreased"
    → [0.23, -0.41, 0.87, 0.12, ...]  (1024 numbers)

    These numbers capture the MEANING of the text.
    Similar meanings → similar vectors → found together in search.

    WHY SEPARATE FUNCTION?
    ───────────────────────
    Both collections use the same embedding function.
    Define it once here, reuse for both collections.
    Also reused by rag_retriever.py when searching.
    """

    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name = EMBEDDING_MODEL,
        device     = "cpu"
        # Use "cuda" if you have NVIDIA GPU (much faster)
        # Use "cpu" works on all machines including MacBook
    )


def get_chroma_client():
    """
    Creates and returns a ChromaDB client.

    PersistentClient vs Client:
    ────────────────────────────
    chromadb.Client()           → in-memory, data lost on restart
    chromadb.PersistentClient() → saves to disk, data survives

    We always use PersistentClient so ChromaDB data
    is not lost every time you restart the server.
    """

    # Create chroma_db folder if it doesn't exist
    os.makedirs(CHROMA_DIR, exist_ok=True)

    # Create persistent client
    # path = where to save ChromaDB files on disk
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    return client


def get_collections():
    """
    Main function — returns both ChromaDB collections.

    WHAT IS get_or_create_collection?
    ───────────────────────────────────
    First run:  collection doesn't exist → creates it
    Later runs: collection exists → opens it (no data loss)
    Safe to call multiple times.

    metadata={"hnsw:space": "cosine"}:
    → hnsw = algorithm used for fast vector search
    → cosine = similarity measure (best for text)
    → cosine measures ANGLE between vectors
    → dot product measures magnitude (worse for text)

    Returns: (fsam_collection, user_collection)

    Usage:
    fsam_col, user_col = get_collections()
    fsam_col.add(...)    → store chunks
    fsam_col.query(...)  → search chunks
    """

    client       = get_chroma_client()
    embedding_fn = get_embedding_function()

    # Collection for your 57 pre-loaded papers
    fsam_collection = client.get_or_create_collection(
        name               = "fsam_papers",
        embedding_function = embedding_fn,
        metadata           = {"hnsw:space": "cosine"}
    )

    # Collection for user-uploaded papers
    user_collection = client.get_or_create_collection(
        name               = "user_papers",
        embedding_function = embedding_fn,
        metadata           = {"hnsw:space": "cosine"}
    )

    return fsam_collection, user_collection


def get_collection_stats() -> dict:
    """
    Returns statistics about what's stored in ChromaDB.
    Used by FastAPI /stats endpoint and Streamlit sidebar.

    Returns:
    {
        "fsam_chunks": 1028,   ← chunks from your 57 papers
        "user_chunks": 45,     ← chunks from user uploads
        "total_chunks": 1073
    }
    """

    fsam_col, user_col = get_collections()

    # .count() returns total items in collection
    fsam_count = fsam_col.count()
    user_count = user_col.count()

    return {
        "fsam_chunks":  fsam_count,
        "user_chunks":  user_count,
        "total_chunks": fsam_count + user_count
    }


# ── TEST ──────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 50)
    print("chroma_client.py — Connection Test")
    print("=" * 50)

    print("\n[Step 1] Connecting to ChromaDB...")
    fsam_col, user_col = get_collections()
    print(f"✅ Connected to ChromaDB at: {CHROMA_DIR}/")

    print("\n[Step 2] Collection stats...")
    stats = get_collection_stats()
    print(f"  fsam_papers:  {stats['fsam_chunks']} chunks")
    print(f"  user_papers:  {stats['user_chunks']} chunks")
    print(f"  total:        {stats['total_chunks']} chunks")

    print("\n[Step 3] Testing collections exist...")
    print(f"  fsam_papers collection: ✅")
    print(f"  user_papers collection: ✅")

    if stats["fsam_chunks"] == 0:
        print("\n⚠️  No chunks stored yet.")
        print("   Run: python -m backend.embeddings.embedder")
    else:
        print(f"\n✅ ChromaDB ready with {stats['total_chunks']} chunks")