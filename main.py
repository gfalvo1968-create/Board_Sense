from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import List, Optional
import uvicorn
from ecosystem import get_ecosystem
from routes.board_analyzer import analyze_board
from routes.pair_reasoner import reconcile_pair
from routes.pair_decision_guard import guard_pair
from routes.spike_evidence_packet import build_evidence_packet
from routes.case_reasoner import reconcile_case
from routes.inspection_target import parse_inspection_target, apply_inspection_target
from routes.free_usage_gate import check_free_board_allowance, record_free_board_use, free_gate_payload
from recovery_lab.core.time_value import compare_paths
from routes.grade import router as grade_router
from routes.irm_core import router as irm_router
from routes.market_bridge import router as market_router
from routes.reference_loader import load_reference_data
from routes.upload_security import UploadBodyLimitMiddleware, validated_board_images
from routes.origin_security import OriginProtectionMiddleware

app = FastAPI(title="Board Sense")
app.add_middleware(UploadBodyLimitMiddleware)
app.add_middleware(OriginProtectionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://gfalvo1968-create.github.io", "https://boardsense.scrapradarfamily.com"],
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
MULTI_BOARD_CROP_DIR = IMAGE_DIR / "multi_board_crops"
MULTI_BOARD_CROP_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/Static", StaticFiles(directory=STATIC_DIR), name="Static")
app.mount("/blueprints", StaticFiles(directory=BLUEPRINT_DIR), name="blueprints")
app.mount("/multi-board-crops", StaticFiles(directory=MULTI_BOARD_CROP_DIR), name="multi-board-crops")
app.include_router(grade_router)
app.include_router(irm_router)
app.include_router(market_router)


@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/ecosystem")
def ecosystem_data():
    return get_ecosystem()


@app.get("/health")
def health():
    """Deployment probe; no scan, visitor data or private contacts."""
    return {"status": "ok", "service": "Board Sense", "release": "launch-20261006-phone-routing"}


@app.get("/free-usage")
def free_usage(request: Request):
    """Return today's anonymous free-board allowance without consuming it."""
    decision = check_free_board_allowance(request)
    if decision.reason == "usage_backend_unavailable":
        return JSONResponse(status_code=503, content=free_gate_payload(decision))
    return {"status": "success", "free_usage": decision.as_dict()}


def _economics_payload(**values):
    return {k: v for k, v in values.items() if v is not None}


def _spike_target_rank(result):
    t = (result or {}).get("inspection_target") or {}
    status = t.get("status")
    rank = {"target_candidate": 3, "target_area_candidate": 2, "target_not_confirmed": 1}.get(status, 0)
    vt = t.get("visual_target") or {}
    visual = float(vt.get("confidence") or 0)
    role_bonus = 1 if (result or {}).get("spike_role") == "closeup" else 0
    spike = (result or {}).get("spike_glass") or {}
    generic = float(spike.get("confidence") or 0)
    return (rank, visual, role_bonus, generic)


def _gate_or_block(request: Request):
    decision = check_free_board_allowance(request)
    if decision.allowed:
        return None
    status_code = 503 if decision.reason == "usage_backend_unavailable" else 429
    return JSONResponse(status_code=status_code, content=free_gate_payload(decision))


def _claim_or_block(request: Request, mode: str):
    usage = record_free_board_use(request, mode)
    blocked = None
    if not usage.allowed:
        status_code = 503 if usage.reason == "usage_backend_unavailable" else 429
        blocked = JSONResponse(status_code=status_code, content=free_gate_payload(usage))
    return usage, blocked


def _attach_usage(result: dict, usage):
    result["free_usage"] = usage.as_dict()
    return result


@app.post("/analyze")
async def analyze_board_route(request: Request, file: UploadFile = File(...), inspection_target: Optional[str] = Form(None)):
    blocked = _gate_or_block(request)
    if blocked:
        return blocked
    with validated_board_images([file], IMAGE_DIR) as paths:
        usage, blocked = _claim_or_block(request, "single_board")
        if blocked is not None:
            return blocked
        file_path = paths[0]
        result = analyze_board(str(file_path))
        target_packet = parse_inspection_target(inspection_target)
        if target_packet:
            result = apply_inspection_target(result, target_packet, str(file_path))
        result["status"] = "success"
        result["board"] = file.filename
        result["spike_evidence"] = build_evidence_packet(result)
    return _attach_usage(result, usage)


@app.post("/analyze-spike-pair")
async def analyze_spike_pair_route(
    request: Request,
    context: UploadFile = File(...),
    closeup: Optional[UploadFile] = File(None),
    inspection_target: Optional[str] = Form(None),
):
    blocked = _gate_or_block(request)
    if blocked:
        return blocked
    target_packet = parse_inspection_target(inspection_target)
    uploads = [("context", context)]
    if closeup is not None:
        uploads.append(("closeup", closeup))
    views = []
    with validated_board_images([upload for _, upload in uploads], IMAGE_DIR) as paths:
        usage, blocked = _claim_or_block(request, "spike_two_photo_one_board")
        if blocked is not None:
            return blocked
        for (role, upload), path in zip(uploads, paths):
            result = analyze_board(str(path))
            if target_packet:
                result = apply_inspection_target(result, target_packet, str(path))
            result["status"] = "success"
            result["board"] = upload.filename
            result["spike_role"] = role
            result["spike_evidence"] = build_evidence_packet(result)
            views.append(result)
    selected = max(views, key=_spike_target_rank) if target_packet else max(
        views, key=lambda r: float(((r.get("spike_glass") or {}).get("confidence")) or 0)
    )
    summary = []
    for view in views:
        spike = view.get("spike_glass") or {}
        top = spike.get("top_match") or {}
        target = view.get("inspection_target") or {}
        summary.append(
            {
                "role": view.get("spike_role"),
                "board": view.get("board"),
                "generic_label": top.get("label"),
                "generic_confidence": spike.get("confidence"),
                "target_status": target.get("status"),
                "target_confidence": ((target.get("visual_target") or {}).get("confidence")),
            }
        )
    payload = {
        "status": "success",
        "mode": "spike_two_photo",
        "photo_count": len(views),
        "views": views,
        "combined": selected,
        "selected_role": selected.get("spike_role"),
        "pair_summary": summary,
        "integrity_rule": "Two-photo Spike Glass compares context and close-up evidence for one inspection target. It does not merge board economics or manufacture composition/value.",
    }
    return _attach_usage(payload, usage)


@app.post("/analyze-pair")
async def analyze_board_pair_route(request: Request, side_a: UploadFile = File(...), side_b: UploadFile = File(...)):
    blocked = _gate_or_block(request)
    if blocked:
        return blocked
    with validated_board_images([side_a, side_b], IMAGE_DIR) as paths:
        usage, blocked = _claim_or_block(request, "two_sided_one_board")
        if blocked is not None:
            return blocked
        result_a = analyze_board(str(paths[0]))
        result_b = analyze_board(str(paths[1]))
    result_a["spike_evidence"] = build_evidence_packet(result_a)
    result_b["spike_evidence"] = build_evidence_packet(result_b)
    paired = guard_pair(result_a, result_b, reconcile_pair(result_a, result_b))
    paired["spike_evidence"] = build_evidence_packet(paired)
    paired["model"] = "Board Sense v2.3 + SPIKE Verification v0.1 + Pair Reasoner v1.1"
    payload = {
        "status": "success",
        "mode": "two_sided_same_board",
        "side_a": result_a,
        "side_b": result_b,
        "paired": paired,
    }
    return _attach_usage(payload, usage)


@app.post("/analyze-case")
async def analyze_board_case_route(
    request: Request,
    files: List[UploadFile] = File(...),
    current_sell_whole_value: Optional[float] = Form(None, ge=0, allow_inf_nan=False),
    intact_sell_whole_value: Optional[float] = Form(None, ge=0, allow_inf_nan=False),
    partial_recovered_value: Optional[float] = Form(None, ge=0, allow_inf_nan=False),
    partial_residual_value: Optional[float] = Form(None, ge=0, allow_inf_nan=False),
    partial_minutes: Optional[float] = Form(None, ge=0, allow_inf_nan=False),
    partial_costs: Optional[float] = Form(None, ge=0, allow_inf_nan=False),
    full_recovery_value: Optional[float] = Form(None, ge=0, allow_inf_nan=False),
    full_minutes: Optional[float] = Form(None, ge=0, allow_inf_nan=False),
    full_costs: Optional[float] = Form(None, ge=0, allow_inf_nan=False),
    operator_same_board_confirmation: bool = Form(False),
):
    """Analyze 2-6 photos of one physical board and consume one daily free-board allowance."""
    blocked = _gate_or_block(request)
    if blocked:
        return blocked
    if len(files) < 2 or len(files) > 6:
        return {"status": "error", "message": "Choose between 2 and 6 photos of the same board."}
    results = []
    with validated_board_images(files, IMAGE_DIR) as paths:
        usage, blocked = _claim_or_block(request, "multi_photo_one_board")
        if blocked is not None:
            return blocked
        for i, (upload, path) in enumerate(zip(files, paths), 1):
            result = analyze_board(str(path))
            result["board"] = upload.filename
            result["view_number"] = i
            result["spike_evidence"] = build_evidence_packet(result)
            results.append(result)
    combined = reconcile_case(results, operator_same_board_confirmation=operator_same_board_confirmation)
    if combined.get("status") == "case_identity_failed" or (combined.get("same_board_verification") or {}).get("block_reconciliation"):
        identity = combined.get("same_board_verification") or {}
        multiple = str(identity.get("status", "")).startswith("MULTIPLE_BOARDS")
        return _attach_usage({
            "status": "success",
            "mode": "multi_photo_identity_blocked",
            "photo_count": len(results),
            "views": results,
            "combined": combined,
            "case_warning": ("Multiple boards detected. Start a separate case for each physical board."
                             if multiple else "Board identity needs clarification. Add clearer views of one board."),
        }, usage)
    econ = _economics_payload(
        sell_whole_value=intact_sell_whole_value,
        partial_recovered_value=partial_recovered_value,
        partial_residual_value=partial_residual_value,
        partial_minutes=partial_minutes,
        partial_costs=partial_costs,
        full_recovery_value=full_recovery_value,
        full_minutes=full_minutes,
        full_costs=full_costs,
    )
    condition = combined.get("condition_and_harvest") or {}
    factor = condition.get("remaining_value_factor", 1.0)
    if current_sell_whole_value is not None:
        econ["sell_whole_value"] = current_sell_whole_value
        factor = 1.0
        sell_basis = "CURRENT CONDITION OFFER"
    elif intact_sell_whole_value is not None:
        sell_basis = "INTACT BOARD BASELINE"
    else:
        sell_basis = "NOT PROVIDED"
    combined["recovery_economics"] = compare_paths(condition_factor=factor, **econ)
    combined["recovery_economics"]["sell_value_basis"] = sell_basis
    combined["recovery_economics"]["condition_link"] = {
        "condition": condition.get("condition"),
        "remaining_value_factor": condition.get("remaining_value_factor", 1.0),
        "rule": "Current-condition offers are never discounted twice. Intact-board baselines may be reduced only by confirmed harvesting. Uncertain absence creates no deduction.",
    }
    combined["spike_evidence"] = build_evidence_packet(combined, condition_observations=condition.get("observations"))
    payload = {
        "status": "success",
        "mode": "same_board_multi_photo",
        "photo_count": len(results),
        "views": results,
        "combined": combined,
    }
    return _attach_usage(payload, usage)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
