"""SPIKE target-specific visual detector for speaker magnet assemblies.

This module locates the rear motor/magnet stack of a loudspeaker. It uses only
visible geometry and tonal structure. It never identifies magnet chemistry
(ferrite, neodymium, etc.), recoverable mass, or cash value.

Evidence ladder:
    TARGET NOT CONFIRMED
    TARGET AREA CANDIDATE
    TARGET CANDIDATE

A component-level candidate requires a compact rear circular stack with
concentric support plus local basket/frame evidence. A front cone or generic
round object should not be promoted simply because it is circular.
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


def _safe_circles(gray, min_r, max_r, param2=33):
    if max_r <= min_r:
        return []
    try:
        blur = cv2.GaussianBlur(gray, (9, 9), 1.8)
        found = cv2.HoughCircles(
            blur,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(14, int(min(gray.shape[:2]) * 0.05)),
            param1=120,
            param2=param2,
            minRadius=max(5, int(min_r)),
            maxRadius=max(7, int(max_r)),
        )
        if found is None:
            return []
        return [tuple(float(v) for v in c) for c in found[0]]
    except Exception:
        return []


def _safe_lines(gray):
    try:
        short = min(gray.shape[:2])
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 55, 145)
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180.0,
            threshold=max(24, int(short * 0.04)),
            minLineLength=max(26, int(short * 0.08)),
            maxLineGap=max(8, int(short * 0.025)),
        )
        if lines is None:
            return []
        return [tuple(float(v) for v in line) for line in lines[:, 0]]
    except Exception:
        return []


def _line_distance_to_point(line, px, py):
    x1, y1, x2, y2 = line
    vx, vy = x2 - x1, y2 - y1
    denom = vx * vx + vy * vy
    if denom <= 1e-6:
        return float(np.hypot(px - x1, py - y1))
    t = ((px - x1) * vx + (py - y1) * vy) / denom
    t = max(0.0, min(1.0, t))
    qx, qy = x1 + t * vx, y1 + t * vy
    return float(np.hypot(px - qx, py - qy))


def _annulus_stats(hsv, cx, cy, r):
    h, w = hsv.shape[:2]
    outer = np.zeros((h, w), dtype=np.uint8)
    inner = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(outer, (int(cx), int(cy)), max(2, int(r * 1.02)), 255, -1)
    cv2.circle(inner, (int(cx), int(cy)), max(1, int(r * 0.50)), 255, -1)
    ring = cv2.bitwise_and(outer, cv2.bitwise_not(inner))
    pixels = max(1, cv2.countNonZero(ring))

    neutral = cv2.inRange(hsv, np.array([0, 0, 30]), np.array([179, 95, 250]))
    dark = cv2.inRange(hsv, np.array([0, 0, 18]), np.array([179, 255, 115]))
    neutral_ratio = float(cv2.countNonZero(cv2.bitwise_and(neutral, ring)) / pixels)
    dark_ratio = float(cv2.countNonZero(cv2.bitwise_and(dark, ring)) / pixels)

    center = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(center, (int(cx), int(cy)), max(2, int(r * 0.32)), 255, -1)
    cpix = max(1, cv2.countNonZero(center))
    center_neutral = float(cv2.countNonZero(cv2.bitwise_and(neutral, center)) / cpix)
    center_dark = float(cv2.countNonZero(cv2.bitwise_and(dark, center)) / cpix)
    return neutral_ratio, dark_ratio, center_neutral, center_dark


def _speaker_magnet_geometry(image_path):
    result = {
        "applicable": True,
        "status": "target_not_confirmed",
        "confidence": 0,
        "evidence": [],
        "message": (
            "SPIKE did not yet see enough rear speaker motor/magnet geometry. "
            "Show the back of the speaker with the basket/frame and rear magnet stack in view."
        ),
    }

    image = cv2.imread(str(image_path))
    if image is None:
        result["message"] = "SPIKE could not read the image for speaker-target geometry."
        return result

    image = _resize(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, w = gray.shape[:2]
    short = float(min(h, w))
    if short <= 0:
        return result

    circles = _safe_circles(gray, short * 0.07, short * 0.38, 34)
    if not circles:
        circles = _safe_circles(gray, short * 0.06, short * 0.40, 29)
    lines = _safe_lines(gray)

    best = None
    for cx, cy, r in circles:
        rr = r / short
        if rr < 0.075 or rr > 0.38:
            continue

        concentric = []
        for ox, oy, orad in circles:
            if abs(orad - r) < 2:
                continue
            center_delta = float(np.hypot(ox - cx, oy - cy))
            if center_delta <= max(10.0, r * 0.16):
                ratio = orad / max(r, 1.0)
                if 0.22 <= ratio <= 1.35:
                    concentric.append((ox, oy, orad))

        neutral_ratio, dark_ratio, center_neutral, center_dark = _annulus_stats(hsv, cx, cy, r)

        spoke_count = 0
        for line in lines:
            x1, y1, x2, y2 = line
            length = float(np.hypot(x2 - x1, y2 - y1))
            if length < r * 0.55:
                continue
            near = _line_distance_to_point(line, cx, cy)
            if near > r * 1.12:
                continue
            far = max(float(np.hypot(x1 - cx, y1 - cy)), float(np.hypot(x2 - cx, y2 - cy)))
            if far >= r * 1.35:
                spoke_count += 1

        margin = min(cx, cy, w - cx, h - cy)
        frame_room = margin / max(r, 1.0)

        score = 0
        if 0.11 <= rr <= 0.30:
            score += 20
        elif 0.08 <= rr <= 0.34:
            score += 12

        score += min(24, len(concentric) * 8)

        mechanical_ratio = max(neutral_ratio, dark_ratio)
        center_mechanical = max(center_neutral, center_dark)
        if mechanical_ratio >= 0.62:
            score += 18
        elif mechanical_ratio >= 0.45:
            score += 12
        elif mechanical_ratio >= 0.30:
            score += 6

        if center_mechanical >= 0.58:
            score += 14
        elif center_mechanical >= 0.38:
            score += 8

        if spoke_count >= 3:
            score += 18
        elif spoke_count >= 2:
            score += 12
        elif spoke_count >= 1:
            score += 6

        if frame_room >= 1.30:
            score += 8
        elif frame_room >= 1.10:
            score += 4
        elif frame_room < 0.82:
            score -= 12

        candidate = {
            "score": int(score),
            "circle": (cx, cy, r),
            "concentric_count": len(concentric),
            "neutral_ratio": neutral_ratio,
            "dark_ratio": dark_ratio,
            "center_mechanical": center_mechanical,
            "spoke_count": spoke_count,
            "frame_room": frame_room,
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate

    result["metrics"] = {
        "image_width": int(w),
        "image_height": int(h),
        "speaker_circle_count": len(circles),
        "line_candidate_count": len(lines),
    }
    if not best:
        return result

    cx, cy, r = best["circle"]
    score = max(0, min(93, int(best["score"])))
    result["confidence"] = score
    result["metrics"].update({
        "rear_stack_radius_ratio": round(r / short, 4),
        "concentric_support": int(best["concentric_count"]),
        "basket_spoke_support": int(best["spoke_count"]),
        "rear_stack_neutral_ratio": round(best["neutral_ratio"], 3),
        "rear_stack_dark_ratio": round(best["dark_ratio"], 3),
        "rear_center_mechanical_ratio": round(best["center_mechanical"], 3),
        "frame_room_ratio": round(best["frame_room"], 2),
    })
    result["geometry"] = {
        "speaker_motor": {"x": round(cx, 1), "y": round(cy, 1), "r": round(r, 1)},
    }

    evidence = []
    if best["concentric_count"] >= 1:
        evidence.append("concentric rear motor/magnet-stack geometry detected")
    if max(best["neutral_ratio"], best["dark_ratio"]) >= 0.45:
        evidence.append("rear circular stack has strong mechanical neutral/dark material cues")
    if best["center_mechanical"] >= 0.38:
        evidence.append("central pole/plate-scale mechanical structure detected")
    if best["spoke_count"] >= 1:
        evidence.append("basket/frame members extend away from the rear circular stack")
    if best["frame_room"] >= 1.10:
        evidence.append("rear stack is compact enough in frame to preserve surrounding speaker context")
    result["evidence"] = evidence

    area_ok = (
        score >= 55
        and best["concentric_count"] >= 1
        and (best["spoke_count"] >= 1 or best["frame_room"] >= 1.20)
    )
    component_ok = (
        score >= 76
        and best["concentric_count"] >= 2
        and max(best["neutral_ratio"], best["dark_ratio"]) >= 0.45
        and best["center_mechanical"] >= 0.38
        and best["frame_room"] >= 1.05
    )

    if component_ok:
        result["status"] = "target_candidate"
        result["confidence"] = min(93, max(82, score))
        result["geometry"]["plate"] = {
            "x": round(cx, 1),
            "y": round(cy, 1),
            "r": round(r, 1),
            "method": "rear_speaker_magnet_stack_center",
        }
        result["message"] = (
            "SPIKE sees a compact concentric rear speaker motor/magnet stack with enough basket/frame "
            "and mechanical structure to treat the speaker magnet assembly as a visual target candidate. "
            "This does not identify magnet chemistry, neodymium content, recoverable mass, or cash value."
        )
    elif area_ok:
        result["status"] = "target_area_candidate"
        result["message"] = (
            "SPIKE found the rear speaker motor/magnet neighborhood from concentric circular geometry "
            "and surrounding basket/frame context. Move closer to the rear magnet stack for component-level "
            "confirmation. Magnet chemistry remains unproven."
        )
    else:
        result["message"] = (
            "SPIKE sees some speaker-like rear circular geometry, but the rear motor/magnet relationship "
            "is not strong enough yet. Keep the basket/frame and rear circular magnet stack in the same view."
        )

    return result


def inspect_speaker_target_visual(image_path, source_id, target):
    source_id = str(source_id or "").strip().lower()
    target_text = str(target or "").strip().lower()
    if source_id != "speaker" or "magnet" not in target_text:
        return {"applicable": False, "status": "not_applicable", "confidence": 0, "evidence": []}
    try:
        return _speaker_magnet_geometry(image_path)
    except Exception as exc:
        return {
            "applicable": True,
            "status": "target_not_confirmed",
            "confidence": 0,
            "evidence": [],
            "message": "Speaker target geometry recovered safely from an internal vision error.",
            "diagnostics": ["speaker target detector recovered: " + type(exc).__name__],
        }
