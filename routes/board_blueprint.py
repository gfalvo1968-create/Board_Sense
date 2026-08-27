"""Generate a clean, ranked Board Blueprint from the user's actual board photo.

Blueprint v0.2 keeps all detector evidence internally but presents only the most
useful, non-overlapping regions to the user. The goal is a readable field guide,
not a screen full of detector boxes.
"""

from pathlib import Path
import math
import cv2


LABELS = {
    "IC-like package": "IC / Logic Package",
    "Power block / transformer / relay-like": "Power / Transformer / Relay",
    "Capacitor-like round component": "Capacitor / Power Component",
    "Plated contact / keypad pad": "Plated Contact / Keypad Pad",
    "Gold finger / edge contact": "Gold Finger / Edge Contact",
}

# Higher values make a region more useful on the customer-facing blueprint.
TYPE_PRIORITY = {
    "Gold finger / edge contact": 6.0,
    "Plated contact / keypad pad": 5.0,
    "Power block / transformer / relay-like": 4.5,
    "IC-like package": 4.0,
    "Capacitor-like round component": 2.0,
}


def _confidence(region):
    value = region.get("confidence", 0.0)
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return value / 100.0 if value > 1.0 else value


def _iou(a, b):
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = ax1 + a["w"], ay1 + a["h"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = bx1 + b["w"], by1 + b["h"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union else 0.0


def _rank_regions(regions, image_area, limit=12):
    ranked = []
    for raw in regions or []:
        region = dict(raw)
        region["x"] = max(0, int(region.get("x", 0)))
        region["y"] = max(0, int(region.get("y", 0)))
        region["w"] = max(1, int(region.get("w", 1)))
        region["h"] = max(1, int(region.get("h", 1)))
        rtype = region.get("type", "Detected region")
        area_ratio = (region["w"] * region["h"]) / max(1, image_area)
        score = TYPE_PRIORITY.get(rtype, 1.0)
        score += _confidence(region) * 4.0
        score += min(1.5, math.sqrt(max(0.0, area_ratio)) * 5.0)
        region["_blueprint_score"] = score
        ranked.append(region)

    ranked.sort(key=lambda r: r["_blueprint_score"], reverse=True)

    selected = []
    type_counts = {}
    for region in ranked:
        rtype = region.get("type", "Detected region")
        # Prevent repetitive detections from dominating the finished sheet.
        per_type_limit = 4 if rtype == "IC-like package" else 3
        if type_counts.get(rtype, 0) >= per_type_limit:
            continue
        if any(_iou(region, kept) > 0.38 for kept in selected):
            continue
        selected.append(region)
        type_counts[rtype] = type_counts.get(rtype, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def generate_blueprint(image_path, component_regions, output_dir):
    image = cv2.imread(str(image_path))
    if image is None:
        return {"available": False, "message": "Blueprint could not read the uploaded image."}

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(image_path).stem
    output_name = f"{stem}_blueprint.png"
    output_path = output_dir / output_name

    height, width = image.shape[:2]
    image_area = width * height
    thickness = max(2, int(max(width, height) / 720))
    font_scale = max(0.55, min(1.05, max(width, height) / 1500))
    radius = max(15, int(max(width, height) / 62))

    selected = _rank_regions(component_regions, image_area, limit=12)
    index = []

    for number, region in enumerate(selected, start=1):
        x = min(width - 1, region["x"])
        y = min(height - 1, region["y"])
        w = min(region["w"], max(1, width - x))
        h = min(region["h"], max(1, height - y))
        cx = min(width - radius - 2, max(radius + 2, x + w // 2))
        cy = min(height - radius - 2, max(radius + 2, y + h // 2))

        # v0.2 intentionally removes the large yellow rectangles. A compact
        # numbered marker keeps the original board visible and readable.
        cv2.circle(image, (cx, cy), radius, (0, 0, 0), -1)
        cv2.circle(image, (cx, cy), radius, (0, 255, 255), thickness)
        text = str(number)
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        cv2.putText(
            image,
            text,
            (cx - tw // 2, cy + th // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (0, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

        region_type = region.get("type", "Detected region")
        index.append({
            "number": number,
            "label": LABELS.get(region_type, region_type),
            "detector_label": region_type,
            "confidence": region.get("confidence"),
            "importance": round(region.get("_blueprint_score", 0.0), 2),
            "box": {"x": x, "y": y, "w": w, "h": h},
        })

    cv2.imwrite(str(output_path), image)
    return {
        "available": True,
        "image_filename": output_name,
        "component_index": index,
        "marker_count": len(index),
        "candidate_region_count": len(component_regions or []),
        "mode": "Board Blueprint v0.2",
        "note": "The finished blueprint shows only the highest-value, non-overlapping detector-supported regions. Additional candidate regions remain available to the analysis engine but are hidden to keep the board readable.",
    }
