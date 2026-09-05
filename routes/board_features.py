# routes/board_features.py

import cv2
import numpy as np


def detect_board_features(image_path):
    """Detect general board features from the image itself.

    Specialized RAM and motherboard detectors add their own signals later in
    the analysis pipeline. This module deliberately avoids using filenames as
    evidence so a photo named IMG_1234.jpg is treated the same as one named
    motherboard.jpg.

    Density thresholds are intentionally board-relative so older dense logic
    boards with many smaller packages are not treated like sparse modern PCBs.
    """

    features = {
        "motherboard": False,
        "ram": False,
        "memory_module": False,
        "power_board": False,
        "gold_fingers": False,
        "large_ic_chips": False,
        "processor": False,
        "dense_component_board": False,
        "component_count": 0,
        "component_density": 0.0,
    }

    try:
        image = cv2.imread(image_path)
        if image is None:
            return features

        height, width = image.shape[:2]
        image_area = max(width * height, 1)

        # Normalize very large photos so contour thresholds stay practical.
        max_side = max(width, height)
        if max_side > 1400:
            scale = 1400.0 / max_side
            image = cv2.resize(
                image,
                (max(1, int(width * scale)), max(1, int(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
            height, width = image.shape[:2]
            image_area = max(width * height, 1)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Use a slightly more permissive threshold than the old detector.
        # The old 0.0008 minimum area missed rows of smaller legacy ICs.
        _, dark_mask = cv2.threshold(gray, 86, 255, cv2.THRESH_BINARY_INV)
        kernel = np.ones((3, 3), np.uint8)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(
            dark_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        chip_like_count = 0
        chip_like_area = 0.0
        largest_chip_ratio = 0.0
        largest_chip_centered = False

        for contour in contours:
            area = cv2.contourArea(contour)
            if area <= 0:
                continue

            area_ratio = area / image_area
            if area_ratio < 0.00025 or area_ratio > 0.12:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            rect_area = max(w * h, 1)
            rectangularity = area / rect_area
            aspect = max(w, h) / max(min(w, h), 1)

            # Legacy logic packages can be small, slightly worn, or partially
            # obscured, so do not require near-perfect rectangles.
            if rectangularity < 0.46 or aspect > 5.2:
                continue

            chip_like_count += 1
            chip_like_area += area

            if area_ratio > largest_chip_ratio:
                largest_chip_ratio = area_ratio
                cx = x + (w / 2)
                cy = y + (h / 2)
                largest_chip_centered = (
                    width * 0.20 <= cx <= width * 0.80
                    and height * 0.20 <= cy <= height * 0.80
                )

        component_density = chip_like_area / image_area
        features["component_count"] = int(chip_like_count)
        features["component_density"] = round(float(component_density), 4)

        if chip_like_count >= 3:
            features["large_ic_chips"] = True

        # A board can be dense because of many small packages even when their
        # combined dark area is modest.
        if chip_like_count >= 8 or component_density >= 0.025:
            features["dense_component_board"] = True

        # A single dominant, centrally located package can be CPU/processor-like.
        # Keep this conservative; the package is a candidate, not chemistry/value.
        if largest_chip_centered and largest_chip_ratio >= 0.018:
            features["processor"] = True

        # Gold-like material close to an outside edge can indicate connector
        # fingers. The dedicated visual detector still performs the stricter
        # repeated-contact geometry confirmation.
        gold_lower = np.array([10, 75, 90], dtype=np.uint8)
        gold_upper = np.array([38, 255, 255], dtype=np.uint8)
        gold_mask = cv2.inRange(hsv, gold_lower, gold_upper)

        edge_band = max(1, int(min(width, height) * 0.15))
        edge_mask = np.zeros((height, width), dtype=np.uint8)
        edge_mask[:edge_band, :] = 255
        edge_mask[-edge_band:, :] = 255
        edge_mask[:, :edge_band] = 255
        edge_mask[:, -edge_band:] = 255

        edge_gold = cv2.bitwise_and(gold_mask, edge_mask)
        edge_pixels = max(int(np.count_nonzero(edge_mask)), 1)
        if (np.count_nonzero(edge_gold) / edge_pixels) >= 0.03:
            features["gold_fingers"] = True

    except Exception as exc:
        print(f"[Board Features Error] {exc}")

    return features
