"""
router.py — Decide SQL vs RAG per Question
===========================================
ONE JOB ONLY: Look at the user question and decide
whether to use SQL or RAG to answer it.

TWO TYPES OF QUESTIONS:
────────────────────────
SQL questions → ask for specific numbers/data
    "What is the hardness of AA6061?"
    "Which alloy has highest UTS?"
    "Show papers with rotation speed above 1000 rpm"

RAG questions → ask for explanation/mechanism
    "Why does grain size decrease in AFSD?"
    "How does rotation speed affect microstructure?"
    "What happens when traverse velocity increases?"
    "Explain the recrystallization mechanism"

HOW WE DECIDE:
───────────────
We look for trigger words in the question:
    "why", "how", "explain", "mechanism" → RAG
    "what is", "show", "compare"         → SQL

Some questions need BOTH:
    "What is hardness of AA6061 and why is it high?"
    → SQL for the number
    → RAG for the explanation
    → Combined answer
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(
                os.path.dirname(__file__))))

from backend.query.answer_generator import generate_answer
# generate_answer() = SQL pipeline (question → SQL → answer)

from backend.query.rag_retriever import retrieve
# retrieve() = RAG pipeline (question → ChromaDB → passages)

from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL  = "llama-3.3-70b-versatile"


# ── TRIGGER WORDS ─────────────────────────────────────────────

# These words in a question → use RAG
RAG_TRIGGERS = [
    "why", "how", "explain", "mechanism", "reason",
    "cause", "effect", "what happens", "describe",
    "what is the role", "influence", "impact",
    "relationship", "affect", "because", "due to",
    "process", "behavior", "behaviour", "phenomenon"
]

# These words in a question → use SQL
SQL_TRIGGERS = [
    "what is the", "what are the", "show", "list",
    "highest", "lowest", "maximum", "minimum",
    "compare", "which alloy", "how many", "average",
    "value", "hardness", "uts", "yield strength",
    "grain size", "rotation speed", "traverse"
]


def classify_question(question: str) -> str:
    """
    Classifies question as "sql", "rag", or "both".

    HOW IT WORKS:
    ─────────────
    1. Convert question to lowercase
    2. Check if any RAG trigger words are present
    3. Check if any SQL trigger words are present
    4. Decide based on what was found

    RULES:
    ──────
    RAG triggers found + SQL triggers found → "both"
    Only RAG triggers found                 → "rag"
    Only SQL triggers found                 → "sql"
    Nothing found                           → "rag" (default)
    Why RAG as default?
    → RAG can handle any question
    → SQL fails if no alloy/parameter mentioned

    Examples:
    "What is hardness of AA6061?"     → sql
    "Why does grain size decrease?"   → rag
    "What is hardness and why high?"  → both
    """

    q = question.lower()
    # lowercase for case-insensitive matching
    # "WHY" and "why" and "Why" all become "why"

    has_rag = any(trigger in q for trigger in RAG_TRIGGERS)
    # any() = True if at least one trigger word found
    # "why does grain size" → "why" found → has_rag = True

    has_sql = any(trigger in q for trigger in SQL_TRIGGERS)
    # "what is the hardness" → "what is the" found → has_sql = True

    if has_rag and has_sql:
        return "both"
    elif has_rag:
        return "rag"
    elif has_sql:
        return "sql"
    else:
        return "rag"
        # Default to RAG — handles open-ended questions better


def format_rag_answer(question: str, passages: list[dict]) -> str:
    """
    Sends RAG passages to Groq to write a natural language answer.

    WHAT WE SEND TO GROQ:
    ──────────────────────
    1. The user question
    2. The 5 most relevant passages from ChromaDB
    3. Instructions to write a clear answer with citations

    Groq reads the passages and synthesizes a coherent answer
    just like a researcher reading papers and summarizing them.
    """

    if not passages:
        return "No relevant passages found in the database."

    # Format passages as numbered list for Groq
    passages_text = ""
    for i, p in enumerate(passages, 1):
        passages_text += f"\n[{i}] From {p['paper_id']}:\n"
        passages_text += f"{p['text']}\n"

    system_prompt = """You are a materials science expert specializing
in Friction Stir Additive Manufacturing (FSAM/AFSD).

Answer the user's question using ONLY the provided passages.
Follow these rules:
1. Give a clear direct answer in 3-5 sentences
2. Cite which paper supports each claim e.g. (paper_27)
3. Use proper materials science terminology
4. If passages don't fully answer the question, say so
5. Never make up information not in the passages
"""

    user_message = f"""Question: {question}

Relevant passages from research papers:
{passages_text}

Please answer the question based on these passages."""

    try:
        response = client.chat.completions.create(
            model       = MODEL,
            messages    = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message}
            ],
            temperature = 0.3,
            max_tokens  = 600
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        # Fallback: return raw passages if Groq fails
        return f"Based on research papers:\n\n{passages_text}"


def route_question(question: str,
                   search_user: bool = False) -> dict:
    """
    Main function — routes question to SQL, RAG, or both.

    RETURNS:
    ─────────
    {
        "question":    original question,
        "route":       "sql" / "rag" / "both",
        "sql_answer":  answer from SQL pipeline (or None),
        "rag_answer":  answer from RAG pipeline (or None),
        "passages":    list of relevant passages (or []),
        "sql":         the SQL query used (or None),
        "rows":        number of SQL results (or 0),
        "error":       error message (or None)
    }
    """

    # Step 1: Classify the question
    route = classify_question(question)

    result = {
        "question":   question,
        "route":      route,
        "sql_answer": None,
        "rag_answer": None,
        "passages":   [],
        "sql":        None,
        "rows":       0,
        "error":      None
    }

    # Step 2: SQL path
    if route in ["sql", "both"]:
        sql_result = generate_answer(question)
        result["sql_answer"] = sql_result["answer"]
        result["sql"]        = sql_result["sql"]
        result["rows"]       = sql_result["rows"]

        if sql_result["error"]:
            result["error"] = sql_result["error"]

    # Step 3: RAG path
    if route in ["rag", "both"]:
        rag_result = retrieve(
            question,
            search_fsam = True,
            search_user = search_user
            # search_user = True when user has uploaded a paper
        )

        result["passages"] = rag_result["passages"]

        if rag_result["passages"]:
            result["rag_answer"] = format_rag_answer(
                question,
                rag_result["passages"]
            )
        else:
            result["rag_answer"] = "No relevant passages found."

    return result


# ── TEST ──────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 60)
    print("router.py — Question Routing Test")
    print("=" * 60)

    test_questions = [
        # SQL questions
        "What is the hardness of AA6061?",
        "Which alloy has the highest UTS?",

        # RAG questions
        "Why does grain size decrease in AFSD?",
        "How does rotation speed affect microstructure?",

        # Both
        "What is hardness of AA6061 and why is it high?",
    ]

    for question in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {question}")

        result = route_question(question)
        print(f"Route: {result['route'].upper()}")

        if result["sql_answer"]:
            print(f"\n📊 SQL Answer:")
            print(f"   {result['sql_answer'][:200]}")

        if result["rag_answer"]:
            print(f"\n📖 RAG Answer:")
            print(f"   {result['rag_answer'][:200]}")