import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REFERENCE_DIR = BASE_DIR / "reference_data"

knowledge_base = {}

def load_json_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Autodidact Error] Failed loading {file_path.name}: {e}")
        return []

def load_reference_data():
    global knowledge_base

    knowledge_base = {}

    for json_file in REFERENCE_DIR.glob("*.json"):
        category_name = json_file.stem

        knowledge_base[category_name] = load_json_file(json_file)

        print(f"[Autodidact Loaded] {category_name}")

    print(f"[Autodidact Core Online] Loaded {len(knowledge_base)} knowledge files")

    return knowledge_base

def get_knowledge():
    return knowledge_base
