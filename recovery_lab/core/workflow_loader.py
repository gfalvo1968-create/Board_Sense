"""Load Recovery Lab workflow books from each lab folder."""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


def load_workflow(lab_key):
    safe_key = str(lab_key or "").strip().lower().replace("-", "_")
    if not safe_key or "/" in safe_key or "\\" in safe_key or ".." in safe_key:
        return None
    path = BASE_DIR / safe_key / "workflow.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def attach_workflows(labs):
    enriched = []
    for lab in labs or []:
        item = dict(lab)
        workflow = load_workflow(item.get("key"))
        item["workflow_available"] = workflow is not None
        if workflow:
            item["workflow"] = workflow
        enriched.append(item)
    return enriched
