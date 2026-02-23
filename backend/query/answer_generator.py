"""
answer_generator.py — Format SQL Results as Readable Answers
=============================================================

WHY THIS FILE EXISTS:
─────────────────────
sql_generator.py returns raw data tuples:
    ('paper_36', 'AA6061', 60.0, 60.0, 'mm/min', 4.0, 6.0, 'µm')

Users expect a clean readable answer:
    "AA6061 processed at 60 mm/min traverse velocity
     achieved a final grain size of 4.0–6.0 µm"

This file uses Groq to format raw SQL results
into a natural language answer with proper units.

HOW IT WORKS:
─────────────
1. Receives: original question + SQL results + column names
2. Sends to Groq: question + formatted table of results
3. Groq writes: clean narrative answer with units
4. Returns: formatted answer ready for user
"""

import os
from groq import Groq
from dotenv import load_dotenv
from backend.query.sql_generator import generate_sql

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL  = "llama-3.3-70b-versatile"


def format_results_as_table(columns: list, results: list) -> str:
    """
    Converts raw SQL results into a readable text table.
    This table is sent to Groq for formatting.

    Input:
    columns = ['paper_id', 'base_alloy', 'hardness_min', 'hardness_unit']
    results = [('paper_8', 'AA6061', 71.93, 'HV'), ...]

    Output:
    paper_id | base_alloy | hardness_min | hardness_unit
    paper_8  | AA6061     | 71.93        | HV
    paper_36 | AA6061     | 95.0         | HV
    """
    if not results:
        return "No results found."

    # Header row
    header = " | ".join(columns)
    separator = "-" * len(header)

    # Data rows
    rows = []
    for row in results:
        formatted_row = " | ".join(
            str(v) if v is not None else "N/A"
            for v in row
        )
        rows.append(formatted_row)

    return "\n".join([header, separator] + rows)


def format_units_in_answer(answer: str) -> str:
    """
    Ensures units are properly formatted in the answer.
    Fixes common unit display issues.
    """
    # Ensure units are spaced correctly
    replacements = {
        "MPa":   " MPa",
        "HV":    " HV",
        "rpm":   " rpm",
        "mm/min":" mm/min",
        "µm":    " µm",
        "°C":    " °C",
        "kN":    " kN",
        "Nm":    " Nm",
        "mm":    " mm",
        "%":     "%",
    }

    for unit, replacement in replacements.items():
        answer = answer.replace(f"  {unit}", replacement)

    return answer


def generate_answer(question: str) -> dict:
    """
    Complete pipeline: question → SQL → results → formatted answer.

    STEPS:
    1. Generate SQL and run it (via sql_generator)
    2. Format results as text table
    3. Send to Groq for natural language formatting
    4. Return clean answer

    RETURNS:
    {
        "question": original question,
        "answer":   formatted natural language answer,
        "table":    raw results as formatted table,
        "sql":      the SQL that was run,
        "rows":     number of results found,
        "error":    error message or None
    }
    """

    # ── Step 1: Generate SQL and get results ─────────────
    sql_result = generate_sql(question)

    if sql_result["error"]:
        return {
            "question": question,
            "answer":   f"Sorry, I could not answer this question. {sql_result['error']}",
            "table":    None,
            "sql":      sql_result["sql"],
            "rows":     0,
            "error":    sql_result["error"]
        }

    if not sql_result["results"]:
        return {
            "question": question,
            "answer":   "No data found matching your query. Try rephrasing or checking the alloy name.",
            "table":    None,
            "sql":      sql_result["sql"],
            "rows":     0,
            "error":    None
        }

    # ── Step 2: Format results as table ──────────────────
    table = format_results_as_table(
        sql_result["columns"],
        sql_result["results"]
    )

    # ── Step 3: Ask Groq to write a natural answer ────────
    system_prompt = """You are a materials science research assistant
specializing in Friction Stir Additive Manufacturing (FSAM).

Your job is to answer the user's question using the database
results provided. Follow these rules:

1. Always include specific numbers AND units in your answer
2. If multiple results exist, summarize the range
3. Mention the alloy name in your answer
4. Keep the answer concise — 2 to 4 sentences maximum
5. End with the most important finding
6. Format numbers cleanly (e.g. 71.93–88.53 HV not 71.93 HV to 88.53 HV)
7. If comparing alloys, clearly state which performed better
8. Always mention how many papers the data comes from
"""

    user_message = f"""User question: {question}

Database results:
{table}

Please answer the question using these results.
Include all relevant values with their units."""

    try:
        response = client.chat.completions.create(
            model       = MODEL,
            messages    = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message}
            ],
            temperature = 0.3,   # slight creativity for natural language
            max_tokens  = 500
        )

        answer = response.choices[0].message.content.strip()
        answer = format_units_in_answer(answer)

    except Exception as e:
        # If Groq fails, fall back to showing the raw table
        answer = f"Here are the results:\n\n{table}"

    return {
        "question": question,
        "answer":   answer,
        "table":    table,
        "sql":      sql_result["sql"],
        "rows":     len(sql_result["results"]),
        "error":    None
    }


# ── TEST ─────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 60)
    print("answer_generator.py — Full Pipeline Test")
    print("=" * 60)

    test_questions = [
        "What is the hardness of AA6061?",
        #"Which alloy has the highest UTS?",
        #"Compare grain size of AA6061 and AA7075",
        #"What is traverse speed of AA6061 with grain size around 6 um?",
    ]

    for question in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {question}")
        print(f"{'='*60}")

        result = generate_answer(question)

        print(f"\n📊 Raw Results ({result['rows']} rows):")
        print(result["table"])

        print(f"\n💬 Answer:")
        print(result["answer"])