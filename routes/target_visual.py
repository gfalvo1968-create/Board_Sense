"""Target-specific visual geometry for SPIKE inspection missions.

This module is intentionally narrow. It does not identify chemistry or recoverable
mass. It only decides whether a photo visually contains the expected inspection
area strongly enough to guide the next close-up.
"""
from __future__ import annotations

import cv2
import numpy as np


def _resize(image, max_side=1100):
    h, w = image.shape[:2]
    if max(h, w) <= max_side:
        return image
    scale = float(max_side) / float(max(h, w))
    return cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)


def _circles(gray, min_r, max_r, param2, min_dist):
    if max_r <= min_r:
        return []
    blur = cv2.GaussianBlur(gray, (9, 9), 1.8)
    found = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(12, int(min_dist)),
        param1=120,
        param2=param2,
        minRadius=max(4, int(min_r)),
        maxRadius=max(6, int(max_r)),
    )
    if found is None:
        return []
    return [tuple(float(v) for v in c) for c in found[0]]


def _metallic_ratio(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Broad neutral/metallic support only. This is context, never proof of metal type.
    mask = cv2.inRange(hsv, np.array([0, 0, 45]), np.array([179, 85, 245]))
    return float(cv2.countNonZero(mask) / max(mask.size, 1))


def _line_support(gray, pivot, platter):
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 55, 145)
    short = min(gray.shape[:2])
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180.0,
        threshold=max(25, int(short * 0.04)),
        minLineLength=max(28, int(short * 0.12)),
        maxLineGap=max(8, int(short * 0.025)),
    )
    if lines is None:
        return 0, []
    px, py, pr = pivot
    cx, cy, cr = platter
    supported = []
    for line in lines[:, 0]:
        x1, y1, x2, y2 = [float(v) for v in line]
        length = float(np.hypot(x2 - x1, y2 - y1))
        d1 = float(np.hypot(x1 - px, y1 - py))
        d2 = float(np.hypot(x2 - px, y2 - py))
        near = min(d1, d2)
        if near > max(pr * 2.3, cr * 0.18):
            continue
        # The actuator arm should be a meaningful elongated structure near the pivot,
        # not a tiny screw edge or texture fragment.
        if length < cr * 0.22:
            continue
        farx, fary = (x2, y2) if d2 >= d1 else (x1, y1)
        far_to_platter = float(np.hypot(farx - cx, fary - cy))
        if far_to_platter <= cr * 1.20:
            supported.append((x1, y1, x2, y2, length))
    return len(supported), supported[:8]


def _hard_drive_actuator_geometry(image_path):
    result = {
        "applicable": True,
        "status": "target_not_confirmed",
        "confidence": 0,
        "evidence": [],
        "message": "Opened hard-drive actuator geometry was not strong enough to mark the target area yet.",
    }
    image = cv2.imread(str(image_path))
    if image is None:
        result["message"] = "SPIKE could not read the image for target-specific geometry."
        return result
    image = _resize(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    short = float(min(h, w))

    large = _circles(gray, short * 0.16, short * 0.56, 48, short * 0.22)
    if not large:
        large = _circles(gray, short * 0.16, short * 0.56, 39, short * 0.20)
    if not large:
        return result

    # Favor a large circular structure that is not merely a tiny border artifact.
    platter = max(large, key=lambda c: c[2])
    cx, cy, cr = platter
    if cr < short * 0.17:
        return result
    score = 42
    evidence = ["large circular platter/spindle-scale structure detected"]

    small = _circles(gray, short * 0.025, short * 0.14, 29, short * 0.055)
    pivot_candidates = []
    margin = short * 0.045
    for c in small:
        x, y, r = c
        if x < margin or y < margin or x > w - margin or y > h - margin:
            continue
        dist = float(np.hypot(x - cx, y - cy))
        if dist < cr * 0.30 or dist > cr * 1.30:
            continue
        # Prefer a substantial pivot-like circle rather than a tiny chassis screw.
        relative_r = r / max(cr, 1.0)
        local = 0.0
        if 0.055 <= relative_r <= 0.28:
            local += 12
        elif 0.035 <= relative_r <= 0.34:
            local += 6
        ratio = dist / max(cr, 1.0)
        if 0.45 <= ratio <= 1.05:
            local += 12
        elif 0.35 <= ratio <= 1.20:
            local += 6
        border = min(x, y, w - x, h - y)
        if border >= short * 0.09:
            local += 5
        pivot_candidates.append((local, c))

    pivot = None
    line_count = 0
    if pivot_candidates:
        # Let arm-line geometry break ties among plausible pivots.
        best = None
        for local, candidate in pivot_candidates[:18]:
            lc, _ = _line_support(gray, candidate, platter)
            combined = local + min(20, lc * 5)
            if best is None or combined > best[0]:
                best = (combined, local, lc, candidate)
        if best:
            _, local, line_count, pivot = best
            score += int(local)
            evidence.append("secondary pivot-scale circular structure detected near the platter")
            if line_count:
                score += min(22, line_count * 6)
                evidence.append("elongated arm-like geometry detected from the pivot toward the platter")

    metallic = _metallic_ratio(image)
    if metallic >= 0.34:
        score += 8
        evidence.append("open mechanical/metallic drive context is visually strong")
    elif metallic >= 0.22:
        score += 4

    score = max(0, min(92, int(score)))
    result["confidence"] = score
    result["evidence"] = evidence
    result["metrics"] = {
        "large_circle_count": len(large),
        "pivot_candidate_count": len(pivot_candidates),
        "arm_line_support": int(line_count),
        "neutral_metallic_ratio": round(metallic, 3),
    }
    if pivot is not None:
        result["geometry"] = {
            "platter": {"x": round(cx, 1), "y": round(cy, 1), "r": round(cr, 1)},
            "pivot": {"x": round(pivot[0], 1), "y": round(pivot[1], 1), "r": round(pivot[2], 1)},
        }

    if score >= 68 and pivot is not None and line_count >= 1:
        result["status"] = "target_area_candidate"
        result["message"] = (
            "Opened hard-drive geometry is consistent with the actuator pivot/voice-coil area. "
            "Treat this as the correct target area for a closer magnet-assembly inspection; the magnet material itself is not proven."
        )
    elif score >= 61 and pivot is not None:
        result["message"] = (
            "SPIKE sees opened hard-drive and pivot-scale geometry, but the actuator-arm relationship is still incomplete. "
            "Keep the pivot and nearby metal-backed plate in frame and move closer."
        )
    return result


def inspect_target_visual(image_path, source_id, target):
    source_id = str(source_id or "").strip().lower()
    target_text = str(target or "").strip().lower()
    if source_id == "hard-drive" and "actuator" in target_text and "magnet" in target_text:
        return _hard_drive_actuator_geometry(image_path)
    return {"applicable": False, "status": "not_applicable", "confidence": 0, "evidence": []}
