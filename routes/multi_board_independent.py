"""Preview-only isolation of independent PCB results from a single photo.

No combined grade, metal mass, buyer price, or economic result is allowed.
Requires an independent multi-board frame gate and disjoint image crops.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from routes.analysis_image import board_analysis_image
from routes.board_analyzer import analyze_board
from routes.frame_identity_gate import inspect_frame

MAX_BOARDS = 4


def _blocked(message, gate=None):
    return {
        "status": "manual_review_required",
        "mode": "separate_board_preview",
        "board_count": 0,
        "reports": [],
        "message": message,
        "frame_gate_status": (gate or {}).get("status"),
        "combined_grade": None,
        "combined_recovery_economics": None,
    }


def inspect_independent_regions(image_path, max_boards=MAX_BOARDS):
    """Return candidate boxes only when independently separated regions pass guards."""
    image = cv2.imread(str(image_path))
    if image is None:
        return _blocked("Image could not be read.")
    gate = inspect_frame(str(image_path))
    if gate.get("status") != "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED" or not gate.get("block_analysis"):
        return _blocked("Separate boards are not proven. Photograph each board individually.", gate)

    h, w = image.shape[:2]
    area = float(max(1, h * w))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([28, 35, 22]), np.array([105, 255, 255]))
    k = max(3, (min(h, w) // 110) | 1)
    surface = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    contours, _ = cv2.findContours(surface, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        a = float(cv2.contourArea(contour))
        if a / area < .045:
            continue
        x, y, bw, bh = cv2.boundingRect(contour)
        _, (rw, rh), _ = cv2.minAreaRect(contour)
        if a / max(1.0, rw * rh) < .35:
            continue
        candidates.append({"x": x, "y": y, "w": bw, "h": bh,
                           "area_ratio": a / area, "_contour": contour})

    if not 2 <= len(candidates) <= min(int(max_boards), MAX_BOARDS):
        return _blocked("The number of separately visible boards cannot be proven.", gate)
    candidates.sort(key=lambda x: x["area_ratio"], reverse=True)
    if candidates[0]["area_ratio"] < .10 or sum(r["area_ratio"] for r in candidates) < .20:
        return _blocked("PCB regions are too small for independent grading.", gate)

    margin = max(4, int(min(w, h) * .01))
    pad = max(6, int(min(w, h) * .015))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 55, 150)
    boxes = []
    for r in candidates:
        x, y, bw, bh = (r[key] for key in ("x", "y", "w", "h"))
        if x <= margin or y <= margin or x+bw >= w-margin or y+bh >= h-margin:
            return _blocked("A candidate board extends to the edge of the photo.", gate)
        mask = np.zeros((h, w), np.uint8)
        cv2.drawContours(mask, [r["_contour"]], -1, 255, -1)
        inside = cv2.erode(mask, np.ones((7, 7), np.uint8))
        edge_density = cv2.countNonZero(cv2.bitwise_and(edges, inside)) / max(1, cv2.countNonZero(inside))
        if edge_density < .025:
            return _blocked("One region lacks populated PCB evidence; manual review required.", gate)
        boxes.append({"x": x-pad, "y": y-pad, "w": bw+2*pad, "h": bh+2*pad})

    # Even a single pixel of intersecting crop would contaminate identity.
    for i, a in enumerate(boxes):
        for b in boxes[i+1:]:
            iw = max(0, min(a["x"]+a["w"], b["x"]+b["w"]) - max(a["x"], b["x"]))
            ih = max(0, min(a["y"]+a["h"], b["y"]+b["h"]) - max(a["y"], b["y"]))
            if iw and ih:
                return _blocked("Candidate crops overlap. Use separate photos.", gate)
    boxes.sort(key=lambda r: (r["x"], r["y"]))
    return {"status": "separable_preview", "mode": "separate_board_preview",
            "board_count": len(boxes), "boxes": boxes,
            "frame_gate_status": gate["status"]}


def analyze_independent_boards(image_path, analyzer=analyze_board):
    """Return one provisional result per supported board; no combined analysis."""
    with board_analysis_image(image_path) as normalized:
        split = inspect_independent_regions(normalized)
        if split["status"] != "separable_preview":
            return split
        photo = cv2.imread(str(normalized))
        reports = []
        with TemporaryDirectory(prefix="board-sense-separated-") as directory:
            for n, box in enumerate(split["boxes"], 1):
                x, y, bw, bh = (box[k] for k in ("x", "y", "w", "h"))
                crop = photo[y:y+bh, x:x+bw]
                if not crop.size:
                    return _blocked("Empty crop; manual review required.")
                path = Path(directory) / f"board_{n}.png"
                if not cv2.imwrite(str(path), crop):
                    return _blocked("Could not prepare private board crop.")
                cropped_frame = inspect_frame(str(path))
                if cropped_frame.get("block_analysis") or cropped_frame.get("status") in ("FRAME_UNREADABLE", "FRAME_GATE_UNCERTAIN"):
                    return _blocked("A crop remains ambiguous; no automatic grades.", cropped_frame)
                result = analyzer(str(path))
                mode = (result.get("object_gate") or {}).get("mode", "unknown")
                confidence = int(result.get("confidence") or 0)
                grade = str(result.get("grade") or "")
                blueprint = result.get("board_blueprint") or {}
                verified_candidate = bool(
                    mode == "board" and confidence >= 60
                    and grade in ("LOW", "MEDIUM", "HIGH", "VERY HIGH")
                    and not (blueprint.get("frame_identity_gate") or {}).get("block_analysis")
                )
                reports.append({
                    "board_index": n,
                    "box": box,
                    "object_mode": mode,
                    "board_type": result.get("board_type") if mode == "board" else "UNVERIFIED",
                    "confidence": confidence,
                    "provisional_grade": grade if verified_candidate else "MANUAL REVIEW",
                    "status": "provisional_grade" if verified_candidate else "manual_review",
                    "recommendation": (result.get("recommendation") if verified_candidate
                                       else "Inspect this physical board separately before assigning a buyer grade."),
                    "board_blueprint": blueprint if mode == "board" else {"available": False},
                    "recovery_economics": {"status": "unpriced",
                                           "message": "No material mass, assay or payout inferred from the image."},
                })
    return {
        "status": "separate_reports",
        "mode": "separate_board_preview",
        "board_count": len(reports),
        "reports": reports,
        "combined_grade": None,
        "combined_recovery_economics": None,
        "rule": "One physical board per independent provisional grade or manual-review report. Never combine board grades or components.",
        "limitations": "Experimental inspection only; individual board completeness and buyer grade require human verification.",
    }
