"""
embedder.py — Store Text Chunks in ChromaDB
=============================================
ONE JOB ONLY: Take chunks from chunker.py and store
them in ChromaDB as vectors.

WHAT HAPPENS WHEN WE STORE A CHUNK:
─────────────────────────────────────
1. We pass text to ChromaDB
2. ChromaDB passes text through embedding function
3. Embedding function returns vector [0.23, -0.41, 0.87...]
4. ChromaDB stores: vector + original text + metadata

Later when searching:
1. User question → converted to vector
2. ChromaDB finds vectors closest to question vector
3. Returns original text of matching chunks

Input:  list of chunks from chunker.py
Output: chunks stored permanently in ChromaDB
"""

import os
import sys

# Add project root to path so imports work
sys.path.append(os.path.dirname(os.path.dirname(
                os.path.dirname(__file__))))

from backend.database.chroma_client import get_collections
# get_collections() returns (fsam_collection, user_collection)
# We only use fsam_collection here for pre-loaded papers
# user_collection is used when users upload papers at runtime

from backend.etl.pdf_ingestion import load_all_pdfs
# load_all_pdfs() returns list of dicts with text from each PDF

from backend.etl.chunker import chunk_all_papers, build_paper_id_map
# chunk_all_papers() splits all paper texts into chunks
# build_paper_id_map() converts "paper1" → "paper_1"

import re
# re = regular expressions
# Used to find related JSON files for each paper


# ── WHERE JSON FILES LIVE ─────────────────────────────────────
from pathlib import Path
JSON_DIR = Path("data/raw/json")


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
    Stores chunks in ChromaDB. Skips duplicates.

    BATCH PROCESSING:
    ──────────────────
    We store chunks in batches of 50 instead of one at a time.

    One at a time (slow):
    for chunk in 1028 chunks:
        collection.add(one chunk)   ← 1028 separate operations

    Batches of 50 (fast):
    for batch in 21 batches:
        collection.add(50 chunks)   ← 21 operations

    Same result, much faster.

    DUPLICATE CHECK:
    ─────────────────
    Before storing, we check which IDs already exist.
    This makes re-running the script safe — no duplicates.

    collection.get(ids=[...]) → returns existing items
    We filter out already-stored chunks before adding.
    """

    if not chunks:
        return {"added": 0, "skipped": 0}

    # Get all chunk IDs we want to store
    all_ids = [chunk["id"] for chunk in chunks]

    # Check which IDs already exist in ChromaDB
    existing = collection.get(ids=all_ids)
    existing_ids = set(existing["ids"])
    # set() = fast lookup, like a list but O(1) check instead of O(n)

    # Filter to only NEW chunks
    new_chunks = [
        chunk for chunk in chunks
        if chunk["id"] not in existing_ids
    ]
    # List comprehension:
    # "keep chunk if its ID is not already in ChromaDB"

    skipped = len(chunks) - len(new_chunks)

    if not new_chunks:
        return {"added": 0, "skipped": skipped}

    # Store in batches of 50
    BATCH_SIZE = 50
    added      = 0

    for i in range(0, len(new_chunks), BATCH_SIZE):
        # range(0, 1028, 50) = [0, 50, 100, 150, ...]
        # Each iteration processes one batch

        batch = new_chunks[i : i + BATCH_SIZE]
        # new_chunks[0:50]   = first batch
        # new_chunks[50:100] = second batch

        # Prepare data for ChromaDB
        # collection.add() needs three parallel lists:
        # ids, documents, metadatas — all same length
        ids       = [chunk["id"]       for chunk in batch]
        documents = [chunk["text"]     for chunk in batch]
        metadatas = [chunk["metadata"] for chunk in batch]

        # Add related_jsons to each chunk's metadata
        for j, chunk in enumerate(batch):
            paper_id      = chunk["metadata"]["paper_id"]
            related       = get_related_jsons(paper_id)
            # Store as comma-separated string
            # ChromaDB metadata only accepts strings, not lists
            metadatas[j]["related_jsons"] = ",".join(related)

        # Store batch in ChromaDB
        # ChromaDB automatically:
        # 1. Takes documents (text)
        # 2. Passes through embedding function
        # 3. Gets back vectors
        # 4. Stores vectors + metadata + text together
        collection.add(
            ids       = ids,
            documents = documents,
            metadatas = metadatas
        )

        added += len(batch)

        # Show progress
        total_new = len(new_chunks)
        print(f"    Stored {min(i + BATCH_SIZE, total_new)}"
              f"/{total_new} chunks...", end="\r")
        # end="\r" = overwrite same line (progress bar effect)

    print()
    # Print newline after progress bar

    return {"added": added, "skipped": skipped}


def embed_all_papers() -> None:
    """
    Complete pipeline: PDF → text → chunks → ChromaDB.

    Calls all previous files in order:
    1. pdf_ingestion.load_all_pdfs()   → read 52 PDFs
    2. chunker.build_paper_id_map()    → "paper1" → "paper_1"
    3. chunker.chunk_all_papers()      → 1028 chunks
    4. store_chunks()                  → save to ChromaDB

    Run this ONCE after setting up your PDFs.
    Re-run when adding new papers.
    Duplicates are automatically skipped.
    """

    print("=" * 55)
    print("embedder.py — Storing Chunks in ChromaDB")
    print("=" * 55)

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

    # Step 4: Chunk all papers
    print("\n[Step 4] Chunking papers...")
    all_chunks = chunk_all_papers(papers, id_map)
    print(f"✅ Created {len(all_chunks)} total chunks")

    # Step 5: Store in ChromaDB
    print("\n[Step 5] Storing in ChromaDB...")
    result = store_chunks(fsam_collection, all_chunks)
    print(f"✅ Added:   {result['added']} new chunks")
    print(f"✅ Skipped: {result['skipped']} existing chunks")

    # Final stats
    final_count = fsam_collection.count()
    print(f"\n{'='*55}")
    print(f"✅ ChromaDB now contains {final_count} chunks")
    print(f"   Ready for RAG search")
    print(f"{'='*55}")


# ── TEST ──────────────────────────────────────────────────────
if __name__ == "__main__":
    embed_all_papers()