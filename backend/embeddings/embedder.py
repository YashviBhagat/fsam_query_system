"""
embedder.py — Store Text Chunks in ChromaDB
=============================================
ONE JOB ONLY: Take chunks from chunker.py and store
them in ChromaDB as vectors.

IMPORTANT FIX:
──────────────
All embeddings are generated manually using BAAI/bge-large-en-v1.5
(1024 dimensions) before storing in ChromaDB.

This is critical because:
- ChromaDB's default model = all-MiniLM-L6-v2 (384 dimensions)
- Your query model = BAAI/bge-large-en-v1.5 (1024 dimensions)
- If dimensions do not match → query crashes with InvalidDimensionException

By passing embeddings explicitly, ChromaDB skips its default model
and uses our pre-computed 1024-dim vectors instead.

WHAT HAPPENS WHEN WE STORE A CHUNK:
─────────────────────────────────────
1. We pass text to BAAI model
2. BAAI model returns 1024-dim vector [0.23, -0.41, 0.87...]
3. We pass vector + text + metadata to ChromaDB
4. ChromaDB stores all three together

Later when searching:
1. User question → converted to 1024-dim vector by same BAAI model
2. ChromaDB finds vectors closest to question vector
3. Returns original text of matching chunks

Input:  list of chunks from chunker.py
Output: chunks stored permanently in ChromaDB with 1024-dim vectors
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(
                os.path.dirname(__file__))))

from sentence_transformers import SentenceTransformer
# SentenceTransformer = library for embedding models
# Used to convert text → 1024-dim vectors
# Must match the model used in rag_retriever.py

from backend.database.chroma_client import get_collections
from backend.etl.pdf_ingestion import load_all_pdfs
from backend.etl.chunker import chunk_all_papers, build_paper_id_map

import re
from pathlib import Path

# ── WHERE JSON FILES LIVE ─────────────────────────────────────
JSON_DIR = Path("data/raw/json")

# ── LOAD EMBEDDING MODEL ONCE ─────────────────────────────────
# Load at module level so it is only loaded once
# Loading takes ~5 seconds — we do not want to repeat this
# for every batch of chunks
print("Loading BAAI/bge-large-en-v1.5 embedding model...")
EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-large-en-v1.5")
print("✅ Embedding model loaded (1024 dimensions)")


def get_related_jsons(paper_id: str) -> list[str]:
    """
    Finds ALL JSON files related to one paper.

    WHY WE NEED THIS:
    ──────────────────
    paper7.pdf → paper_7.json
                 paper_7_1.json
                 paper_7_2.json

    We store all related paper_ids in chunk metadata
    so RAG retriever can link text → structured data.

    Example:
    get_related_jsons("paper_7")
    → ["paper_7", "paper_7_1", "paper_7_2"]
    """

    related = []

    # Check base JSON (paper_7.json)
    if (JSON_DIR / f"{paper_id}.json").exists():
        related.append(paper_id)

    # Check variants (paper_7_1.json to paper_7_5.json)
    for i in range(1, 6):
        variant = f"{paper_id}_{i}"
        if (JSON_DIR / f"{variant}.json").exists():
            related.append(variant)

    return related


def store_chunks(collection, chunks: list[dict]) -> dict:
    """
    Stores chunks in ChromaDB with BAAI embeddings.
    Skips duplicates automatically.

    KEY FIX vs old version:
    ────────────────────────
    OLD: collection.add(ids, documents, metadatas)
         → ChromaDB used its own 384-dim model
         → caused dimension mismatch on query

    NEW: embeddings = BAAI_MODEL.encode(documents)
         collection.add(ids, documents, embeddings, metadatas)
         → ChromaDB stores our 1024-dim vectors
         → matches rag_retriever.py query vectors perfectly

    BATCH PROCESSING:
    ──────────────────
    We process chunks in batches of 50.
    Embedding is done per batch before storing.

    DUPLICATE CHECK:
    ─────────────────
    Before storing, we check which IDs already exist.
    This makes re-running the script safe — no duplicates.
    """

    if not chunks:
        return {"added": 0, "skipped": 0}

    # Get all chunk IDs we want to store
    all_ids = [chunk["id"] for chunk in chunks]

    # Check which IDs already exist in ChromaDB
    existing    = collection.get(ids=all_ids)
    existing_ids = set(existing["ids"])

    # Filter to only NEW chunks
    new_chunks = [
        chunk for chunk in chunks
        if chunk["id"] not in existing_ids
    ]

    skipped = len(chunks) - len(new_chunks)

    if not new_chunks:
        return {"added": 0, "skipped": skipped}

    # Store in batches of 50
    BATCH_SIZE = 50
    added      = 0

    for i in range(0, len(new_chunks), BATCH_SIZE):

        batch = new_chunks[i : i + BATCH_SIZE]

        # Prepare parallel lists for ChromaDB
        ids       = [chunk["id"]       for chunk in batch]
        documents = [chunk["text"]     for chunk in batch]
        metadatas = [chunk["metadata"] for chunk in batch]

        # Add related_jsons to each chunk's metadata
        for j, chunk in enumerate(batch):
            paper_id = chunk["metadata"]["paper_id"]
            related  = get_related_jsons(paper_id)
            # Store as comma-separated string
            # ChromaDB metadata only accepts strings not lists
            metadatas[j]["related_jsons"] = ",".join(related)

        # ── CRITICAL FIX ─────────────────────────────────────
        # Embed documents manually using BAAI model
        # This produces 1024-dim vectors matching rag_retriever.py
        # Without this, ChromaDB uses its 384-dim default model
        # causing InvalidDimensionException on every query
        embeddings = EMBEDDING_MODEL.encode(
            documents,
            show_progress_bar = False,
            batch_size        = 32
        ).tolist()
        # .tolist() converts numpy array → Python list
        # ChromaDB requires Python list not numpy array

        # Store batch in ChromaDB with explicit embeddings
        collection.add(
            ids        = ids,
            documents  = documents,
            embeddings = embeddings,   # ← 1024-dim BAAI vectors
            metadatas  = metadatas
        )

        added += len(batch)

        # Show progress
        total_new = len(new_chunks)
        print(f"    Stored {min(i + BATCH_SIZE, total_new)}"
              f"/{total_new} chunks...", end="\r")

    print()

    return {"added": added, "skipped": skipped}


def embed_all_papers() -> None:
    """
    Complete pipeline: PDF → text → chunks → ChromaDB.

    Calls all previous files in order:
    1. pdf_ingestion.load_all_pdfs()   → read 52 PDFs
    2. chunker.build_paper_id_map()    → paper1 → paper_1
    3. chunker.chunk_all_papers()      → section-aware chunks
    4. store_chunks()                  → embed + save to ChromaDB

    Run this ONCE after setting up your PDFs.
    Re-run when adding new papers.
    Duplicates are automatically skipped.

    NOTE: With section-aware chunker, each paper now produces:
    - 1 abstract chunk  (section=abstract)
    - 1 conclusion chunk (section=conclusion)
    - N body chunks      (section=body)
    This improves retrieval for questions like:
    "What is the objective?" → finds abstract chunk
    "What are the conclusions?" → finds conclusion chunk
    """

    print("=" * 55)
    print("embedder.py — Storing Chunks in ChromaDB")
    print("=" * 55)
    print(f"Embedding model: BAAI/bge-large-en-v1.5 (1024-dim)")

    # Step 1: Connect to ChromaDB
    print("\n[Step 1] Connecting to ChromaDB...")
    fsam_collection, user_collection = get_collections()
    print(f"✅ Connected. Current chunks: {fsam_collection.count()}")

    # Step 2: Load all PDFs
    print("\n[Step 2] Loading PDFs...")
    papers = load_all_pdfs()
    print(f"✅ Loaded {len(papers)} PDFs")

    # Step 3: Build paper_id mapping
    print("\n[Step 3] Building paper ID map...")
    pdf_stems = [p["pdf_stem"] for p in papers]
    id_map    = build_paper_id_map(pdf_stems)
    print(f"✅ Map built for {len(id_map)} papers")

    # Step 4: Chunk all papers with section-aware chunker
    print("\n[Step 4] Chunking papers (section-aware)...")
    all_chunks = chunk_all_papers(papers, id_map)

    # Count section types
    abstract_count   = sum(1 for c in all_chunks if c["metadata"].get("section") == "abstract")
    conclusion_count = sum(1 for c in all_chunks if c["metadata"].get("section") == "conclusion")
    body_count       = sum(1 for c in all_chunks if c["metadata"].get("section") == "body")

    print(f"✅ Created {len(all_chunks)} total chunks")
    print(f"   Abstract chunks:   {abstract_count}")
    print(f"   Conclusion chunks: {conclusion_count}")
    print(f"   Body chunks:       {body_count}")

    # Step 5: Embed and store in ChromaDB
    print("\n[Step 5] Embedding and storing in ChromaDB...")
    print(f"   Using BAAI/bge-large-en-v1.5 (1024-dim)")
    print(f"   This may take 5-10 minutes for 52 papers...")
    result = store_chunks(fsam_collection, all_chunks)
    print(f"✅ Added:   {result['added']} new chunks")
    print(f"✅ Skipped: {result['skipped']} existing chunks")

    # Final stats
    final_count = fsam_collection.count()
    print(f"\n{'='*55}")
    print(f"✅ ChromaDB now contains {final_count} chunks")
    print(f"   All embeddings: 1024-dim BAAI vectors")
    print(f"   Ready for RAG search")
    print(f"{'='*55}")


# ── TEST ──────────────────────────────────────────────────────
if __name__ == "__main__":
    embed_all_papers()