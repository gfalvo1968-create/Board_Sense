from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import json

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
IRM_DIR = BASE_DIR / "data" / "irm"
IRM_FILE = IRM_DIR / "sources.json"

IRM_DIR.mkdir(parents=True, exist_ok=True)


class SourceEntry(BaseModel):
    name: str = ""
    phone: str = ""
    address: str = ""
    notes: str = ""
    material: str = ""
    value_level: str = ""
    gps: str = ""
    last_scan: str = ""


def load_sources():
    if not IRM_FILE.exists():
        return []

    with IRM_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_sources(sources):
    with IRM_FILE.open("w", encoding="utf-8") as f:
        json.dump(sources, f, indent=4)


@router.get("/irm/sources")
def get_sources():
    return {
        "status": "success",
        "sources": load_sources()
    }


@router.post("/irm/save-source")
def save_source(entry: SourceEntry):
    sources = load_sources()

    new_entry = entry.dict()
    new_entry["created_at"] = datetime.utcnow().isoformat()
    new_entry["id"] = len(sources) + 1

    sources.append(new_entry)
    save_sources(sources)

    return {
        "status": "success",
        "message": "Source saved to IRM Core.",
        "source": new_entry
    }
