"""Refinement guard for SPIKE hard-drive actuator targets.

The legacy target detector is still responsible for finding the general actuator
neighborhood. This module only re-checks a legacy component-level candidate so a
false platter/large-circle solution cannot promote itself to TARGET CANDIDATE.

For a hard-drive actuator magnet mission, component promotion requires a local
chain that is physically meaningful in an opened drive:

    copper/bronze voice-coil cue -> nearby pivot-scale bearing -> neutral metal
    on the backing-plate side of that pair.

This is geometry only. It never identifies magnet chemistry, neodymium content,
recoverable mass, or cash value.
"""
from __future__ import annotations

import cv2
import numpy as np

from routes.target_visual import inspect_target_visual as _legacy_inspect_target_visual
from routes.speaker_target_visual import inspect_speaker_target_visual


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


def _safe_circles(gray, min_r, max_r):
    try:
        blur = cv2.GaussianBlur(gray, (9, 9), 1.8)
        found = cv2.HoughCircles(
            blur,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(12, int(min(gray.shape[:2]) * 0.045)),
            param1=120,
            param2=27,
            minRadius=max(4, int(min_r)),
            maxRadius=max(6, int(max_r)),
        )
        if found is None:
            return []
        return [tuple(float(v) for v in c) for c in found[0]]
    except Exception:
        return []


def _component_refinement(image_path):
    out = {
        "confirmed": False,
        "score": 0,
        "geometry": {},
        "metrics": {},
        "evidence": [],
    }
    image = cv2.imread(str(image_path))
    if image is None:
        return out
    image = _resize(image)
    h, w = image.shape[:2]
    short = float(min(h, w))
    image_area = float(h * w)
    if short <= 0:
        return out

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    copper = cv2.inRange(hsv, np.array([3, 55, 45]), np.array([32, 255, 245]))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    copper = cv2.morphologyEx(copper, cv2.MORPH_OPEN, kernel, iterations=1)
    copper = cv2.morphologyEx(copper, cv2.MORPH_CLOSE, kernel, iterations=1)
    count, _, stats, centroids = cv2.connectedComponentsWithStats(copper)
    copper_components = []
    for i in range(1, count):
        x, y, cw, ch, area = stats[i]
        cx, cy = centroids[i]
        area_ratio = float(area) / max(image_area, 1.0)
        border = min(cx, cy, w - cx, h - cy)
        if area_ratio < 0.00035 or area_ratio > 0.035:
            continue
        if border < short * 0.045:
            continue
        copper_components.append(
            {
                "area": int(area),
                "area_ratio": area_ratio,
                "x": float(cx),
                "y": float(cy),
                "w": int(cw),
                "h": int(ch),
            }
        )

    circles = _safe_circles(gray, short * 0.022, short * 0.11)
    neutral = cv2.inRange(hsv, np.array([0, 0, 48]), np.array([179, 92, 250]))

    best = None
    for comp in copper_components:
        cx, cy = comp["x"], comp["y"]
        for pivot in circles:
            px, py, pr = pivot
            distance = float(np.hypot(px - cx, py - cy))
            if distance < short * 0.07 or distance > short * 0.24:
                continue
            radius_ratio = pr / short
            if radius_ratio < 0.025 or radius_ratio > 0.095:
                continue

            distance_per_radius = distance / max(pr, 1.0)
            vx, vy = cx - px, cy - py
            tx, ty = cx + 0.55 * vx, cy + 0.55 * vy
            if tx < 0 or ty < 0 or tx >= w or ty >= h:
                continue
            sample_radius = max(18, int(short * 0.055))
            sample = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(sample, (int(tx), int(ty)), sample_radius, 255, -1)
            sample_pixels = max(1, cv2.countNonZero(sample))
            neutral_ratio = float(cv2.countNonZero(cv2.bitwise_and(neutral, sample)) / sample_pixels)

            score = 0
            score += min(20, int(comp["area"] / max(image_area * 0.0005, 1.0) * 3))
            if 1.45 <= distance_per_radius <= 2.35:
                score += 18
            elif 1.15 <= distance_per_radius <= 2.80:
                score += 10
            elif distance_per_radius > 3.20:
                score -= 8
            if 0.035 <= radius_ratio <= 0.080:
                score += 16
            else:
                score += 8
            if neutral_ratio >= 0.65:
                score += 24
            elif neutral_ratio >= 0.45:
                score += 16
            elif neutral_ratio >= 0.30:
                score += 8
            score += min(10, int(radius_ratio / 0.01))

            candidate = {
                "score": int(score),
                "neutral_ratio": neutral_ratio,
                "copper": comp,
                "pivot": {"x": px, "y": py, "r": pr},
                "plate_point": {"x": tx, "y": ty},
                "distance": distance,
                "distance_per_radius": distance_per_radius,
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate

    out["metrics"] = {
        "image_width": int(w),
        "image_height": int(h),
        "copper_component_count": len(copper_components),
        "pivot_circle_count": len(circles),
    }
    if not best:
        return out

    out["score"] = best["score"]
    out["metrics"].update(
        {
            "refine_neutral_plate_ratio": round(best["neutral_ratio"], 3),
            "refine_voicecoil_pivot_distance": round(best["distance"], 1),
            "refine_distance_per_pivot_radius": round(best["distance_per_radius"], 2),
            "refine_copper_area_ratio": round(best["copper"]["area_ratio"], 5),
        }
    )

    if best["score"] < 78 or best["neutral_ratio"] < 0.45:
        return out

    out["confirmed"] = True
    out["geometry"] = {
        "pivot": {
            "x": round(best["pivot"]["x"], 1),
            "y": round(best["pivot"]["y"], 1),
            "r": round(best["pivot"]["r"], 1),
        },
        "voice_coil": {
            "x": round(best["copper"]["x"], 1),
            "y": round(best["copper"]["y"], 1),
            "area": best["copper"]["area"],
        },
        "plate": {
            "x": round(best["plate_point"]["x"], 1),
            "y": round(best["plate_point"]["y"], 1),
            "score": best["score"],
            "method": "voice_coil_pivot_projection",
        },
    }
    out["evidence"] = [
        "copper/bronze voice-coil region detected",
        "pivot-scale circular bearing detected beside the voice coil",
        "neutral metal verified on the backing-plate side of the voice-coil/pivot pair",
        "voice-coil-to-pivot geometry localizes the actuator magnet backing side",
    ]
    return out


def inspect_target_visual(image_path, source_id, target):
    source_id = str(source_id or "").strip().lower()
    target_text = str(target or "").strip().lower()

    if source_id == "speaker" and "magnet" in target_text:
        return inspect_speaker_target_visual(image_path, source_id, target)

    base = _legacy_inspect_target_visual(image_path, source_id, target)

    if source_id != "hard-drive" or "actuator" not in target_text or "magnet" not in target_text:
        return base

    if (base or {}).get("status") != "target_candidate":
        return base

    try:
        refined = _component_refinement(image_path)
    except Exception as exc:
        base["status"] = "target_area_candidate"
        base["confidence"] = min(int(base.get("confidence") or 0), 84)
        base["message"] = (
            "SPIKE found the actuator neighborhood, but component localization could not be re-checked safely. "
            "Keep this at target-area level until the voice-coil/pivot relationship is confirmed."
        )
        base.setdefault("diagnostics", []).append("component refinement recovered: " + type(exc).__name__)
        return base

    metrics = base.setdefault("metrics", {})
    metrics.update(refined.get("metrics") or {})
    metrics["component_refinement_score"] = int(refined.get("score") or 0)

    if not refined.get("confirmed"):
        base["status"] = "target_area_candidate"
        base["confidence"] = min(int(base.get("confidence") or 0), 84)
        base["message"] = (
            "SPIKE found the actuator neighborhood, but the proposed component point did not survive the "
            "voice-coil/pivot/backing-plate cross-check. Treat this as a target-area candidate and move closer."
        )
        base["evidence"] = [
            e for e in (base.get("evidence") or [])
            if "broad neutral-metal plate-like" not in str(e).lower()
        ]
        return base

    geometry = base.setdefault("geometry", {})
    geometry.update(refined.get("geometry") or {})
    base["status"] = "target_candidate"
    base["confidence"] = min(93, max(82, int(refined.get("score") or 0) + 6))

    retained = [
        e for e in (base.get("evidence") or [])
        if "broad neutral-metal plate-like" not in str(e).lower()
        and "copper/bronze voice-coil color cue" not in str(e).lower()
        and "pivot is large enough" not in str(e).lower()
    ]
    for item in refined.get("evidence") or []:
        if item not in retained:
            retained.append(item)
    base["evidence"] = retained
    base["message"] = (
        "SPIKE cross-checked the actuator candidate from the local voice-coil, pivot bearing, and neutral backing-plate side. "
        "This supports the actuator magnet assembly as a visual target candidate only; magnet chemistry, neodymium content, "
        "recoverable mass, and cash value remain unproven."
    )
    base["refinement_rule"] = (
        "Component promotion requires a local voice-coil/pivot/backing-side geometry chain. "
        "A platter-scale or generic metallic feature cannot promote itself to TARGET CANDIDATE."
    )
    return base
