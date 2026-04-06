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

IMPROVEMENT — SECTION-AWARE CHUNKING:
───────────────────────────────────────
Old approach: split every 500 words regardless of structure
New approach: detect section boundaries (Abstract, Conclusion etc.)
              keep important sections as priority chunks
              then do regular word-count chunking for the rest

This ensures Abstract and Conclusions are always retrievable.

Input:  raw text string + paper_id
Output: list of chunk dicts ready for ChromaDB
"""

import re

# ── CONSTANTS ─────────────────────────────────────────────────
CHUNK_SIZE      = 500   # words per chunk
CHUNK_OVERLAP   = 100   # words shared between consecutive chunks
MIN_CHUNK_WORDS = 50    # skip chunks smaller than this

# Section headers that indicate important content
# These are detected and kept as priority chunks
IMPORTANT_SECTIONS = [
    "abstract",
    "conclusion",
    "conclusions",
    "summary",
    "introduction",
    "results",
    "discussion",
    "findings",
    "objectives",
    "highlights",
]


def clean_text(text: str) -> str:
    """
    Cleans raw PDF text before chunking.

    PDF text extraction is messy:
    - Multiple spaces between words
    - Weird line breaks inside sentences
    - Page numbers floating in the middle
    - Headers/footers repeated on every page
    """

    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)

    # Remove common PDF artifacts — lines that are just numbers
    text = re.sub(r'\n\d+\n', ' ', text)

    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def extract_abstract(text: str) -> str | None:
    """
    Tries to extract the abstract from paper text.

    Looks for text between "Abstract" and the next section header.
    Returns the abstract text if found, None otherwise.

    Example:
    "Abstract This study investigates... 1. Introduction..."
    → "This study investigates..."
    """

    # Pattern: "abstract" followed by text until next section
    # (?i) = case insensitive
    # (.+?) = non-greedy match of any characters
    pattern = r'(?i)abstract\s*(.+?)(?=\n\s*\d+\.|introduction|keywords|1\s+introduction)'

    match = re.search(pattern, text, re.DOTALL)

    if match:
        abstract_text = match.group(1).strip()
        # Only return if it is a reasonable length
        if 50 <= len(abstract_text.split()) <= 500:
            return abstract_text

    return None


def extract_conclusions(text: str) -> str | None:
    """
    Tries to extract the conclusions section from paper text.

    Looks for text starting with "conclusion" or "conclusions"
    and ending at the next major section (references, acknowledgements).

    Returns the conclusions text if found, None otherwise.
    """

    # Pattern: conclusion/conclusions header followed by text
    pattern = r'(?i)(?:conclusion|conclusions)\s*\n?\s*(.+?)(?=references|acknowledgement|acknowledgment|funding|appendix|$)'

    match = re.search(pattern, text, re.DOTALL)

    if match:
        conclusion_text = match.group(1).strip()
        conclusion_text = re.sub(r'^[^A-Za-z]+', '', conclusion_text)
        # Clean up and limit size
        conclusion_text = re.sub(r'\s+', ' ', conclusion_text)
        words = conclusion_text.split()

        if len(words) >= MIN_CHUNK_WORDS:
            # If very long, take first 600 words
            if len(words) > 600:
                conclusion_text = ' '.join(words[:600])
            return conclusion_text

    return None


def make_chunk(text: str, paper_id: str, chunk_idx: int,
               start_word: int, section: str = "body") -> dict:
    """
    Creates a single chunk dict ready for ChromaDB.

    Parameters:
    ────────────
    text       = chunk text content
    paper_id   = which paper this chunk is from
    chunk_idx  = chunk number (for unique ID)
    start_word = word position in original text
    section    = "abstract", "conclusion", "body"
                 Used to prioritize retrieval
    """
    words = text.split()
    return {
        "id":   f"{paper_id}_chunk_{chunk_idx}",
        "text": text,
        "metadata": {
            "paper_id":    paper_id,
            "chunk_index": chunk_idx,
            "start_word":  start_word,
            "word_count":  len(words),
            "section":     section,
            # section tag helps identify where chunk came from
            # "abstract"   = first chunk, contains objective
            # "conclusion" = last section, contains findings
            # "body"       = main content
        }
    }


def split_into_chunks(text: str, paper_id: str) -> list[dict]:
    """
    Splits text into overlapping chunks with section awareness.

    STRATEGY:
    ─────────
    Step 1: Extract abstract → add as dedicated chunk
    Step 2: Extract conclusions → add as dedicated chunk
    Step 3: Split full text into regular word-count chunks
    Step 4: Remove duplicates (abstract/conclusion overlap with body)
    Step 5: Return all chunks sorted by position

    WHY THIS IS BETTER:
    ────────────────────
    Old:  "What is the objective?" → might miss abstract chunk
    New:  Abstract is ALWAYS chunk_0 → always findable

    Old:  "What are the conclusions?" → might get methods section
    New:  Conclusion is ALWAYS a dedicated chunk → always findable

    Each chunk contains:
    {
        "id":       "paper_1_chunk_0"
        "text":     "This study investigates..."
        "metadata": {
            "paper_id":    "paper_1"
            "chunk_index": 0
            "start_word":  0
            "word_count":  245
            "section":     "abstract"   ← NEW
        }
    }
    """

    # Step 1: Clean text
    text = clean_text(text)
    words = text.split()

    if len(words) < MIN_CHUNK_WORDS:
        return []

    chunks    = []
    chunk_idx = 0

    # ── Priority Chunk 1: Abstract ───────────────────────────
    # Extract and store abstract as first chunk
    abstract = extract_abstract(text)
    if abstract:
        chunks.append(make_chunk(
            text       = abstract,
            paper_id   = paper_id,
            chunk_idx  = chunk_idx,
            start_word = 0,
            section    = "abstract"
        ))
        chunk_idx += 1
        print(f"    📋 Abstract chunk extracted ({len(abstract.split())} words)")

    # ── Priority Chunk 2: Conclusions ────────────────────────
    # Extract and store conclusions as dedicated chunk
    conclusions = extract_conclusions(text)
    if conclusions:
        # Find approximate word position of conclusions in text
        conclusion_pos = text.lower().find("conclusion")
        if conclusion_pos > 0:
            words_before = len(text[:conclusion_pos].split())
        else:
            words_before = len(words) - len(conclusions.split())

        chunks.append(make_chunk(
            text       = conclusions,
            paper_id   = paper_id,
            chunk_idx  = chunk_idx,
            start_word = words_before,
            section    = "conclusion"
        ))
        chunk_idx += 1
        print(f"    📋 Conclusion chunk extracted ({len(conclusions.split())} words)")

    # ── Regular Chunks: Full Text ────────────────────────────
    # Split full text into word-count chunks with overlap
    # These cover everything including sections we did not extract
    start = 0

    while start < len(words):
        end         = start + CHUNK_SIZE
        chunk_words = words[start:end]
        chunk_text  = " ".join(chunk_words)

        if len(chunk_words) >= MIN_CHUNK_WORDS:
            chunks.append(make_chunk(
                text       = chunk_text,
                paper_id   = paper_id,
                chunk_idx  = chunk_idx,
                start_word = start,
                section    = "body"
            ))
            chunk_idx += 1

        # Move forward by CHUNK_SIZE - CHUNK_OVERLAP
        start += (CHUNK_SIZE - CHUNK_OVERLAP)

    return chunks


def chunk_all_papers(papers: list[dict], paper_id_map: dict) -> list[dict]:
    """
    Chunks ALL papers from pdf_ingestion.load_all_pdfs()

    paper_id_map converts PDF stem → JSON paper_id:
    {
        "paper1":  "paper_1",
        "paper27": "paper_27",
    }

    Returns ALL chunks from ALL papers as one flat list.
    """

    all_chunks = []

    for paper in papers:
        pdf_stem = paper["pdf_stem"]
        paper_id = paper_id_map.get(pdf_stem, pdf_stem)

        chunks = split_into_chunks(paper["text"], paper_id)

        all_chunks.extend(chunks)

        # Count by section type
        abstract_chunks    = sum(1 for c in chunks if c["metadata"]["section"] == "abstract")
        conclusion_chunks  = sum(1 for c in chunks if c["metadata"]["section"] == "conclusion")
        body_chunks        = sum(1 for c in chunks if c["metadata"]["section"] == "body")

        print(f"  ✅ {paper['pdf_name']:30} → {len(chunks)} chunks "
              f"(abs:{abstract_chunks} conc:{conclusion_chunks} body:{body_chunks})")

    print(f"\n  Total chunks: {len(all_chunks)}")
    return all_chunks


def build_paper_id_map(pdf_stems: list[str]) -> dict:
    """
    Builds mapping from PDF stem to JSON paper_id.

    PDF stems:   ["paper1", "paper7", "paper27"]
    JSON ids:    ["paper_1", "paper_7", "paper_27"]
    """

    mapping = {}

    for stem in pdf_stems:
        paper_id = re.sub(r'(paper)(\d+)', r'\1_\2', stem)
        mapping[stem] = paper_id

    return mapping


# ── TEST ──────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 50)
    print("chunker.py — Section-Aware Chunking Test")
    print("=" * 50)

    # Quick test with sample text
    sample_text = """
    Abstract
    This study investigates the effect of rotation speed on the 
    microstructure and mechanical properties of AA6061 aluminum alloy 
    processed by Friction Stir Additive Manufacturing. The main objective 
    is to optimize process parameters for maximum hardness and minimum 
    grain size. Results show that higher rotation speeds produce finer 
    grains due to increased dynamic recrystallization.

    1. Introduction
    Friction Stir Additive Manufacturing (FSAM) is a solid-state process
    that deposits material layer by layer using frictional heat and severe
    plastic deformation. This process has gained significant attention
    for aluminum alloys due to its ability to produce fine-grained
    microstructures without melting.

    2. Experimental Methods
    AA6061-T6 aluminum alloy was used as the feedstock material.
    Rotation speeds of 800, 1000, and 1200 rpm were investigated.
    Traverse speed was held constant at 100 mm/min.
    Hardness testing was performed using Vickers indentation.
    Grain size was measured using EBSD analysis.

    3. Results
    Hardness increased from 65 HV to 89 HV as rotation speed 
    increased from 800 to 1200 rpm. Grain size decreased from 
    8.2 um to 3.1 um over the same range. Dynamic recrystallization
    was identified as the primary grain refinement mechanism.

    Conclusions
    This study demonstrates that rotation speed significantly affects
    the microstructure and mechanical properties of FSAM AA6061.
    Higher rotation speeds of 1200 rpm produced the finest grain size
    of 3.1 um and highest hardness of 89 HV. Dynamic recrystallization
    driven by frictional heat is the dominant microstructural mechanism.
    These findings provide guidance for optimizing FSAM process parameters
    for structural aluminum components.

    References
    [1] Mishra RS, Ma ZY. Friction stir welding and processing...
    [2] Rivera OG et al. Additive friction stir deposition...
    """

    print("\nTesting section extraction:")
    abstract = extract_abstract(sample_text)
    print(f"\nAbstract found: {bool(abstract)}")
    if abstract:
        print(f"  {abstract[:150]}...")

    conclusions = extract_conclusions(sample_text)
    print(f"\nConclusions found: {bool(conclusions)}")
    if conclusions:
        print(f"  {conclusions[:150]}...")

    print("\nTesting full chunking:")
    chunks = split_into_chunks(sample_text, "test_paper")
    print(f"\nTotal chunks: {len(chunks)}")
    for c in chunks:
        print(f"  [{c['metadata']['section']:10}] chunk_{c['metadata']['chunk_index']:02d} "
              f"| {c['metadata']['word_count']} words "
              f"| {c['text'][:60]}...")