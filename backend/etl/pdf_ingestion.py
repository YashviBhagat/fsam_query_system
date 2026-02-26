"""
pdf_ingestion.py — Read PDFs and Extract Text
===============================================
ONE JOB ONLY: Open PDF files and return their text.

"""
import os
import fitz
from pathlib import Path

# Where your PDF files live
PDF_DIR = Path("data/raw/pdfs")

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Opens ONE PDF and returns ALL its text as a string.

    HOW IT WORKS:
    ─────────────
    Step 1: fitz.open() → opens the PDF file
    Step 2: Loop through every page
    Step 3: page.get_text() → extracts text from that page
    Step 4: Join all pages together
    Step 5: Return full text

    WHY TRY/EXCEPT:
    ───────────────
    Some PDFs fail:
    - Password protected → cannot open
    - Scanned images     → no text layer
    - Corrupted files    → damaged

    try/except catches these without crashing everything.
    Returns "" (empty string) for failed PDFs.

    Example:
    extract_text_from_pdf(Path("data/raw/pdfs/paper1.pdf"))
    → returns "Abstract: This study investigates..."
    """
    try:
        # Open the PDF
        # str(pdf_path) converts Path object → string
        # fitz.open() needs a string not a Path object
        doc = fitz.open(str(pdf_path))

        pages_text = []

        # Loop through every page
        # doc.page_count = total pages (e.g. 12)
        # range(12) = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        for page_num in range(doc.page_count):

            # Get page object
            page = doc[page_num]

            # Extract all text from this page
            # Returns a string with everything on the page
            page_text = page.get_text()

            pages_text.append(page_text)

        # Always close file to free memory
        doc.close()

        # Join all pages with double newline
        # Preserves separation between pages
        # ["page1 text", "page2 text"] → "page1 text\n\npage2 text"
        full_text = "\n\n".join(pages_text)

        return full_text

    except Exception as e:
        print(f"  ⚠️  Could not read {pdf_path.name}: {e}")
        return ""
        # Return empty string so pipeline continues

def load_all_pdfs() -> list[dict]:
    """
    Reads ALL PDFs from data/raw/pdfs/ folder.
    Returns a list — one item per PDF.

    Each item looks like:
    {
        "pdf_name":  "paper1.pdf",
        "pdf_stem":  "paper1",          ← filename without extension
        "text":      "Abstract: This study...",
        "page_count": 12
    }

    Similar to loader.py in ETL pipeline:
    loader.py    → loads JSON files → returns list of dicts
    load_all_pdfs() → loads PDF files → returns list of dicts

    Same pattern, different file type.
    """

    # Find all PDF files
    # Path.glob("*.pdf") = find all files matching *.pdf
    # sorted() = alphabetical order
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"⚠️  No PDF files found in {PDF_DIR}")
        return []

    papers = []

    for pdf_path in pdf_files:
        print(f"  📄 Reading: {pdf_path.name}")

        # Extract text from this PDF
        text = extract_text_from_pdf(pdf_path)

        if not text.strip():
            # text.strip() removes whitespace
            # If empty after stripping → PDF had no readable text
            print(f"     ⚠️  No text extracted")
            continue
            # continue = skip this PDF, move to next one

        # Get page count for metadata
        try:
            doc        = fitz.open(str(pdf_path))
            page_count = doc.page_count
            doc.close()
        except:
            page_count = 0

        papers.append({
            "pdf_name":   pdf_path.name,       # "paper1.pdf"
            "pdf_stem":   pdf_path.stem,        # "paper1"
            "text":       text,                 # full extracted text
            "page_count": page_count            # number of pages
        })

    print(f"\n✅ Loaded text from {len(papers)}/{len(pdf_files)} PDFs")
    return papers

def process_uploaded_pdf(pdf_bytes: bytes, filename: str, user_collection) -> dict:
    """
    Processes a PDF uploaded by a user through Streamlit.

    DIFFERENCE FROM load_all_pdfs:
    ────────────────────────────────
    load_all_pdfs  → reads files FROM DISK
    process_uploaded_pdf → receives BYTES from Streamlit uploader

    Steps:
    1. Save bytes to temp file
    2. Extract text using fitz
    3. Split into chunks
    4. Store in user_collection (separate from your 57 papers)
    5. Delete temp file
    """
    import re
    from backend.etl.chunker import split_into_chunks
    from backend.database.chroma_client import get_collections

    # Save bytes to temp file
    temp_dir  = Path("data/temp")
    os.makedirs(temp_dir, exist_ok=True)

    temp_path = temp_dir / filename
    with open(temp_path, "wb") as f:
        f.write(pdf_bytes)
        # "wb" = write binary mode

    # Create paper_id from filename
    paper_id = Path(filename).stem
    paper_id = re.sub(r'[^a-zA-Z0-9_]', '_', paper_id)
    # "My Paper (2024)" → "My_Paper__2024_"

    # Extract text
    text = extract_text_from_pdf(temp_path)

    if not text.strip():
        os.remove(temp_path)
        return {
            "filename": filename,
            "chunks":   0,
            "status":   "failed - no text extracted"
        }

    # Split into chunks
    chunks = split_into_chunks(text, paper_id)

    # Store in user collection
    added = 0
    for chunk in chunks:
        existing = user_collection.get(ids=[chunk["id"]])
        if len(existing["ids"]) == 0:
            user_collection.add(
                ids       = [chunk["id"]],
                documents = [chunk["text"]],
                metadatas = [chunk["metadata"]]
            )
            added += 1

    # Clean up temp file
    os.remove(temp_path)

    return {
        "filename":     filename,
        "paper_id":     paper_id,
        "total_chunks": len(chunks),
        "added_chunks": added,
        "status":       "success"
    }


# ── TEST ──────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 50)
    print("pdf_ingestion.py — Test")
    print("=" * 50)

    papers = load_all_pdfs()

    if papers:
        # Show sample from first paper
        first = papers[0]
        print(f"\n--- First paper sample ---")
        print(f"File:   {first['pdf_name']}")
        print(f"Pages:  {first['page_count']}")
        print(f"Words:  {len(first['text'].split())}")

        print(f"\nFirst 200 characters:")
        print(first['text'][:200])