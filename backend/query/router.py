"""
router.py — Decide SQL vs RAG per Question
===========================================
ONE JOB ONLY: Look at the user question and decide
whether to use SQL or RAG to answer it.

THREE TYPES OF QUESTIONS:
──────────────────────────
SQL questions → ask for specific numbers/data
    "What is the hardness of AA6061?"
    "Which alloy has highest UTS?"

RAG questions → ask for explanation/mechanism
    "Why does grain size decrease in AFSD?"
    "How does rotation speed affect microstructure?"

UPLOADED PAPER questions → ask about user's specific paper
    "What is the base alloy in the paper?"
    "What does this study conclude?"
    → Skips SQL entirely, searches ONLY uploaded paper
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(
                os.path.dirname(__file__))))

from backend.query.answer_generator import generate_answer
from backend.query.rag_retriever    import retrieve
from groq       import Groq
from dotenv     import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL  = "llama-3.3-70b-versatile"


# ── TRIGGER WORDS ─────────────────────────────────────────────

# These words → user is asking about their uploaded paper
# When found + user has uploaded a paper → skip SQL, search uploaded paper only
USER_PAPER_TRIGGERS = [
    "the paper", "this paper", "my paper",
    "uploaded paper", "the study", "this study",
    "the article", "this article", "the document",
    "in this", "in the paper", "from the paper",
    "the authors", "the researchers", "the uploaded",
    "that paper", "this research", "the research"
]

# These words → use RAG pipeline
RAG_TRIGGERS = [
    "why", "how", "explain", "mechanism", "reason",
    "cause", "effect", "what happens", "describe",
    "what is the role", "influence", "impact",
    "relationship", "affect", "because", "due to",
    "process", "behavior", "behaviour", "phenomenon"
]

# These words → use SQL pipeline
SQL_TRIGGERS = [
    "what is the", "what are the", "show", "list",
    "highest", "lowest", "maximum", "minimum",
    "compare", "which alloy", "how many", "average",
    "value", "hardness", "uts", "yield strength",
    "grain size", "rotation speed", "traverse"
]


# ── FUNCTION 1: Classify Question ─────────────────────────────

def classify_question(question: str) -> str:
    """
    Classifies question as "sql", "rag", or "both".

    Rules:
    RAG + SQL triggers found → "both"
    Only RAG triggers        → "rag"
    Only SQL triggers        → "sql"
    Nothing found            → "rag" (safe default)
    """

    q       = question.lower()
    has_rag = any(trigger in q for trigger in RAG_TRIGGERS)
    has_sql = any(trigger in q for trigger in SQL_TRIGGERS)

    if has_rag and has_sql:
        return "both"
    elif has_rag:
        return "rag"
    elif has_sql:
        return "sql"
    else:
        return "rag"


# ── FUNCTION 2: Format RAG Answer ─────────────────────────────

def format_rag_answer(question: str, passages: list[dict]) -> str:
    """
    Sends RAG passages to Groq to write a natural language answer.
    Uses ONLY the provided passages — no outside knowledge.
    """

    if not passages:
        return "No relevant passages found in the database."

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
5. NEVER make up information not in the passages
6. Answer ONLY from the provided passages — do NOT use general knowledge
7. If the answer is directly stated in a passage, state it clearly
"""

    user_message = f"""Question: {question}

Relevant passages from research papers:
{passages_text}

Please answer the question based ONLY on these passages."""

    try:
        response = client.chat.completions.create(
            model       = MODEL,
            messages    = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message}
            ],
            temperature = 0.1,
            # 0.1 = very deterministic
            # Important for factual questions about uploaded paper
            max_tokens  = 600
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Based on research papers:\n\n{passages_text}"


# ── FUNCTION 3: Main Route Function ───────────────────────────

def route_question(question: str, search_user: bool = False) -> dict:
    """
    Main function — routes question to SQL, RAG, or both.

    SPECIAL CASE:
    If user asks about "the paper" / "this paper" / "uploaded paper"
    AND they have uploaded a paper (search_user=True)
    → Skip SQL entirely
    → Search ONLY the uploaded paper
    → Return answer from that paper only

    This prevents the system from answering about the database
    when user clearly means their uploaded paper.
    """

    # Initialize result dict
    result = {
        "question":     question,
        "route":        "rag",
        "final_answer": None,
        "sql_answer":   None,
        "rag_answer":   None,
        "passages":     [],
        "sql":          None,
        "rows":         0,
        "error":        None
    }

    # ── SPECIAL CASE: Question about uploaded paper ───────────
    # Check BEFORE normal routing so SQL never runs for these
    q_lower             = question.lower()
    asking_about_upload = any(t in q_lower for t in USER_PAPER_TRIGGERS)

    if asking_about_upload and search_user:
        # User is asking about their uploaded paper specifically
        # Force RAG on user collection only — skip SQL and database
        rag_result = retrieve(
            question,
            search_fsam = False,   # skip your 57 papers
            search_user = True     # only search uploaded paper
        )

        result["route"]    = "rag"
        result["passages"] = rag_result.get("passages", [])

        if result["passages"]:
            result["rag_answer"]   = format_rag_answer(
                question,
                result["passages"]
            )
            result["final_answer"] = result["rag_answer"]
        else:
            result["final_answer"] = (
                "Could not find relevant information in your uploaded paper. "
                "Try rephrasing your question."
            )

        return result
        # Returns here — SQL never runs

    # ── NORMAL ROUTING ────────────────────────────────────────
    route          = classify_question(question)
    result["route"] = route

    # SQL path
    if route in ["sql", "both"]:
        try:
            sql_result = generate_answer(question)
            result["sql_answer"] = sql_result.get("answer")
            result["sql"]        = sql_result.get("sql")
            result["rows"]       = sql_result.get("rows", 0)

            if sql_result.get("error"):
                result["error"] = sql_result["error"]
        except Exception as e:
            result["error"] = f"SQL error: {str(e)}"

    # RAG path
    if route in ["rag", "both"]:
        try:
            rag_result = retrieve(
                question,
                search_fsam = True,
                search_user = search_user
            )

            result["passages"] = rag_result.get("passages", [])

            if result["passages"]:
                result["rag_answer"] = format_rag_answer(
                    question,
                    result["passages"]
                )
            else:
                result["rag_answer"] = "No relevant passages found."

        except Exception as e:
            result["error"] = f"RAG error: {str(e)}"

    # Build final answer
    if route == "both":
        parts = []
        if result["sql_answer"]:
            parts.append(f"📊 Data:\n{result['sql_answer']}")
        if result["rag_answer"]:
            parts.append(f"📖 Explanation:\n{result['rag_answer']}")
        result["final_answer"] = "\n\n".join(parts)
    elif route == "sql":
        result["final_answer"] = result["sql_answer"]
    elif route == "rag":
        result["final_answer"] = result["rag_answer"]

    if not result["final_answer"]:
        result["final_answer"] = "Could not generate an answer. Try rephrasing."

    return result


# ── TEST ──────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 60)
    print("router.py — Question Routing Test")
    print("=" * 60)

    test_questions = [
        ("What is the hardness of AA6061?",               "expect: sql"),
        ("Which alloy has the highest UTS?",              "expect: sql"),
        ("Why does grain size decrease in AFSD?",         "expect: rag"),
        ("How does rotation speed affect microstructure?","expect: rag"),
        ("What is hardness of AA6061 and why is it high?","expect: both"),
    ]

    for question, expectation in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {question}  ({expectation})")

        result = route_question(question)
        print(f"Route: {result['route'].upper()}")

        if result["sql_answer"]:
            print(f"\n📊 SQL: {result['sql_answer'][:200]}")
        if result["rag_answer"]:
            print(f"\n📖 RAG: {result['rag_answer'][:200]}")