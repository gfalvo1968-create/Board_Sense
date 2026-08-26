"""Conservative first-stage object gate for Board Sense.

The gate answers a simple question before board grading begins:
Is the uploaded image actually a PCB/board, a loose electronic component/module,
or something we should leave unknown?

This is deliberately conservative. It is better to route an uncertain image to
review/component mode than to manufacture a confident motherboard diagnosis.
"""

import cv2
import numpy as np


def _largest_foreground(gray):
    """Estimate the main foreground object using border-derived background tone."""
    h, w = gray.shape[:2]
    border = np.concatenate([
        gray[: max(2, h // 20), :].ravel(),
        gray[-max(2, h // 20):, :].ravel(),
        gray[:, : max(2, w // 20)].ravel(),
        gray[:, -max(2, w // 20):].ravel(),
    ])
    background = float(np.median(border))
    diff = cv2.absdiff(gray, np.full_like(gray, int(background)))
    _, mask = cv2.threshold(diff, 24, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, 0.0
    contour = max(contours, key=cv2.contourArea)
    ratio = cv2.contourArea(contour) / max(h * w, 1)
    return contour, float(ratio)


def classify_object(image_path):
    result = {
        "mode": "unknown",
        "label": "Unknown object",
        "confidence": 35,
        "board_likelihood": 0,
        "component_likelihood": 0,
        "camera_module_likelihood": 0,
        "evidence": [],
        "message": "Not enough evidence to run board grading safely.",
    }

    try:
        image = cv2.imread(image_path)
        if image is None:
            result["message"] = "Image could not be read."
            return result

        h0, w0 = image.shape[:2]
        max_side = max(h0, w0)
        if max_side > 1200:
            scale = 1200.0 / max_side
            image = cv2.resize(image, (max(1, int(w0 * scale)), max(1, int(h0 * scale))), interpolation=cv2.INTER_AREA)

        h, w = image.shape[:2]
        area = max(h * w, 1)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Common green PCB solder-mask signal. Keep the range broad enough for
        # different lighting, while requiring saturation so gray backgrounds do not count.
        green_mask = cv2.inRange(hsv, np.array([30, 45, 28]), np.array([100, 255, 245]))
        green_ratio = float(cv2.countNonZero(green_mask) / area)

        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 60, 150)
        edge_ratio = float(cv2.countNonZero(edges) / area)

        foreground, foreground_ratio = _largest_foreground(gray)
        bbox_aspect = 0.0
        bbox_fill = 0.0
        compact = False
        if foreground is not None:
            x, y, bw, bh = cv2.boundingRect(foreground)
            bbox_aspect = max(bw, bh) / max(min(bw, bh), 1)
            bbox_fill = (bw * bh) / area
            compact = bbox_aspect <= 1.8 and bbox_fill <= 0.38

        # Lens-like evidence: one or more dark circular structures inside a compact
        # foreground object, useful for loose smartphone camera modules.
        blur = cv2.GaussianBlur(gray, (9, 9), 1.6)
        min_r = max(5, int(min(h, w) * 0.012))
        max_r = max(min_r + 2, int(min(h, w) * 0.11))
        circles = cv2.HoughCircles(
            blur,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(18, min_r * 2),
            param1=100,
            param2=26,
            minRadius=min_r,
            maxRadius=max_r,
        )
        circle_count = 0 if circles is None else len(circles[0])

        board_score = 0
        if green_ratio >= 0.22:
            board_score += 60
        elif green_ratio >= 0.10:
            board_score += 45
        elif green_ratio >= 0.055:
            board_score += 28
        if foreground_ratio >= 0.28:
            board_score += 18
        if edge_ratio >= 0.055:
            board_score += 12
        if foreground_ratio >= 0.50:
            board_score += 10
        board_score = min(board_score, 100)

        component_score = 0
        if 0.003 <= foreground_ratio <= 0.38:
            component_score += 42
        if green_ratio < 0.055:
            component_score += 22
        if compact:
            component_score += 18
        if edge_ratio >= 0.01:
            component_score += 8
        component_score = min(component_score, 100)

        camera_score = 0
        if component_score >= 55 and compact:
            camera_score += 35
        if circle_count >= 1:
            camera_score += 35
        if green_ratio < 0.025:
            camera_score += 15
        if bbox_aspect and bbox_aspect <= 1.45:
            camera_score += 10
        camera_score = min(camera_score, 100)

        result.update({
            "board_likelihood": int(board_score),
            "component_likelihood": int(component_score),
            "camera_module_likelihood": int(camera_score),
            "metrics": {
                "pcb_green_ratio": round(green_ratio, 4),
                "foreground_ratio": round(foreground_ratio, 4),
                "edge_ratio": round(edge_ratio, 4),
                "circle_count": int(circle_count),
            },
        })

        if board_score >= 58 and board_score >= component_score + 8:
            result["mode"] = "board"
            result["label"] = "Circuit board / PCB"
            result["confidence"] = max(60, min(96, board_score))
            result["evidence"] = [
                "PCB-like solder-mask area detected",
                "Board-scale foreground geometry detected",
                "Circuit-detail edge density supports board analysis",
            ]
            result["message"] = "Board evidence is strong enough to continue into Board Sense grading."
            return result

        if camera_score >= 65:
            result["mode"] = "component"
            result["label"] = "Phone camera / optical module"
            result["confidence"] = max(65, min(94, camera_score))
            result["evidence"] = [
                "Compact loose electronic module detected",
                "Circular lens-like structure detected",
                "Insufficient PCB-area evidence for whole-board grading",
            ]
            result["message"] = "Component mode selected; motherboard grading and board recovery scoring were intentionally skipped."
            return result

        if component_score >= 58 and board_score < 58:
            result["mode"] = "component"
            result["label"] = "Loose electronic component / module"
            result["confidence"] = max(58, min(90, component_score))
            result["evidence"] = [
                "Compact foreground object detected",
                "Insufficient PCB-area evidence for whole-board grading",
            ]
            result["message"] = "Component mode selected; board-specific grading was intentionally skipped."
            return result

        result["confidence"] = max(30, min(55, max(board_score, component_score)))
        result["evidence"] = ["Input does not yet meet the confidence threshold for board or component mode."]
        return result

    except Exception as exc:
        print(f"[Object Gate Error] {exc}")
        result["message"] = "Object gate could not classify the image safely."
        return result
