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

from backend.database.chroma_client import get_collections
# get_collections() → (fsam_collection, user_collection)

# How many results to return per search
# 5 = enough context without overwhelming Groq
N_RESULTS = 5


def search_chunks(question: str,
                  search_fsam: bool = True,
                  search_user: bool = True) -> list[dict]:
    """
    Searches ChromaDB for chunks relevant to the question.

    HOW collection.query() WORKS:
    ───────────────────────────────
    1. Takes question text
    2. Converts to vector using embedding function
    3. Finds N_RESULTS vectors closest to question vector
    4. Returns original text + metadata of those chunks

    PARAMETERS:
    ────────────
    search_fsam = True  → search your 57 pre-loaded papers
    search_user = True  → search user uploaded papers
    Both = True         → search everything (default)

    DISTANCE SCORE:
    ────────────────
    ChromaDB returns a distance score for each result.
    Lower distance = more similar = better match.

    distance = 0.0  → perfect match (identical text)
    distance = 0.5  → very similar meaning
    distance = 1.0  → somewhat related
    distance = 2.0  → not related

    We filter out results with distance > 1.0
    to avoid returning irrelevant passages.
    """

    fsam_col, user_col = get_collections()

    all_results = []

    # Search fsam_papers collection
    if search_fsam and fsam_col.count() > 0:
        fsam_results = fsam_col.query(
            query_texts = [question],
            # query_texts must be a list even for one question
            # ChromaDB converts this to a vector and searches

            n_results   = N_RESULTS,
            # Return top N_RESULTS most similar chunks

            include     = ["documents", "metadatas", "distances"]
            # documents = original text of each chunk
            # metadatas = paper_id, chunk_index etc.
            # distances = similarity score (lower = better)
        )
        all_results.extend(
            parse_query_results(fsam_results, source="fsam")
        )

    # Search user_papers collection
    if search_user and user_col.count() > 0:
        user_results = user_col.query(
            query_texts = [question],
            n_results   = N_RESULTS,
            include     = ["documents", "metadatas", "distances"]
        )
        all_results.extend(
            parse_query_results(user_results, source="user")
        )

    # Sort all results by distance (best matches first)
    all_results.sort(key=lambda x: x["distance"])
    # lambda x: x["distance"] = sort by distance value
    # Lower distance = better match = comes first

    # Filter out poor matches
    all_results = [r for r in all_results if r["distance"] < 1.0]
    # Keep only results with distance < 1.0
    # Higher distance = too different = not useful

    # Return top N_RESULTS overall
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
            # Used to fetch structured data alongside text answer

            "distance":  round(dist, 4),
            # How similar this chunk is to the question
            # Rounded to 4 decimal places for readability

            "source":    source
            # "fsam" = from your pre-loaded papers
            # "user" = from user uploaded paper
        })

    return parsed


def retrieve(question: str,
             search_fsam: bool = True,
             search_user: bool = True) -> dict:
    """
    Main function — retrieves relevant passages for a question.

    Called by:
    - router.py when question needs RAG answer
    - answer_generator.py to get context for Groq

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
        passages = search_chunks(question, search_fsam, search_user)

        return {
            "question": question,
            "passages": passages,
            "count":    len(passages),
            "error":    None
        }

    except Exception as e:
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

    test_questions = [
        "Why does grain size decrease in AFSD?",
        #"How does rotation speed affect microstructure?",
        #"What is the recrystallization mechanism in FSAM?",
        #"What happens when traverse velocity increases?",
    ]

    for question in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {question}")
        print(f"{'='*60}")

        result = retrieve(question)

        if result["error"]:
            print(f"❌ Error: {result['error']}")
            continue

        print(f"Found {result['count']} relevant passages:\n")

        for i, passage in enumerate(result["passages"], 1):
            print(f"  [{i}] Paper: {passage['paper_id']}"
                  f"  Distance: {passage['distance']}"
                  f"  Source: {passage['source']}")
            print(f"      {passage['text'][:150]}...")
            print()