"""Target-specific visual geometry for SPIKE inspection missions.

This module is intentionally narrow. It does not identify chemistry or recoverable
mass. It only decides whether a photo visually contains the expected inspection
area strongly enough to guide the next close-up, or whether component-level
geometry is strong enough to mark the saved target as a candidate.
"""
from __future__ import annotations

import cv2
import numpy as np


def _resize(image, max_side=1100):
    h, w = image.shape[:2]
    if max(h, w) <= max_side:
        return image
    scale = float(max_side) / float(max(h, w))
    return cv2.resize(
        image,
        (max(1, int(w * scale)), max(1, int(h * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _safe_circles(gray, min_r, max_r, param2, min_dist, diagnostics):
    if max_r <= min_r:
        return []
    try:
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
    except Exception as exc:
        diagnostics.append("circle detector recovered: " + type(exc).__name__)
        return []


def _metallic_ratio(image, diagnostics):
    try:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([0, 0, 45]), np.array([179, 85, 245]))
        return float(cv2.countNonZero(mask) / max(mask.size, 1))
    except Exception as exc:
        diagnostics.append("metallic-context detector recovered: " + type(exc).__name__)
        return 0.0


def _detect_lines(gray, diagnostics):
    try:
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
            return []
        return [tuple(float(v) for v in line) for line in lines[:, 0]]
    except Exception as exc:
        diagnostics.append("arm-line detector recovered: " + type(exc).__name__)
        return []


def _line_support(lines, pivot, platter):
    px, py, pr = pivot
    cx, cy, cr = platter
    supported = []
    for line in lines:
        x1, y1, x2, y2 = line
        length = float(np.hypot(x2 - x1, y2 - y1))
        d1 = float(np.hypot(x1 - px, y1 - py))
        d2 = float(np.hypot(x2 - px, y2 - py))
        near = min(d1, d2)
        if near > max(pr * 2.3, cr * 0.18):
            continue
        if length < cr * 0.22:
            continue
        farx, fary = (x2, y2) if d2 >= d1 else (x1, y1)
        far_to_platter = float(np.hypot(farx - cx, fary - cy))
        if far_to_platter <= cr * 1.20:
            supported.append((x1, y1, x2, y2, length))
    return len(supported), supported[:8]


def _plate_and_voice_coil_cues(image, platter, pivot, diagnostics):
    """Look for component-level actuator cues around a proven pivot neighborhood.

    The detector looks for a broad neutral-metal plate near the pivot plus a small
    copper-colored voice-coil cue. Those cues can support an actuator-magnet
    *candidate*. They never prove magnet chemistry.
    """
    out = {
        "plate_score": 0,
        "plate": None,
        "voice_coil_ratio": 0.0,
        "component_scale": 0.0,
        "evidence": [],
    }
    try:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, w = image.shape[:2]
        short = float(min(h, w))
        cx, cy, cr = platter
        px, py, pr = pivot

        roi = np.zeros((h, w), dtype=np.uint8)
        roi_radius = max(int(cr * 0.68), int(pr * 5.5), 45)
        cv2.circle(roi, (int(px), int(py)), roi_radius, 255, -1)

        # Remove the deep platter interior and the pivot hub itself. The platter
        # edge may remain because real actuator plates can sit close to it.
        platter_core = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(platter_core, (int(cx), int(cy)), max(1, int(cr * 0.78)), 255, -1)
        pivot_core = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(pivot_core, (int(px), int(py)), max(3, int(max(pr * 1.15, cr * 0.045))), 255, -1)
        usable = cv2.bitwise_and(roi, cv2.bitwise_not(platter_core))
        usable = cv2.bitwise_and(usable, cv2.bitwise_not(pivot_core))

        neutral = cv2.inRange(hsv, np.array([0, 0, 58]), np.array([179, 82, 248]))
        neutral = cv2.bitwise_and(neutral, usable)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        neutral = cv2.morphologyEx(neutral, cv2.MORPH_CLOSE, kernel, iterations=2)
        neutral = cv2.morphologyEx(neutral, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(neutral, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        platter_vec = np.array([px - cx, py - cy], dtype=np.float32)
        platter_norm = float(np.linalg.norm(platter_vec)) or 1.0
        platter_unit = platter_vec / platter_norm
        image_area = float(w * h)

        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if area < max(120.0, cr * cr * 0.010) or area > min(image_area * 0.16, cr * cr * 0.95):
                continue
            moments = cv2.moments(cnt)
            if not moments.get("m00"):
                continue
            mx = float(moments["m10"] / moments["m00"])
            my = float(moments["m01"] / moments["m00"])
            dp = float(np.hypot(mx - px, my - py))
            if dp < max(pr * 0.75, cr * 0.045) or dp > cr * 0.72:
                continue

            rect = cv2.minAreaRect(cnt)
            rw, rh = rect[1]
            if rw <= 1 or rh <= 1:
                continue
            ratio = max(rw, rh) / max(1.0, min(rw, rh))
            hull = cv2.convexHull(cnt)
            hull_area = float(cv2.contourArea(hull)) or 1.0
            solidity = area / hull_area
            box_area = float(rw * rh) or 1.0
            extent = area / box_area
            dc = float(np.hypot(mx - cx, my - cy))
            rel_area = area / max(cr * cr, 1.0)
            offset = np.array([mx - px, my - py], dtype=np.float32)
            away = float(np.dot(offset, platter_unit)) / max(cr, 1.0)

            score = 0
            if 0.025 <= rel_area <= 0.60:
                score += 8
            elif 0.012 <= rel_area <= 0.80:
                score += 4
            if 1.15 <= ratio <= 5.8:
                score += 6
            elif ratio <= 7.5:
                score += 3
            if solidity >= 0.70:
                score += 6
            elif solidity >= 0.55:
                score += 3
            if extent >= 0.34:
                score += 4
            if dp <= cr * 0.52:
                score += 6
            elif dp <= cr * 0.66:
                score += 3
            if dc >= cr * 0.72:
                score += 5
            elif dc >= cr * 0.62:
                score += 2
            if away >= -0.08:
                score += 4

            candidate = (score, area, mx, my, rw, rh, ratio, solidity)
            if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and area > best[1]):
                best = candidate

        if best:
            score, area, mx, my, rw, rh, ratio, solidity = best
            out["plate_score"] = int(score)
            out["plate"] = {
                "x": round(mx, 1),
                "y": round(my, 1),
                "w": round(rw, 1),
                "h": round(rh, 1),
                "score": int(score),
            }
            if score >= 19:
                out["evidence"].append("broad neutral-metal plate-like structure detected beside the actuator pivot")

        # Copper/bronze cue near the pivot can support the visible voice-coil area.
        copper = cv2.inRange(hsv, np.array([3, 55, 45]), np.array([32, 255, 245]))
        copper = cv2.bitwise_and(copper, usable)
        roi_pixels = max(1, cv2.countNonZero(usable))
        copper_ratio = float(cv2.countNonZero(copper) / roi_pixels)
        out["voice_coil_ratio"] = round(copper_ratio, 4)
        if copper_ratio >= 0.004:
            out["evidence"].append("copper/bronze voice-coil color cue detected beside the pivot")

        component_scale = float(pr / max(short, 1.0))
        out["component_scale"] = round(component_scale, 4)
        if component_scale >= 0.035:
            out["evidence"].append("pivot is large enough in frame for component-level inspection")
        return out
    except Exception as exc:
        diagnostics.append("plate/voice-coil detector recovered: " + type(exc).__name__)
        return out


def _hard_drive_actuator_geometry(image_path):
    result = {
        "applicable": True,
        "status": "target_not_confirmed",
        "confidence": 0,
        "evidence": [],
        "message": "Opened hard-drive actuator geometry was not strong enough to mark the target area yet.",
    }
    diagnostics = []
    try:
        image = cv2.imread(str(image_path))
        if image is None:
            result["message"] = "SPIKE could not read the image for target-specific geometry."
            return result
        image = _resize(image)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        short = float(min(h, w))

        large = _safe_circles(gray, short * 0.16, short * 0.56, 48, short * 0.22, diagnostics)
        if not large:
            large = _safe_circles(gray, short * 0.16, short * 0.56, 39, short * 0.20, diagnostics)
        if not large:
            result["diagnostics"] = diagnostics
            return result

        platter = max(large, key=lambda c: c[2])
        cx, cy, cr = platter
        if cr < short * 0.17:
            result["diagnostics"] = diagnostics
            return result

        score = 42
        evidence = ["large circular platter/spindle-scale structure detected"]

        small = _safe_circles(gray, short * 0.025, short * 0.14, 29, short * 0.055, diagnostics)
        pivot_candidates = []
        margin = short * 0.045
        for c in small:
            x, y, r = c
            if x < margin or y < margin or x > w - margin or y > h - margin:
                continue
            dist = float(np.hypot(x - cx, y - cy))
            if dist < cr * 0.30 or dist > cr * 1.30:
                continue
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

        lines = _detect_lines(gray, diagnostics)
        pivot = None
        pivot_geometry_score = 0
        line_count = 0
        if pivot_candidates:
            best = None
            for local, candidate in pivot_candidates[:18]:
                lc, _ = _line_support(lines, candidate, platter)
                combined = local + min(20, lc * 5)
                if best is None or combined > best[0]:
                    best = (combined, local, lc, candidate)
            if best:
                _, pivot_geometry_score, line_count, pivot = best
                score += int(pivot_geometry_score)
                evidence.append("secondary pivot-scale circular structure detected near the platter")
                if line_count:
                    score += min(22, line_count * 6)
                    evidence.append("elongated arm-like geometry detected from the pivot toward the platter")

        metallic = _metallic_ratio(image, diagnostics)
        if metallic >= 0.34:
            score += 8
            evidence.append("open mechanical/metallic drive context is visually strong")
        elif metallic >= 0.22:
            score += 4

        score = max(0, min(92, int(score)))
        result["confidence"] = score
        result["evidence"] = evidence
        result["metrics"] = {
            "image_width": int(w),
            "image_height": int(h),
            "large_circle_count": len(large),
            "pivot_candidate_count": len(pivot_candidates),
            "pivot_geometry_score": int(pivot_geometry_score),
            "line_candidate_count": len(lines),
            "arm_line_support": int(line_count),
            "neutral_metallic_ratio": round(metallic, 3),
        }
        if diagnostics:
            result["diagnostics"] = diagnostics
        if pivot is not None:
            result["geometry"] = {
                "platter": {"x": round(cx, 1), "y": round(cy, 1), "r": round(cr, 1)},
                "pivot": {"x": round(pivot[0], 1), "y": round(pivot[1], 1), "r": round(pivot[2], 1)},
            }

        high_geometry = score >= 68 and pivot is not None and line_count >= 1
        strong_pivot_context = score >= 66 and pivot is not None and pivot_geometry_score >= 24 and metallic >= 0.22
        strong_open_drive_context = score >= 61 and pivot is not None and pivot_geometry_score >= 17 and metallic >= 0.34
        area_candidate = high_geometry or strong_pivot_context or strong_open_drive_context

        component = None
        if pivot is not None and area_candidate:
            component = _plate_and_voice_coil_cues(image, platter, pivot, diagnostics)
            result["metrics"].update({
                "plate_candidate_score": int(component.get("plate_score") or 0),
                "voice_coil_ratio": component.get("voice_coil_ratio", 0.0),
                "component_scale": component.get("component_scale", 0.0),
            })
            if component.get("plate"):
                result["geometry"]["plate"] = component["plate"]
            if component.get("evidence"):
                evidence.extend(component["evidence"])
                result["evidence"] = evidence

        plate_score = int((component or {}).get("plate_score") or 0)
        coil_ratio = float((component or {}).get("voice_coil_ratio") or 0.0)
        component_scale = float((component or {}).get("component_scale") or 0.0)
        strong_plate = plate_score >= 23
        plate_plus_coil = plate_score >= 18 and coil_ratio >= 0.004
        close_plate = plate_score >= 20 and component_scale >= 0.035

        if area_candidate and pivot is not None and (strong_plate or plate_plus_coil or close_plate):
            component_conf = min(95, max(score, 72) + min(12, max(0, plate_score - 17)) + (4 if coil_ratio >= 0.004 else 0))
            result["status"] = "target_candidate"
            result["confidence"] = int(component_conf)
            result["message"] = (
                "SPIKE sees a plate-like metal backing in the actuator pivot/voice-coil neighborhood with enough local component evidence "
                "to treat the actuator magnet assembly as a target candidate. This does not identify magnet chemistry, neodymium content, "
                "recoverable mass, or cash value."
            )
        elif high_geometry:
            result["status"] = "target_area_candidate"
            result["message"] = (
                "Opened hard-drive geometry is consistent with the actuator pivot/voice-coil area. "
                "Treat this as the correct target area for a closer magnet-assembly inspection; the magnet material itself is not proven."
            )
        elif strong_pivot_context or strong_open_drive_context:
            result["status"] = "target_area_candidate"
            evidence.append("platter-to-pivot geometry is strong enough to locate the actuator neighborhood")
            result["evidence"] = evidence
            result["message"] = (
                "SPIKE located the opened-drive actuator neighborhood from the platter, pivot-scale structure, "
                "and mechanical context. Move closer to the pivot and nearby metal-backed plate for component-level confirmation. "
                "This does not prove neodymium or recoverable mass."
            )
        elif score >= 61 and pivot is not None:
            result["message"] = (
                "SPIKE sees opened hard-drive and pivot-scale geometry, but the actuator neighborhood is still incomplete. "
                "Keep the pivot and nearby metal-backed plate in frame and move closer."
            )
        if diagnostics:
            result["diagnostics"] = diagnostics
        return result
    except Exception as exc:
        result["message"] = "Target geometry detector recovered safely from an internal vision error."
        result["diagnostics"] = diagnostics + ["target detector recovered: " + type(exc).__name__]
        return result


def inspect_target_visual(image_path, source_id, target):
    source_id = str(source_id or "").strip().lower()
    target_text = str(target or "").strip().lower()
    if source_id == "hard-drive" and "actuator" in target_text and "magnet" in target_text:
        return _hard_drive_actuator_geometry(image_path)
    return {"applicable": False, "status": "not_applicable", "confidence": 0, "evidence": []}
