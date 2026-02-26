"""
pdf_ingestion.py — Read PDFs and Extract Text
===============================================
ONE JOB ONLY: Open PDF files and return their text.

"""
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