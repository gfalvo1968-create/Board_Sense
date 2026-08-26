from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import uvicorn

from ecosystem import get_ecosystem
from routes.board_analyzer import analyze_board
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


@app.post("/analyze")
async def analyze_board_route(file: UploadFile = File(...)):
    file_path = IMAGE_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = analyze_board(str(file_path))
    result["status"] = "success"
    result["board"] = file.filename
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
