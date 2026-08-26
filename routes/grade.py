# routes/grade.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
from datetime import datetime
import shutil

from routes.board_analyzer import analyze_board

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMAGE_DIR = DATA_DIR / "Images"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_board(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()

    if suffix not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{Path(file.filename).name}"
    file_path = IMAGE_DIR / safe_name

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ai_result = analyze_board(str(file_path))

    return {
        "status": "success",
        "filename": safe_name,
        "image_url": f"/data/Images/{safe_name}",
        "ai_grade": ai_result.get("grade", "UNKNOWN"),
        "confidence": ai_result.get("confidence", 0),
        "board_type": ai_result.get("board_type", "General PCB"),
        "board_type_reason": ai_result.get("board_type_reason", ""),
        "signals": ai_result.get("signals", {}),
        "score": ai_result.get("score", 0),
        "recommendation": ai_result.get("recommendation", "Manual review required."),
        "recovery_signals": ai_result.get("recovery_signals", []),
        "grade_notes": ai_result.get("grade_notes", ""),
        "pay_dirt_ready": ai_result.get("pay_dirt_ready", False),
        "features": ai_result.get("features", {}),
        "power": ai_result.get("power", {}),
        "insight": ai_result.get("insight", {}),
        "model": ai_result.get("model", "Board Sense AI")
    }
