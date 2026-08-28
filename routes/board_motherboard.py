# routes/board_motherboard.py

import cv2
import numpy as np


def detect_motherboard(image_path):
    """Conservative structural motherboard detector.

    v0.2 treats motherboard-scale geometry plus repeated long slot/socket
    structures as stronger evidence than generic round power components.
    It is intentionally color-independent so green, brown, blue and black PCBs
    can all qualify.
    """
    signals = {
        "large_board": False,
        "possible_motherboard": False,
        "motherboard_structure_score": 0,
        "long_slot_candidates": 0,
        "parallel_slot_bank": False,
        "edge_connector_bank": False,
        "structural_evidence": [],
    }

    try:
        image = cv2.imread(image_path)
        if image is None:
            return signals
        h, w = image.shape[:2]
        long_side, short_side = max(w, h), min(w, h)
        ratio = long_side / max(short_side, 1)
        large_board = ratio < 2.2 and long_side > 700
        signals["large_board"] = large_board
        if large_board:
            signals["structural_evidence"].append("motherboard-scale rectangular board footprint")

        # Find long, narrow rectangular structures such as DIMM and PCI/PCIe
        # slots. We do not name an individual slot from shape alone; a repeated
        # bank is the useful family-level clue.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 55, 145)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        slots = []
        image_area = max(w * h, 1)
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            area_ratio = (cw * ch) / image_area
            aspect = max(cw, ch) / max(min(cw, ch), 1)
            if 4.5 <= aspect <= 24 and 0.0025 <= area_ratio <= 0.055 and max(cw, ch) >= int(long_side * 0.16):
                slots.append((x, y, cw, ch))
        # De-duplicate nested edge contours by approximate centers.
        centers = []
        for x, y, cw, ch in sorted(slots, key=lambda r: r[2] * r[3], reverse=True):
            cx, cy = x + cw // 2, y + ch // 2
            if all(abs(cx-px) > long_side*.035 or abs(cy-py) > long_side*.035 for px, py in centers):
                centers.append((cx, cy))
        slot_count = min(len(centers), 8)
        signals["long_slot_candidates"] = slot_count
        signals["parallel_slot_bank"] = slot_count >= 2
        if slot_count >= 2:
            signals["structural_evidence"].append(f"{slot_count} repeated long slot/socket structures")

        # Dense edge rectangles support a rear-I/O / connector-bank clue.
        edge_band = int(min(w, h) * .16)
        edge_count = 0
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            if cw * ch < image_area * .0015:
                continue
            near_edge = x < edge_band or y < edge_band or x + cw > w-edge_band or y + ch > h-edge_band
            aspect = max(cw, ch) / max(min(cw, ch), 1)
            if near_edge and 1.0 <= aspect <= 5.5:
                edge_count += 1
        signals["edge_connector_bank"] = edge_count >= 4
        if signals["edge_connector_bank"]:
            signals["structural_evidence"].append("dense rectangular connector structures along a board edge")

        score = 0
        if large_board: score += 2
        if slot_count >= 2: score += 4
        if slot_count >= 4: score += 2
        if signals["edge_connector_bank"]: score += 3
        signals["motherboard_structure_score"] = score
        signals["possible_motherboard"] = bool(large_board and (slot_count >= 2 or signals["edge_connector_bank"]) and score >= 6)

    except Exception as e:
        print(f"[Motherboard Detector Error] {e}")

    return signals
