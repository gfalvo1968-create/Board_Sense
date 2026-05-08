# routes/grade.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import shutil
from datetime import datetime

from ai_engine import board_ai

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMAGE_DIR = DATA_DIR / "Images"


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

    ai_result = board_ai.predict_board(safe_name)

    return {
        "status": "success",
        "filename": safe_name,
        "image_url": f"/data/Images/{safe_name}",
        "ai_grade": ai_result["grade"],
        "confidence": ai_result["confidence"],
        "signals": ai_result["signals"],
        "score": ai_result["score"],
        "jackpot": ai_result["jackpot"],
        "recommendation": ai_result["recommendation"],
        "pay_dirt_ready": ai_result["pay_dirt_ready"],
        "features": ai_result["features"],
        "model": ai_result["model"],
    }


@router.get("/ai-status")
def ai_status():
    return board_ai.load_model()
