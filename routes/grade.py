# routes/grade.py

from fastapi import APIRouter, UploadFile, File, Request
from fastapi.responses import JSONResponse
from pathlib import Path

from routes.board_analyzer import analyze_board
from routes.free_usage_gate import check_free_board_allowance, free_gate_payload, record_free_board_use
from routes.upload_security import validated_board_images

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMAGE_DIR = DATA_DIR / "Images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_board(request: Request, file: UploadFile = File(...)):
    decision = check_free_board_allowance(request)
    if not decision.allowed:
        status = 503 if decision.reason == "usage_backend_unavailable" else 429
        return JSONResponse(status_code=status, content=free_gate_payload(decision))

    with validated_board_images([file], IMAGE_DIR) as paths:
        decision = record_free_board_use(request, "single_board")
        if not decision.allowed:
            status = 503 if decision.reason == "usage_backend_unavailable" else 429
            return JSONResponse(status_code=status, content=free_gate_payload(decision))
        safe_name = paths[0].name
        ai_result = analyze_board(str(paths[0]))

    return {
        "status": "success",
        "free_usage": decision.as_dict(),
        "filename": safe_name,
        "image_url": None,  # Private original is deleted after analysis.
        "ai_grade": ai_result.get("grade", "UNKNOWN"),
        "confidence": ai_result.get("confidence", 0),
        "board_type": ai_result.get("board_type", "General PCB"),
        "board_type_reason": ai_result.get("board_type_reason", ""),
        "signals": ai_result.get("signals", {}),
        "score": ai_result.get("score", 0),
        "recommendation": ai_result.get("recommendation", "Manual review required."),
        "recovery_signals": ai_result.get("recovery_signals", []),
        "grade_notes": ai_result.get("grade_notes", ""),
        "reference_intelligence": ai_result.get("reference_intelligence", {}),
        "pay_dirt_ready": ai_result.get("pay_dirt_ready", False),
        "features": ai_result.get("features", {}),
        "power": ai_result.get("power", {}),
        "insight": ai_result.get("insight", {}),
        "model": ai_result.get("model", "Board Sense AI")
    }
