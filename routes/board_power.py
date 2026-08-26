import cv2
import numpy as np


def detect_power_board(image_path):
    """Estimate whether a board has power-supply-style visual characteristics."""
    signals = {
        "possible_power_board": False,
        "large_round_components": 0,
        "large_component_regions": 0,
        "sparse_component_layout": False,
        "power_score": 0,
    }

    try:
        image = cv2.imread(image_path)
        if image is None:
            return signals

        height, width = image.shape[:2]
        image_area = max(width * height, 1)

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
        blur = cv2.GaussianBlur(gray, (9, 9), 1.5)

        min_radius = max(8, int(min(width, height) * 0.018))
        max_radius = max(min_radius + 2, int(min(width, height) * 0.12))

        circles = cv2.HoughCircles(
            blur,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(20, min_radius * 2),
            param1=100,
            param2=28,
            minRadius=min_radius,
            maxRadius=max_radius,
        )

        round_count = 0 if circles is None else len(circles[0])
        signals["large_round_components"] = int(round_count)

        edges = cv2.Canny(blur, 60, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        large_regions = 0
        medium_regions = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area <= 0:
                continue
            ratio = area / image_area
            if 0.01 <= ratio <= 0.18:
                large_regions += 1
            elif 0.002 <= ratio < 0.01:
                medium_regions += 1

        signals["large_component_regions"] = int(large_regions)

        # Power boards commonly have fewer, physically larger parts than dense
        # logic boards. This heuristic is intentionally conservative.
        signals["sparse_component_layout"] = (
            large_regions >= 2 and medium_regions <= 18
        )

        power_score = 0
        if round_count >= 2:
            power_score += 2
        if round_count >= 4:
            power_score += 2
        if large_regions >= 2:
            power_score += 2
        if signals["sparse_component_layout"]:
            power_score += 2

        signals["power_score"] = power_score
        signals["possible_power_board"] = power_score >= 5

    except Exception as exc:
        print(f"[Power Board Detector Error] {exc}")

    return signals
