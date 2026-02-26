"""
chunker.py — Split PDF Text into Overlapping Chunks
=====================================================
ONE JOB ONLY: Take raw text and split into smaller chunks.
Nothing else. No reading PDFs. No storing. Just splitting.

WHY CHUNKS?
────────────
paper1.pdf = 11,866 words — too large to search meaningfully.
Chunks of 500 words = precise, targeted search results.

WHY OVERLAP?
─────────────
Without overlap:
    chunk_1: words 0–499
    chunk_2: words 500–999
    Problem: sentence at boundary gets split → context lost

With overlap (100 words):
    chunk_1: words 0–499
    chunk_2: words 400–899  ← 100 words repeated
    chunk_3: words 800–1299
    Benefit: context always preserved at boundaries

Input:  raw text string + paper_id
Output: list of chunk dicts ready for ChromaDB
"""

import re
# re = regular expressions
# Used to clean text before chunking
# re.sub() = substitute/replace patterns


# ── CONSTANTS ─────────────────────────────────────────────────
CHUNK_SIZE    = 500   # words per chunk
CHUNK_OVERLAP = 100   # words shared between consecutive chunks
MIN_CHUNK_WORDS = 50  # skip chunks smaller than this
# Chunks under 50 words are usually:
# headers, page numbers, reference lists — not useful for search


def clean_text(text: str) -> str:
    """
    Cleans raw PDF text before chunking.

    PDF text extraction is messy:
    - Multiple spaces between words
    - Weird line breaks inside sentences
    - Page numbers floating in the middle
    - Headers/footers repeated on every page

    We fix the most common issues here.

    Example:
    "grain  size\n\ndecreased  due  to"
    → "grain size decreased due to"
    """

    # Replace multiple spaces with single space
    # r'\s+' = match one or more whitespace characters
    # ' '    = replace with single space
    text = re.sub(r'\s+', ' ', text)

    # Remove common PDF artifacts
    # Lines that are just numbers (page numbers)
    text = re.sub(r'\n\d+\n', ' ', text)

    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
    # .strip() removes leading/trailing whitespace


def split_into_chunks(text: str, paper_id: str) -> list[dict]:
    """
    Splits text into overlapping chunks of CHUNK_SIZE words.

    HOW IT WORKS STEP BY STEP:
    ───────────────────────────
    text = "The grain size decreased due to dynamic recrystallization..."
    paper_id = "paper_1"

    Step 1: Clean text
    Step 2: Split into words
            ["The", "grain", "size", "decreased", ...]

    Step 3: Take first 500 words → chunk_0
            words[0:500]

    Step 4: Move forward 400 words (500 - 100 overlap)
            Take words[400:900] → chunk_1

    Step 5: Move forward 400 words
            Take words[800:1300] → chunk_2

    Step 6: Repeat until end of paper

    EACH CHUNK RETURNS:
    ────────────────────
    {
        "id":       "paper_1_chunk_0"   ← unique ID for ChromaDB
        "text":     "The grain size..." ← actual text content
        "metadata": {
            "paper_id":    "paper_1"    ← which paper
            "chunk_index": 0            ← chunk number
            "start_word":  0            ← position in paper
            "word_count":  500          ← size of chunk
        }
    }

    The metadata is stored alongside the vector in ChromaDB.
    When RAG finds a matching chunk, metadata tells us
    exactly which paper and position it came from.
    """

    # Step 1: Clean text
    text = clean_text(text)

    # Step 2: Split into words
    words = text.split()
    # "The grain size" → ["The", "grain", "size"]

    if len(words) < MIN_CHUNK_WORDS:
        # Entire text is too short to be useful
        return []

    chunks    = []
    chunk_idx = 0
    start     = 0

    # Step 3-6: Build chunks with overlap
    while start < len(words):

        end = start + CHUNK_SIZE
        # end = where this chunk stops
        # start=0, CHUNK_SIZE=500 → end=500
        # start=400, CHUNK_SIZE=500 → end=900

        chunk_words = words[start:end]
        # words[0:500]   = first 500 words
        # words[400:900] = words 400 to 899

        chunk_text = " ".join(chunk_words)
        # ["The", "grain", "size"] → "The grain size"

        # Only keep chunks with enough content
        if len(chunk_words) >= MIN_CHUNK_WORDS:
            chunks.append({
                # Unique ID — must be unique across ALL chunks in ChromaDB
                # paper_1_chunk_0, paper_1_chunk_1, paper_1_chunk_2...
                "id": f"{paper_id}_chunk_{chunk_idx}",

                # The actual text content
                "text": chunk_text,

                # Metadata stored alongside the vector
                "metadata": {
                    "paper_id":    paper_id,
                    "chunk_index": chunk_idx,
                    "start_word":  start,
                    "word_count":  len(chunk_words)
                }
            })

        # Move to next chunk start position
        # Step forward by (CHUNK_SIZE - CHUNK_OVERLAP)
        # 500 - 100 = 400 → next chunk starts 400 words later
        start     += (CHUNK_SIZE - CHUNK_OVERLAP)
        chunk_idx += 1

    return chunks


def chunk_all_papers(papers: list[dict], paper_id_map: dict) -> list[dict]:
    """
    Chunks ALL papers from pdf_ingestion.load_all_pdfs()

    paper_id_map converts PDF stem → JSON paper_id:
    {
        "paper1":  "paper_1",
        "paper27": "paper_27",
        "paper7":  "paper_7"
    }

    WHY WE NEED paper_id_map:
    ──────────────────────────
    PDF filename:  "paper1"   (no underscore)
    JSON paper_id: "paper_1"  (with underscore)

    Chunks must use the JSON paper_id so RAG can
    link text answers back to structured database data.

    Returns ALL chunks from ALL papers as one flat list.
    """

    all_chunks = []

    for paper in papers:
        # Get the correct paper_id for this PDF
        # paper["pdf_stem"] = "paper1", "paper27" etc.
        pdf_stem = paper["pdf_stem"]
        paper_id = paper_id_map.get(pdf_stem, pdf_stem)
        # .get(key, default) = get value or use default if not found
        # If "paper1" not in map → use "paper1" as fallback

        # Split this paper's text into chunks
        chunks = split_into_chunks(paper["text"], paper_id)

        all_chunks.extend(chunks)
        # extend() adds all items from chunks to all_chunks
        # Like append() but for a list of items at once

        print(f"  ✅ {paper['pdf_name']:20} → {len(chunks)} chunks")

    print(f"\n  Total chunks: {len(all_chunks)}")
    return all_chunks


def build_paper_id_map(pdf_stems: list[str]) -> dict:
    """
    Builds mapping from PDF stem to JSON paper_id.

    PDF stems:   ["paper1", "paper7", "paper27"]
    JSON ids:    ["paper_1", "paper_7", "paper_27"]

    HOW:
    "paper1"  → insert _ → "paper_1"
    "paper27" → insert _ → "paper_27"

    Uses same regex as before:
    r'(paper)(\d+)' finds "paper" then digits
    r'\1_\2' inserts _ between them
    """

    mapping = {}

    for stem in pdf_stems:
        # Insert underscore between "paper" and number
        paper_id = re.sub(r'(paper)(\d+)', r'\1_\2', stem)
        mapping[stem] = paper_id
        # "paper1"  → "paper_1"
        # "paper27" → "paper_27"

    return mapping


# ── TEST ──────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 50)
    print("chunker.py — Test")
    print("=" * 50)

    # Import pdf_ingestion to get paper texts
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(
                    os.path.dirname(__file__))))

    from backend.etl.pdf_ingestion import load_all_pdfs

    # Load all PDFs
    print("\n[Step 1] Loading PDFs...")
    papers = load_all_pdfs()

    # Build paper_id mapping
    print("\n[Step 2] Building paper ID map...")
    pdf_stems = [p["pdf_stem"] for p in papers]
    # ["paper1", "paper2", "paper3"...]

    id_map = build_paper_id_map(pdf_stems)
    print(f"  Sample mappings:")
    for stem, pid in list(id_map.items())[:5]:
        print(f"    {stem} → {pid}")

    # Chunk all papers
    print("\n[Step 3] Chunking all papers...")
    all_chunks = chunk_all_papers(papers, id_map)

    # Show sample chunk
    if all_chunks:
        sample = all_chunks[0]
        print(f"\n--- Sample Chunk ---")
        print(f"ID:         {sample['id']}")
        print(f"Paper:      {sample['metadata']['paper_id']}")
        print(f"Chunk #:    {sample['metadata']['chunk_index']}")
        print(f"Word count: {sample['metadata']['word_count']}")
        print(f"\nFirst 200 characters:")
        print(sample['text'][:200])