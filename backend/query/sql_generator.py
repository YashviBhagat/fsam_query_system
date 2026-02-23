"""
sql_generator.py — Convert User Questions to SQL Using Groq
=============================================================

WHY THIS FILE EXISTS:
─────────────────────
Users ask questions in natural language:
    "What is the hardness of AA6061 at 1000 rpm?"
    "Which alloy has the highest UTS?"
    "Compare grain size of AA6061 vs AA7075"

SQL databases only understand SQL:
    SELECT paper_id, hardness_min, hardness_unit
    FROM papers
    WHERE base_alloy = 'AA6061'
    AND rotation_speed_min = 1000

This file uses Groq LLM to translate natural language → SQL.

HOW IT WORKS:
─────────────
1. User asks a question
2. fuzzy_matcher finds the alloy name (typo-proof)
3. sql_generator sends to Groq:
   - The user question
   - The matched alloy name
   - ALL column names from database (so Groq knows what exists)
   - Rules to follow
4. Groq returns a valid SQL query
5. We run that SQL on SQLite
6. Return results to user
"""

import os
import re
import sqlite3
import json
from groq import Groq
from dotenv import load_dotenv
from backend.query.fuzzy_matcher import (
    find_alloy_in_question,
    find_all_alloys_in_question,
    detect_alloy_series
)

load_dotenv()

DB_PATH  = "data/processed/fsam_data.db"
client   = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL    = "llama-3.3-70b-versatile"


def get_column_info() -> str:
    """
    Fetches all column names and types from the database.
    This is sent to Groq so it knows exactly what columns exist.

    Returns a formatted string like:
    paper_id (TEXT)
    base_alloy (TEXT)
    hardness_min (REAL)
    hardness_unit (TEXT)
    ...
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(papers)")
    columns = cursor.fetchall()
    conn.close()

    # Format: "column_name (TYPE)"
    col_info = "\n".join([f"{col[1]} ({col[2]})" for col in columns])
    return col_info


def get_sample_values() -> str:
    """
    Fetches sample values for key text columns.
    Helps Groq understand what values actually exist.

    Example output:
    base_alloy values: AA6061, AA7075, AA5083, AA2024...
    process_category values: FSAM, AFSD, FSPAM...
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    samples = {}

    # Key columns where Groq needs to know actual values
    text_columns = [
        "base_alloy",
        "process_category",
        "grain_morphology",
        "cooling_method",
        "tool_material",
        "pin_geometry",
        "defect_type",
        "recrystallization_type",
    ]

    for col in text_columns:
        try:
            cursor.execute(f"""
                SELECT DISTINCT {col}
                FROM papers
                WHERE {col} IS NOT NULL
                LIMIT 10
            """)
            values = [str(row[0]) for row in cursor.fetchall()]
            samples[col] = ", ".join(values)
        except:
            pass

    conn.close()

    result = "\n".join([f"{col}: {vals}" for col, vals in samples.items()])
    return result


def build_system_prompt(col_info: str, sample_values: str) -> str:
    """
    Builds the system prompt sent to Groq.
    This tells Groq exactly how to behave and what rules to follow.
    """
    return f"""You are an expert SQL generator for a materials science database
about Friction Stir Additive Manufacturing (FSAM/AFSD) research papers.

DATABASE TABLE: papers
COLUMNS:
{col_info}

SAMPLE VALUES IN KEY COLUMNS:
{sample_values}

YOUR JOB:
Convert the user's natural language question into a valid SQLite SQL query.

RULES YOU MUST FOLLOW:
1. Always return ONLY a valid SQL query — no explanation, no markdown, no backticks
2. Always SELECT the relevant columns including units (e.g. hardness_unit with hardness_min)
3. Always include paper_id and base_alloy in SELECT
4. For numeric comparisons use the _min column for lower bound, _max for upper bound
5. For range queries use BETWEEN or >= and <=
6. For alloy series use LIKE (e.g. base_alloy LIKE 'AA6%' for 6xxx series)
7. For comparisons between alloys use WHERE base_alloy IN ('AA6061', 'AA7075')
8. For "highest" or "best" use ORDER BY column DESC LIMIT 5
9. For "lowest" use ORDER BY column ASC LIMIT 5
10. Always handle NULL values — use WHERE column IS NOT NULL when filtering
11. For unit columns always SELECT them alongside their numeric columns
12. If user asks about multiple properties, SELECT all relevant columns
13. Never use * — always specify exact columns needed

COLUMN NAMING RULES:
- Hardness:        hardness_min, hardness_max, hardness_unit
- Yield strength:  yield_strength_min, yield_strength_max, yield_strength_unit
- UTS:             uts_min, uts_max, uts_unit
- Elongation:      elongation_min, elongation_max, elongation_unit
- Rotation speed:  rotation_speed_min, rotation_speed_max, rotation_speed_unit
- Traverse speed:  traverse_velocity_min, traverse_velocity_max, traverse_velocity_unit
- Grain size:      final_grain_size_min, final_grain_size_max, final_grain_size_unit
- Temperature:     peak_temperature, peak_temperature_max, peak_temperature_unit
- Grain size init: initial_grain_size, initial_grain_size_unit

EXAMPLE QUERIES:
User: "What is hardness of AA6061?"
SQL:  SELECT paper_id, base_alloy, hardness_min, hardness_max, hardness_unit
      FROM papers
      WHERE base_alloy = 'AA6061'
      AND hardness_min IS NOT NULL

User: "Which alloy has highest UTS?"
SQL:  SELECT paper_id, base_alloy, uts_max, uts_unit
      FROM papers
      WHERE uts_max IS NOT NULL
      ORDER BY uts_max DESC
      LIMIT 5

User: "Compare grain size of AA6061 and AA7075"
SQL:  SELECT paper_id, base_alloy,
             final_grain_size_min, final_grain_size_max, final_grain_size_unit
      FROM papers
      WHERE base_alloy IN ('AA6061', 'AA7075')
      AND final_grain_size_min IS NOT NULL
      ORDER BY base_alloy

User: "Papers with rotation speed above 1000 rpm"
SQL:  SELECT paper_id, base_alloy,
             rotation_speed_min, rotation_speed_max, rotation_speed_unit
      FROM papers
      WHERE rotation_speed_min > 1000
      ORDER BY rotation_speed_min DESC

User: "What is traverse speed of AA6061 with grain size around 6.5 um?"
SQL:  SELECT paper_id, base_alloy,
             traverse_velocity_min, traverse_velocity_unit,
             final_grain_size_min, final_grain_size_unit
      FROM papers
      WHERE base_alloy = 'AA6061'
      AND final_grain_size_min <= 6.5
      AND final_grain_size_max >= 6.5
"""


def generate_sql(question: str) -> dict:
    """
    Main function — takes a user question and returns SQL + results.

    RETURNS a dict with:
    {
        "question":      original question,
        "matched_alloy": alloy found (or None),
        "sql":           generated SQL query,
        "results":       list of result rows,
        "columns":       column names for display,
        "error":         error message (or None)
    }
    """
    # ── Step 1: Find alloys in question ─────────────────
    alloys_found   = find_all_alloys_in_question(question)
    series_pattern = detect_alloy_series(question)

    matched_alloys = [a["matched_alloy"] for a in alloys_found]

    # ── Step 2: Build context for Groq ──────────────────
    col_info      = get_column_info()
    sample_values = get_sample_values()
    system_prompt = build_system_prompt(col_info, sample_values)

    # Enrich the question with matched alloy info
    enriched_question = question
    if matched_alloys:
        enriched_question += f"\n\n[SYSTEM NOTE: Alloys detected in question: {', '.join(matched_alloys)}. Use these exact names in your SQL WHERE clause.]"
    if series_pattern:
        enriched_question += f"\n\n[SYSTEM NOTE: Alloy series detected. Use LIKE '{series_pattern}' in WHERE clause.]"

    # ── Step 3: Ask Groq to generate SQL ────────────────
    try:
        response = client.chat.completions.create(
            model    = MODEL,
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": enriched_question}
            ],
            temperature = 0,      # 0 = deterministic, consistent SQL
            max_tokens  = 500
        )

        sql = response.choices[0].message.content.strip()

        # Clean up any markdown Groq might add
        sql = re.sub(r'```sql', '', sql)
        sql = re.sub(r'```',    '', sql)
        sql = sql.strip()

    except Exception as e:
        return {
            "question":      question,
            "matched_alloy": matched_alloys,
            "sql":           None,
            "results":       [],
            "columns":       [],
            "error":         f"Groq error: {str(e)}"
        }

    # ── Step 4: Run SQL on database ─────────────────────
    try:
        conn    = sqlite3.connect(DB_PATH)
        cursor  = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()

    except Exception as e:
        return {
            "question":      question,
            "matched_alloy": matched_alloys,
            "sql":           sql,
            "results":       [],
            "columns":       [],
            "error":         f"SQL error: {str(e)}\nSQL was: {sql}"
        }

    return {
        "question":      question,
        "matched_alloy": matched_alloys,
        "sql":           sql,
        "results":       results,
        "columns":       columns,
        "error":         None
    }


# ── TEST ─────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 60)
    print("sql_generator.py — Natural Language to SQL Test")
    print("=" * 60)

    test_questions = [
        "What is the hardness of AA6061?",
        "Which alloy has the highest UTS?",
        "Compare grain size of AA6061 and AA7075",
        "Show papers with rotation speed above 1000 rpm",
        "What is traverse speed of AA6061 with grain size around 6 um?",
        "What is the yield strength of 6xxx series alloys?",
        "What is the traverse speed  of 7075 alloy which temper condition is T6? "
    ]

    for question in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {question}")
        print(f"{'='*60}")

        result = generate_sql(question)

        if result["matched_alloy"]:
            print(f"Alloy detected: {result['matched_alloy']}")

        print(f"\nGenerated SQL:")
        print(f"{result['sql']}")

        if result["error"]:
            print(f"\n❌ Error: {result['error']}")
        else:
            print(f"\nResults ({len(result['results'])} rows):")
            # Print column headers
            print("  " + " | ".join(result["columns"]))
            print("  " + "-" * 60)
            # Print first 5 rows
            for row in result["results"][:5]:
                print("  " + " | ".join(str(v) for v in row))