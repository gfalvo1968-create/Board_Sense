from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import uvicorn

from ecosystem import get_ecosystem
from routes.board_analyzer import analyze_board
from routes.pair_reasoner import reconcile_pair
from routes.pair_decision_guard import guard_pair
from routes.spike_evidence_packet import build_evidence_packet
from routes.grade import router as grade_router
from routes.irm_core import router as irm_router
from routes.market_bridge import router as market_router
from routes.reference_loader import load_reference_data

app = FastAPI(title="Board Sense")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://gfalvo1968-create.github.io",
        "https://boardsense.scrapradarfamily.com",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    load_reference_data()


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "Static"
DATA_DIR = BASE_DIR / "data"
IMAGE_DIR = DATA_DIR / "Images"
BLUEPRINT_DIR = DATA_DIR / "Blueprints"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
BLUEPRINT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/Static", StaticFiles(directory=STATIC_DIR), name="Static")
app.mount("/blueprints", StaticFiles(directory=BLUEPRINT_DIR), name="blueprints")

app.include_router(grade_router)
app.include_router(irm_router)
app.include_router(market_router)


@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/ecosystem")
def ecosystem_data():
    return get_ecosystem()


def _save_upload(upload: UploadFile, target: Path):
    with open(target, "wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)


@app.post("/analyze")
async def analyze_board_route(file: UploadFile = File(...)):
    file_path = IMAGE_DIR / file.filename
    _save_upload(file, file_path)

    result = analyze_board(str(file_path))
    result["status"] = "success"
    result["board"] = file.filename
    result["spike_evidence"] = build_evidence_packet(result)
    return result


@app.post("/analyze-pair")
async def analyze_board_pair_route(
    side_a: UploadFile = File(...),
    side_b: UploadFile = File(...),
):
    """Analyze two photos as the two faces of one physical circuit board."""
    side_a_name = f"side_a_{side_a.filename}"
    side_b_name = f"side_b_{side_b.filename}"
    side_a_path = IMAGE_DIR / side_a_name
    side_b_path = IMAGE_DIR / side_b_name
    _save_upload(side_a, side_a_path)
    _save_upload(side_b, side_b_path)

    result_a = analyze_board(str(side_a_path))
    result_b = analyze_board(str(side_b_path))
    result_a["spike_evidence"] = build_evidence_packet(result_a)
    result_b["spike_evidence"] = build_evidence_packet(result_b)

    paired = reconcile_pair(result_a, result_b)
    paired = guard_pair(result_a, result_b, paired)
    paired["spike_evidence"] = build_evidence_packet(paired)
    paired["model"] = "Board Sense v2.2 + SPIKE Decision Guard v1.0 + Pair Reasoner v1.1"

    return {
        "status": "success",
        "mode": "two_sided_same_board",
        "side_a": result_a,
        "side_b": result_b,
        "paired": paired,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
