"""
rag_retriever.py — Search ChromaDB with User Question
=======================================================
ONE JOB ONLY: Take a user question, search ChromaDB,
return the most relevant text passages.

HOW SEMANTIC SEARCH WORKS:
───────────────────────────
Normal search (SQL LIKE):
    WHERE text LIKE '%grain size%'
    → only finds exact words "grain size"
    → misses: "grain refinement", "crystallite size", "microstructure"

Semantic search (ChromaDB):
    "why does grain size decrease?"
    → converted to vector
    → finds chunks with SIMILAR MEANING
    → finds: "grain refinement", "recrystallization", "microstructure"
    → much more powerful for natural language questions

Input:  user question (string)
Output: list of relevant passages with source paper info
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(
                os.path.dirname(__file__))))

from sentence_transformers import SentenceTransformer
from backend.database.chroma_client import get_collections

# ── Embedding model ───────────────────────────────────────────
# CRITICAL: Must use SAME model for both indexing and querying
# Your fsam_papers collection was indexed with BAAI/bge-large-en-v1.5
# Your user_papers collection is now also indexed with same model
# Using a different model causes dimension mismatch errors
print("Loading BAAI/bge-large-en-v1.5 embedding model...")
EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-large-en-v1.5")
print("✅ Embedding model loaded")

# How many results to return per search
N_RESULTS = 5


def search_chunks(question: str,
                  search_fsam: bool = True,
                  search_user: bool = True,
                  user_paper_id: str = None) -> list[dict]:
    """
    Searches ChromaDB for chunks relevant to the question.

    HOW IT WORKS:
    ─────────────
    1. Embed the question using BAAI model → 1024-dim vector
    2. Search fsam_papers collection (if search_fsam=True)
    3. Search user_papers collection (if search_user=True)
       - If user_paper_id provided → filter to THAT paper only
       - If user_paper_id is None  → search ALL user papers
    4. Combine, sort by distance, filter poor matches
    5. Return top N_RESULTS passages

    PARAMETERS:
    ────────────
    question      = user's natural language question
    search_fsam   = True → search your 57 pre-loaded papers
    search_user   = True → search user uploaded papers
    user_paper_id = "1_s2_0_S026412752200418X_main"
                  → filter user search to this paper only
                  → None = search all user papers

    DISTANCE SCORE:
    ────────────────
    ChromaDB returns a distance score for each result.
    Lower distance = more similar = better match.

    distance = 0.0  → perfect match (identical text)
    distance = 0.3  → very similar meaning (excellent)
    distance = 0.5  → similar meaning (good)
    distance = 0.8  → somewhat related (weak)
    distance > 1.0  → not related → filtered out

    WHY WE EMBED MANUALLY:
    ───────────────────────
    We pass query_embeddings instead of query_texts
    because both collections use BAAI/bge-large-en-v1.5 (1024-dim)
    but ChromaDB's default model is all-MiniLM-L6-v2 (384-dim).
    Passing embeddings directly bypasses ChromaDB's model entirely.
    """

    fsam_col, user_col = get_collections()

    all_results = []

    # ── Embed the question manually with BAAI model ──────────
    # This produces a 1024-dimensional vector
    # MUST match the dimensions stored in both collections
    question_embedding = EMBEDDING_MODEL.encode(
        [question]
    ).tolist()
    # .tolist() converts numpy array → Python list
    # ChromaDB requires Python list, not numpy array

    # ── Search fsam_papers collection ───────────────────────
    if search_fsam and fsam_col.count() > 0:
        try:
            fsam_results = fsam_col.query(
                query_embeddings = question_embedding,
                # Pass pre-computed embedding, not raw text
                # Bypasses ChromaDB's default 384-dim model

                n_results        = N_RESULTS,
                include          = ["documents", "metadatas", "distances"]
            )
            all_results.extend(
                parse_query_results(fsam_results, source="fsam")
            )
        except Exception as e:
            print(f"⚠️  fsam_papers search error: {e}")

    # ── Search user_papers collection ───────────────────────
    if search_user and user_col.count() > 0:
        try:
            if user_paper_id:
                # ── Filter to specific uploaded paper ────────
                # $eq is required ChromaDB syntax (NOT eq)
                # This returns ONLY chunks from that paper
                user_results = user_col.query(
                    query_embeddings = question_embedding,
                    n_results        = N_RESULTS,
                    where            = {
                        "paper_id": {"$eq": user_paper_id}
                    },
                    include          = ["documents", "metadatas", "distances"]
                )
            else:
                # ── Search ALL user papers (no filter) ───────
                user_results = user_col.query(
                    query_embeddings = question_embedding,
                    n_results        = N_RESULTS,
                    include          = ["documents", "metadatas", "distances"]
                )

            all_results.extend(
                parse_query_results(user_results, source="user")
            )

        except Exception as e:
            print(f"⚠️  user_papers search error: {e}")

    # ── Sort all results by distance (best matches first) ────
    all_results.sort(key=lambda x: x["distance"])

    
    # ── Filter out poor matches ──────────────────────────────
    all_results = [r for r in all_results if r["distance"] < 1.0]

    
    # ── Return top N_RESULTS overall ────────────────────────
    return all_results[:N_RESULTS]


def parse_query_results(results: dict, source: str) -> list[dict]:
    """
    Converts ChromaDB's raw query output into clean list of dicts.

    ChromaDB returns results in this structure:
    {
        "documents": [["text1", "text2", "text3"]],
        "metadatas": [[{...}, {...}, {...}]],
        "distances": [[0.12, 0.34, 0.56]]
    }

    Notice the double list [[...]] — ChromaDB wraps results
    in an extra list because you can query multiple questions
    at once. We always query one question so we take [0].

    We convert this to:
    [
        {
            "text":      "The grain size decreased...",
            "paper_id":  "paper_27",
            "distance":  0.12,
            "source":    "fsam",
            "chunk_idx": 3
        },
        ...
    ]
    """

    parsed = []

    # Guard against empty results
    if not results or not results.get("documents"):
        return parsed

    if not results["documents"][0]:
        return parsed

    # results["documents"][0] = list of texts for our one question
    # results["metadatas"][0] = list of metadata dicts
    # results["distances"][0] = list of distance scores
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        # zip() pairs up items from multiple lists:
        # zip([a,b,c], [1,2,3]) → [(a,1), (b,2), (c,3)]

        parsed.append({
            "text":      doc,
            # The actual text passage from the paper

            "paper_id":  meta.get("paper_id", "unknown"),
            # Which paper this chunk came from

            "chunk_idx": meta.get("chunk_index", 0),
            # Which chunk number within the paper

            "related_jsons": meta.get("related_jsons", ""),
            # Comma-separated list of related JSON paper_ids

            "distance":  round(dist, 4),
            # How similar this chunk is to the question
            # Rounded to 4 decimal places for readability
            # relevance = 1 - distance (shown in UI)

            "source":    source
            # "fsam" = from your pre-loaded 57 papers
            # "user" = from user uploaded paper
        })

    return parsed


def retrieve(question: str,
             search_fsam: bool = True,
             search_user: bool = True,
             user_paper_id: str = None) -> dict:
    """
    Main function — retrieves relevant passages for a question.

    Called by:
    - router.py when question needs RAG answer
    - answer_generator.py to get context for Groq

    PARAMETERS:
    ────────────
    question      = user's natural language question
    search_fsam   = True → include 57 pre-loaded FSAM papers
    search_user   = True → include user uploaded papers
    user_paper_id = filter user search to specific paper
                    None = search all user papers

    Returns:
    {
        "question":  "Why does grain size decrease in AFSD?",
        "passages":  [
            {
                "text":     "The grain size decreased due to...",
                "paper_id": "paper_27",
                "distance": 0.12,
                "source":   "fsam"
            },
            ...
        ],
        "count":     5,
        "error":     None
    }
    """

    try:
        passages = search_chunks(
            question      = question,
            search_fsam   = search_fsam,
            search_user   = search_user,
            user_paper_id = user_paper_id
            # Passes paper_id filter down to search_chunks
        )

        return {
            "question": question,
            "passages": passages,
            "count":    len(passages),
            "error":    None
        }

    except Exception as e:
        print(f"❌ retrieve() error: {e}")
        return {
            "question": question,
            "passages": [],
            "count":    0,
            "error":    str(e)
        }


# ── TEST ──────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 60)
    print("rag_retriever.py — Semantic Search Test")
    print("=" * 60)

    # Test 1: Search fsam_papers
    print("\n--- Test 1: Search FSAM database ---")
    result = retrieve(
        question    = "Why does grain size decrease in AFSD?",
        search_fsam = True,
        search_user = False
    )

    if result["error"]:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"Found {result['count']} passages:")
        for i, p in enumerate(result["passages"], 1):
            print(f"  [{i}] {p['paper_id']} | dist: {p['distance']} | {p['text'][:100]}...")

    # Test 2: Search specific uploaded paper
    print("\n--- Test 2: Search uploaded paper ---")
    result = retrieve(
        question      = "What is the main objective of this study?",
        search_fsam   = False,
        search_user   = True,
        user_paper_id = "1_s2_0_S0264127525005660_main"  # ← 2025 paper
    )

    if result["error"]:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"Found {result['count']} passages:")
        for i, p in enumerate(result["passages"], 1):
            print(f"  [{i}] {p['paper_id']} | dist: {p['distance']} | {p['text'][:150]}...")