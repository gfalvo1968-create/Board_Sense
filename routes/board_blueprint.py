"""Generate an annotated Board Blueprint from the user's actual board photo."""

from pathlib import Path
import cv2


LABELS = {
    "IC-like package": "IC / Logic Package",
    "Power block / transformer / relay-like": "Power / Transformer / Relay",
    "Capacitor-like round component": "Capacitor-like Component",
}


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
    thickness = max(2, int(max(width, height) / 700))
    font_scale = max(0.55, min(1.1, max(width, height) / 1400))
    radius = max(14, int(max(width, height) / 65))

    index = []
    for number, region in enumerate((component_regions or [])[:16], start=1):
        x = max(0, int(region.get("x", 0)))
        y = max(0, int(region.get("y", 0)))
        w = max(1, int(region.get("w", 1)))
        h = max(1, int(region.get("h", 1)))
        x2 = min(width - 1, x + w)
        y2 = min(height - 1, y + h)
        cx = min(width - radius - 2, max(radius + 2, x + w // 2))
        cy = min(height - radius - 2, max(radius + 2, y + h // 2))

        cv2.rectangle(image, (x, y), (x2, y2), (0, 255, 255), thickness)
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
            "box": {"x": x, "y": y, "w": w, "h": h},
        })

    cv2.imwrite(str(output_path), image)
    return {
        "available": True,
        "image_filename": output_name,
        "component_index": index,
        "marker_count": len(index),
        "note": "Blueprint markers show detector-supported regions on the user's uploaded photo. Labels are visual hypotheses, not guaranteed exact part identification.",
    }
