"""SPIKE Single-Frame Board Identity Gate v0.1.

Detects strong evidence that one uploaded photograph may contain more than one
physical PCB or overlapping PCB regions. This is intentionally conservative:
it does not claim two boards from color alone. It only blocks when a large PCB-
colored region has a strongly non-single-board silhouette with several deep
concavities, which is typical of overlapping/touching boards in one frame.

A block means: retake one physical board per photo. It does NOT mean the upload
is not a PCB.
"""
import cv2
import numpy as np


def inspect_frame(image_path):
    result = {
        "version": "SPIKE Single-Frame Board Identity Gate v0.1",
        "status": "SINGLE_BOARD_NOT_CONTRADICTED",
        "block_analysis": False,
        "confidence": 0,
        "evidence": [],
        "next_step": "Continue normal board analysis.",
    }
    try:
        im = cv2.imread(image_path)
        if im is None:
            result.update({"status": "FRAME_UNREADABLE", "confidence": 0})
            return result

        h, w = im.shape[:2]
        area = float(max(1, h * w))
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)

        # Green PCB support for v0.1. This is a suspicion detector only, never a
        # board classifier. Other solder-mask colors can be added independently.
        mask = cv2.inRange(hsv, np.array([28, 35, 22]), np.array([105, 255, 255]))
        k = max(5, (min(h, w) // 45) | 1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8), iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [c for c in contours if cv2.contourArea(c) >= area * 0.12]
        if not contours:
            return result

        c = max(contours, key=cv2.contourArea)
        board_area = float(cv2.contourArea(c))
        rect = cv2.minAreaRect(c)
        rw, rh = rect[1]
        rw, rh = max(float(rw), 1.0), max(float(rh), 1.0)
        hull_pts = cv2.convexHull(c)
        hull_area = max(float(cv2.contourArea(hull_pts)), 1.0)
        solidity = board_area / hull_area
        rectangularity = board_area / max(rw * rh, 1.0)

        hull_idx = cv2.convexHull(c, returnPoints=False)
        defects = cv2.convexityDefects(c, hull_idx) if hull_idx is not None and len(hull_idx) >= 3 and len(c) >= 4 else None
        deep_defects = []
        scale = max(rw, rh)
        if defects is not None:
            for d in defects[:, 0]:
                depth = float(d[3]) / 256.0
                if depth >= scale * 0.04:
                    deep_defects.append(depth / scale)

        area_ratio = board_area / area
        deep_count = len(deep_defects)
        deepest = max(deep_defects) if deep_defects else 0.0
        result["metrics"] = {
            "pcb_region_area_ratio": round(area_ratio, 3),
            "solidity": round(solidity, 3),
            "rectangularity": round(rectangularity, 3),
            "deep_concavity_count": int(deep_count),
            "deepest_concavity_ratio": round(deepest, 3),
        }

        # Strong suspicion profile calibrated against the known two-board-in-one-
        # frame regression. Requiring all conditions keeps ordinary irregular
        # single PCBs from being rejected from one noisy contour measurement.
        suspicious = (
            0.20 <= area_ratio <= 0.80
            and solidity < 0.91
            and rectangularity < 0.82
            and deep_count >= 5
            and deepest >= 0.08
        )

        if suspicious:
            result.update({
                "status": "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED",
                "block_analysis": True,
                "confidence": 82,
                "evidence": [
                    "One photo contains a large PCB-like region with a strongly compound silhouette.",
                    "Several deep independent concavities suggest overlapping/touching board outlines rather than one clean physical board outline.",
                    "Board grading is withheld because one physical board per photo is required for reliable identity and recovery reasoning.",
                ],
                "next_step": "Retake the photo with exactly one physical board in the frame, separated from other boards.",
            })
        return result
    except Exception as exc:
        result["status"] = "FRAME_GATE_UNCERTAIN"
        result["error"] = str(exc)
        return result
