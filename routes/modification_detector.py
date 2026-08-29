"""SPIKE Modification Detector v0.1.

Conservative computer-vision screening for possible harvested/modified PCB
features. It never treats a crop boundary or a naturally straight PCB edge as
proof of harvesting. Findings are inspection prompts unless evidence is strong.
"""

import cv2
import numpy as np


def detect_modifications(image_path, result=None):
    image = cv2.imread(str(image_path))
    if image is None:
        return {"mode": "SPIKE Modification Detector v0.1", "status": "not_evaluated", "observations": {}, "signals": []}

    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    observations = {}
    signals = []

    # Search inside the board image, not directly on the photograph boundary.
    # Bright, low-saturation elongated regions can be exposed fiberglass/copper
    # or scraped/cut areas, but remain advisory because silkscreen/connectors can
    # look similar.
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    exposed = cv2.inRange(hsv, np.array([0, 0, 105]), np.array([179, 85, 245]))
    edges = cv2.Canny(gray, 70, 170)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
    candidate = cv2.morphologyEx(cv2.bitwise_and(exposed, edges), cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    suspicious_regions = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        if area < max(35, h * w * 0.00008):
            continue
        # Ignore anything touching the photo boundary. Camera cropping is not
        # physical evidence of a cut board.
        margin = max(4, int(min(h, w) * 0.012))
        if x <= margin or y <= margin or x + cw >= w - margin or y + ch >= h - margin:
            continue
        elongation = max(cw, ch) / max(1, min(cw, ch))
        if elongation >= 3.0:
            suspicious_regions.append({"x": x, "y": y, "w": cw, "h": ch, "elongation": round(elongation, 1)})

    if suspicious_regions:
        signals.append({
            "signal": "possible_cut_or_scraped_region",
            "confidence": "low",
            "count": len(suspicious_regions[:8]),
            "regions": suspicious_regions[:8],
            "meaning": "Possible exposed/cut PCB region. Requires visual confirmation before value deduction.",
        })
        observations["board_modification"] = {
            "status": "uncertain",
            "value_impact": "unknown",
            "note": "Vision found a possible cut/scraped region, but it is not confirmed harvesting.",
        }

    # If identity evidence says an edge-connector family but current vision does
    # not see gold fingers, flag the mismatch for inspection. Absence in a photo
    # is never promoted to confirmed missing automatically.
    result = result or {}
    label = str(result.get("board_type", "")).lower()
    signals_dict = result.get("signals") or {}
    expected_edge = any(k in label for k in ("edge-connector", "expansion", "ram", "memory module"))
    fingers_visible = bool(signals_dict.get("gold_fingers") or signals_dict.get("gold_finger_edge"))
    if expected_edge and not fingers_visible:
        observations["gold_finger_edge"] = {
            "status": "expected_not_visible",
            "value_impact": "high",
            "note": "Board family commonly carries an edge connector, but gold fingers are not verified in this image. Inspect for cropping or harvesting before pricing.",
        }
        signals.append({"signal": "expected_value_feature_not_verified", "feature": "gold_finger_edge", "confidence": "advisory"})

    status = "inspection_needed" if observations else "no_visual_modification_signal"
    return {
        "mode": "SPIKE Modification Detector v0.1",
        "status": status,
        "observations": observations,
        "signals": signals,
        "rule": "Possible absence is not confirmed removal. Only verified physical loss may reduce purchase value.",
    }
