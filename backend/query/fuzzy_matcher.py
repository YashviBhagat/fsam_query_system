# """
# fuzzy_matcher.py — Detect Alloy Names in User Questions
# =========================================================

# WHY THIS FILE EXISTS:
# ─────────────────────
# Users never type alloy names perfectly. They write:
#     "AA606l"        instead of "AA6061"  (typo)
#     "7075"          instead of "AA7075"  (missing prefix)
#     "al 6061"       instead of "AA6061"  (wrong case)
#     "6061 aluminum" instead of "AA6061"  (extra words)

# Without fuzzy matching ALL of these return zero results.
# RapidFuzz finds the closest match even with mistakes.

# HOW RAPIDFUZZ WORKS:
# ─────────────────────
# It gives a similarity score from 0 to 100:
#     "AA6061" vs "AA606l"  → 97  ✅ match (one char different)
#     "AA6061" vs "7075"    → 20  ❌ no match (too different)
#     "AA6061" vs "AA6061"  → 100 ✅ perfect

# We only accept matches above 80% similarity.
# """

# import sqlite3
# from rapidfuzz import process, fuzz

# DB_PATH = "data/processed/fsam_data.db"

# # Only accept matches above this score
# # 80 = catches typos but avoids wrong matches
# SIMILARITY_THRESHOLD = 80


# def get_all_alloys() -> list[str]:
#     """
#     Loads every unique alloy name from your database.
#     This is our master list to match against.

#     Example output:
#     ['AA6061', 'AA7075', 'AA5083', 'AA2024', '7A04', ...]
#     """
#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()

#     cursor.execute("""
#         SELECT DISTINCT base_alloy
#         FROM papers
#         WHERE base_alloy IS NOT NULL
#         ORDER BY base_alloy
#     """)

#     alloys = [row[0] for row in cursor.fetchall()]
#     conn.close()
#     return alloys


# def normalize(text: str) -> str:
#     """
#     Cleans text before comparing.
#     Removes spaces, converts to uppercase.

#     "aa 6061"  → "AA6061"
#     "Al-7075"  → "AL-7075"
#     """
#     return text.upper().replace(" ", "")


# def find_alloy_in_question(question: str) -> dict | None:
#     """
#     Scans user question and returns best matching alloy.
#     Uses multiple scoring strategies to catch:
#     - Typos (AA606l → AA6061)
#     - Missing prefix (5083 → AA5083)
#     - Lowercase (al6061 → AA6061)
#     """
#     alloys = get_all_alloys()
#     if not alloys:
#         return None

#     normalized_alloys = [normalize(a) for a in alloys]

#     # Single words + adjacent word pairs
#     words = question.split()
#     candidates = list(words)
#     for i in range(len(words) - 1):
#         candidates.append(words[i] + words[i+1])

#     best_match = None
#     best_score = 0
#     best_input = None

#     for candidate in candidates:
#         normalized_candidate = normalize(candidate)

#         # Strategy 1: exact ratio (good for close matches)
#         result1 = process.extractOne(
#             normalized_candidate,
#             normalized_alloys,
#             scorer=fuzz.ratio
#         )

#         # Strategy 2: partial ratio
#         # good for "5083" matching "AA5083"
#         # looks for candidate INSIDE the alloy name
#         result2 = process.extractOne(
#             normalized_candidate,
#             normalized_alloys,
#             scorer=fuzz.partial_ratio
#         )

#         # Strategy 3: token sort ratio
#         # good for "al 6061" matching "AA6061"
#         result3 = process.extractOne(
#             normalized_candidate,
#             normalized_alloys,
#             scorer=fuzz.token_sort_ratio
#         )

#         # Take the best score across all 3 strategies
#         for result in [result1, result2, result3]:
#             if result:
#                 _, score, idx = result
#                 if score > best_score and score >= SIMILARITY_THRESHOLD:
#                     best_score = score
#                     best_match = alloys[idx]
#                     best_input = candidate

#     if best_match:
#         return {
#             "matched_alloy": best_match,
#             "input_text":    best_input,
#             "score":         best_score
#         }
#     return None


# def find_all_alloys_in_question(question: str) -> list[dict]:
#     """
#     Finds ALL alloys mentioned in a question.
#     Uses same multi-strategy approach.
#     """
#     alloys = get_all_alloys()
#     normalized_alloys = [normalize(a) for a in alloys]

#     words = question.split()
#     candidates = list(words)
#     for i in range(len(words) - 1):
#         candidates.append(words[i] + words[i+1])

#     found = []
#     seen  = set()

#     for candidate in candidates:
#         normalized_candidate = normalize(candidate)

#         for scorer in [fuzz.ratio, fuzz.partial_ratio, fuzz.token_sort_ratio]:
#             result = process.extractOne(
#                 normalized_candidate,
#                 normalized_alloys,
#                 scorer=scorer
#             )

#             if result:
#                 _, score, idx = result
#                 original = alloys[idx]
#                 if score >= SIMILARITY_THRESHOLD and original not in seen:
#                     found.append({
#                         "matched_alloy": original,
#                         "input_text":    candidate,
#                         "score":         score
#                     })
#                     seen.add(original)

#     return found

# # ── TEST ─────────────────────────────────────────────────────
# if __name__ == "__main__":

#     print("=" * 55)
#     print("fuzzy_matcher.py — Alloy Detection Test")
#     print("=" * 55)

#     alloys = get_all_alloys()
#     print(f"\n📋 Alloys in database ({len(alloys)}):")
#     for a in alloys:
#         print(f"   {a}")

#     print(f"\n--- Testing typos and variations ---")
#     tests = [
#         "What is the hardness of AA6061?",
#         "What is hardness of AA606l?",
#         "Give me results for 7075",
#         "Show properties of al 6061",
#         "What process used for 5083?",
#         "Show data for AA8090",
#         "What is hardness of xyz999?",
#     ]

#     for q in tests:
#         result = find_alloy_in_question(q)
#         if result:
#             print(f"\n  Q: {q}")
#             print(f"     Matched: '{result['matched_alloy']}'  "
#                   f"Score: {result['score']}%")
#         else:
#             print(f"\n  Q: {q}")
#             print(f"     No alloy found")

#     print(f"\n--- Multi alloy detection ---")
#     q = "Compare AA6061 and AA7075 hardness"
#     results = find_all_alloys_in_question(q)
#     print(f"\n  Q: {q}")
#     for r in results:
#         print(f"     Found: {r['matched_alloy']}  "
#               f"Score: {r['score']}%")


"""
fuzzy_matcher.py — Detect Alloy Names in User Questions
=========================================================

STRATEGY:
─────────
1. Extract the alloy NUMBER from user input (6061, 7075, 5083)
2. Find alloys in database containing that number
3. Use fuzz.ratio only for final ranking (strict matching)

This avoids false matches like "al 6061" → "5B70 Al alloy"
because we anchor matching on the actual alloy number.
"""

import re
import sqlite3
from rapidfuzz import process, fuzz

DB_PATH = "data/processed/fsam_data.db"
SIMILARITY_THRESHOLD = 80


def get_all_alloys() -> list[str]:
    """
    Loads every unique alloy name from your database.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT base_alloy
        FROM papers
        WHERE base_alloy IS NOT NULL
        ORDER BY base_alloy
    """)
    alloys = [row[0] for row in cursor.fetchall()]
    conn.close()
    return alloys


def normalize(text: str) -> str:
    """
    Removes spaces, converts to uppercase.
    "aa 6061" → "AA6061"
    """
    return text.upper().replace(" ", "").replace("-", "")


def extract_alloy_numbers(text: str) -> list[str]:
    """
    Pulls out 4-digit alloy numbers from any text.

    "al 6061 alloy"  → ["6061"]
    "AA7075-T6"      → ["7075"]
    "5083"           → ["5083"]
    "xyz999"         → []
    """
    return re.findall(r'\b[1-9]\d{3}\b', text)


def find_alloy_in_question(question: str) -> dict | None:
    """
    Finds the best matching alloy in a user question.

    APPROACH:
    Step 1 — Extract 4-digit numbers from question
             "al 6061" → ["6061"]

    Step 2 — Filter database alloys that contain that number
             6061 → ["AA6061", "AA2024/AA6061/..."]

    Step 3 — Among filtered alloys, pick shortest/simplest match
             Prefers "AA6061" over "AA2024/AA6061/AA5083"

    Step 4 — If no number found, fall back to strict fuzz.ratio
             only on single word candidates
    """
    alloys = get_all_alloys()
    if not alloys:
        return None

    # ── Strategy 1: Number-anchored matching ────────────
    # Extract alloy numbers from question
    numbers = extract_alloy_numbers(question)

    if numbers:
        for number in numbers:
            # Find all database alloys containing this number
            candidates = [a for a in alloys if number in a]

            if candidates:
                # Prefer the simplest (shortest) alloy name
                # "AA6061" is better than "AA2024/AA6061/AA5083"
                best = min(candidates, key=len)
                return {
                    "matched_alloy": best,
                    "input_text":    number,
                    "score":         100
                }

    # ── Strategy 2: Strict fuzz.ratio fallback ───────────
    # Used when no number found (e.g. "7A04", "5B70")
    normalized_alloys = [normalize(a) for a in alloys]
    words = question.split()

    best_match = None
    best_score = 0
    best_input = None

    for word in words:
        # Only try words that look like alloy names
        # Must contain at least one letter AND one digit
        if not (re.search(r'[A-Za-z]', word) and
                re.search(r'\d', word)):
            continue

        result = process.extractOne(
            normalize(word),
            normalized_alloys,
            scorer=fuzz.ratio
        )

        if result:
            _, score, idx = result
            if score > best_score and score >= SIMILARITY_THRESHOLD:
                best_score = score
                best_match = alloys[idx]
                best_input = word

    if best_match:
        return {
            "matched_alloy": best_match,
            "input_text":    best_input,
            "score":         best_score
        }

    return None


def find_all_alloys_in_question(question: str) -> list[dict]:
    """
    Finds ALL alloys mentioned in a question.
    Used for comparison questions.

    "Compare AA6061 and AA7075" → [AA6061, AA7075]
    """
    alloys = get_all_alloys()
    found = []
    seen  = set()

    # ── Strategy 1: Find all 4-digit numbers ────────────
    numbers = extract_alloy_numbers(question)

    for number in numbers:
        candidates = [a for a in alloys if number in a]
        if candidates:
            best = min(candidates, key=len)
            if best not in seen:
                found.append({
                    "matched_alloy": best,
                    "input_text":    number,
                    "score":         100
                })
                seen.add(best)

    # ── Strategy 2: Strict fuzz for non-numeric alloys ──
    normalized_alloys = [normalize(a) for a in alloys]
    words = question.split()

    for word in words:
        if not (re.search(r'[A-Za-z]', word) and
                re.search(r'\d', word)):
            continue

        result = process.extractOne(
            normalize(word),
            normalized_alloys,
            scorer=fuzz.ratio
        )

        if result:
            _, score, idx = result
            original = alloys[idx]
            if score >= SIMILARITY_THRESHOLD and original not in seen:
                found.append({
                    "matched_alloy": original,
                    "input_text":    word,
                    "score":         score
                })
                seen.add(original)

    return found


def detect_alloy_series(question: str) -> str | None:
    """
    Detects alloy series like "6xxx" or "7000 series".
    Returns SQL LIKE pattern.

    "6xxx series" → "6%"
    "7000 series" → "7%"
    """
    pattern = re.search(
        r'\b([1-8])(?:xxx|000)\s*(?:series|alloy|aluminum)?\b',
        question,
        re.IGNORECASE
    )
    if pattern:
        return f"{pattern.group(1)}%"
    return None


# ── TEST ─────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 55)
    print("fuzzy_matcher.py — Alloy Detection Test")
    print("=" * 55)

    alloys = get_all_alloys()
    print(f"\n📋 Alloys in database ({len(alloys)}):")
    for a in alloys:
        print(f"   {a}")

    print(f"\n--- Testing typos and variations ---")
    tests = [
        "What is the hardness of AA6061?",
        "What is hardness of AA606l?",
        "Give me results for 7075",
        "Show properties of al 6061",
        "What process used for 5083?",
        "Show data for AA8090",
        "What is hardness of xyz999?",
        "Show 6xxx series hardness",
    ]

    for q in tests:
        result = find_alloy_in_question(q)
        series = detect_alloy_series(q)
        if result:
            print(f"\n  Q: {q}")
            print(f"     Matched: '{result['matched_alloy']}'  "
                  f"Score: {round(result['score'])}%")
        elif series:
            print(f"\n  Q: {q}")
            print(f"     Series detected: LIKE '{series}'")
        else:
            print(f"\n  Q: {q}")
            print(f"     No alloy found")

    print(f"\n--- Multi alloy detection ---")
    tests_multi = [
        "Compare AA6061 and AA7075 hardness",
        "What is difference between 5083 and 6061?",
    ]
    for q in tests_multi:
        results = find_all_alloys_in_question(q)
        print(f"\n  Q: {q}")
        for r in results:
            print(f"     Found: {r['matched_alloy']}  "
                  f"Score: {round(r['score'])}%")