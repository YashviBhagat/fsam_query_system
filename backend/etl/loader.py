import json
from pathlib import Path

# Where your JSON files live
JSON_DIR = Path("data/raw/json")


def load_all_json_files() -> list[dict]:
    """
    Reads every .json file from data/raw/json/
    Returns a list where each item is one paper's data.
    """
    json_files = list(JSON_DIR.glob("*.json"))

    if not json_files:
        print(f"⚠️  No JSON files found in {JSON_DIR}")
        print("    Add your JSON files and try again.")
        return []

    papers = []
    for file in json_files:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)

        papers.append({
            "paper_id": file.stem,   # "paper01.json" → "paper01"
            "file":     file.name,
            "data":     data
        })
        print(f"✅ Loaded: {file.name}")

    print(f"\n📂 Total papers loaded: {len(papers)}")
    return papers


if __name__ == "__main__":
    papers = load_all_json_files()

    if papers:
        print("\n--- First paper structure ---")
        first = papers[0]["data"]
        for section in first.keys():
            print(f"  {section}")
