# routes/board_visual.py

import cv2
import numpy as np


def detect_visual_features(image_path):
    """Extract visual evidence directly from the uploaded board image."""

    visual = {
        "wide_skinny_board": False,
        "possible_ram": False,
        "gold_finger_edge": False,
        "possible_large_ic_chips": False,
        "aspect_ratio": 0.0,
        "gold_ratio": 0.0,
        "dark_component_density": 0.0,
        "large_dark_components": 0,
    }

    try:
        image = cv2.imread(image_path)
        if image is None:
            return visual

        height, width = image.shape[:2]
        long_side = max(width, height)
        short_side = min(width, height)
        ratio = long_side / short_side if short_side else 0.0
        visual["aspect_ratio"] = round(float(ratio), 3)

        # Long, narrow boards are often RAM or similar edge-connector boards.
        if ratio >= 2.4:
            visual["wide_skinny_board"] = True
            visual["possible_ram"] = True

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Detect gold-like material near any outer edge, where connector fingers
        # are commonly found. HSV is more stable than fixed RGB thresholds.
        gold_lower = np.array([10, 70, 80], dtype=np.uint8)
        gold_upper = np.array([38, 255, 255], dtype=np.uint8)
        gold_mask = cv2.inRange(hsv, gold_lower, gold_upper)

        edge_band = max(1, int(min(width, height) * 0.18))
        edge_mask = np.zeros((height, width), dtype=np.uint8)
        edge_mask[:edge_band, :] = 255
        edge_mask[-edge_band:, :] = 255
        edge_mask[:, :edge_band] = 255
        edge_mask[:, -edge_band:] = 255

        edge_gold = cv2.bitwise_and(gold_mask, edge_mask)
        edge_pixels = max(int(np.count_nonzero(edge_mask)), 1)
        gold_ratio = np.count_nonzero(edge_gold) / edge_pixels
        visual["gold_ratio"] = round(float(gold_ratio), 4)

        if gold_ratio >= 0.025:
            visual["gold_finger_edge"] = True

        # Look for dark rectangular component regions that can represent larger
        # IC packages. We keep this conservative to avoid calling every shadow
        # or dark PCB area a valuable chip.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, dark_mask = cv2.threshold(gray, 72, 255, cv2.THRESH_BINARY_INV)

        kernel = np.ones((3, 3), np.uint8)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(
            dark_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        image_area = max(width * height, 1)
        qualifying_components = 0
        qualifying_area = 0.0

        for contour in contours:
            area = cv2.contourArea(contour)
            if area <= 0:
                continue

            area_ratio = area / image_area
            if area_ratio < 0.0015 or area_ratio > 0.08:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            rect_area = max(w * h, 1)
            rectangularity = area / rect_area

            if rectangularity >= 0.55:
                qualifying_components += 1
                qualifying_area += area

        visual["large_dark_components"] = qualifying_components
        visual["dark_component_density"] = round(
            float(qualifying_area / image_area),
            4,
        )

        if qualifying_components >= 2:
            visual["possible_large_ic_chips"] = True

    except Exception as exc:
        print(f"[Board Visual Error] {exc}")

    return visual
