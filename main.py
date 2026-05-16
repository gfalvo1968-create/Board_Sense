from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import shutil
import uvicorn

from ecosystem import get_ecosystem
from signal_engine import evaluate_signals
from routes.grade import router as grade_router
from routes.irm_core import router as irm_router
from routes.reference_loader import load_reference_data

app = FastAPI(title="Board Sense")
app.on_event("startup")
def startup_event():
    load_reference_data()
BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "Static"
DATA_DIR = BASE_DIR / "data"
IMAGE_DIR = DATA_DIR / "Images"


# -----------------------------
# STATIC FILES
# -----------------------------
app.mount("/Static", StaticFiles(directory=STATIC_DIR), name="Static")
app.include_router(grade_router)
app.include_router(irm_router)

# -----------------------------
# FRONTEND
# -----------------------------
@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "index.html")


# -----------------------------
# ECOSYSTEM
# -----------------------------
@app.get("/ecosystem")
def ecosystem_data():
    return get_ecosystem()


# -----------------------------
# BOARD ANALYSIS
# -----------------------------
@app.post("/analyze")
async def analyze_board(file: UploadFile = File(...)):

    file_path = IMAGE_DIR / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # -----------------------------------
    # TEMP TEST DATA
    # Later AI will generate this
    # -----------------------------------

    board_data = {
        "gold_fingers": True,
        "large_ic_chips": True,
        "server_grade": False,
        "low_value_board": False
    }

    signal_results = evaluate_signals(board_data)

    # -----------------------------------
    # SIGNAL LIGHT LOGIC
    # -----------------------------------

    signal_lights = {
        "gold": "green" if board_data["gold_fingers"] else "red",
        "chips": "green" if board_data["large_ic_chips"] else "orange",
        "grade": "orange" if not board_data["server_grade"] else "green"
    }

    # -----------------------------------
    # JACKPOT LOGIC
    # -----------------------------------

    jackpot = signal_results["jackpot"]

    if jackpot:
        recovery_message = (
            "JACKPOT DETECTED — This board should be reviewed for recovery. "
            "Open Pay_Dirt for teardown and recovery guidance."
        )
    else:
        recovery_message = (
            "Board scanned successfully. Continue evaluation."
        )

    # -----------------------------------
    # RETURN DATA
    # -----------------------------------

    return {
        "status": "success",

        "board": file.filename,

        "signals": signal_lights,

        "jackpot": jackpot,

        "score": signal_results["score"],

        "recovery_message": recovery_message,

        "detected_materials": [
            "Gold Fingers",
            "Copper Traces",
            "IC Chips"
        ]
    }


# -----------------------------
# SERVER START
# -----------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
