"""Visual component-family discrimination for Board Sense.

This is a heuristic layer, not exact part identification. It separates common
component silhouettes so dark/large parts are not automatically treated as ICs.
It also preserves candidate coordinates so Board Blueprint can show users where
the detected evidence appears on their actual uploaded board photo.
"""

import cv2
import numpy as np


def discriminate_components(image_path):
    result = {
        "ic_like": 0,
        "capacitor_like": 0,
        "transformer_relay_like": 0,
        "small_component_like": 0,
        "dominant_family": "unknown",
        "logic_component_ratio": 0.0,
        "power_component_ratio": 0.0,
        "regions": [],
        "notes": [],
    }

    try:
        image = cv2.imread(image_path)
        if image is None:
            return result

        original_height, original_width = image.shape[:2]
        height, width = original_height, original_width
        scale = 1.0
        max_side = max(width, height)
        if max_side > 1400:
            scale = 1400.0 / max_side
            image = cv2.resize(
                image,
                (max(1, int(width * scale)), max(1, int(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
            height, width = image.shape[:2]

        inv_scale = 1.0 / scale
        image_area = max(width * height, 1)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        _, dark = cv2.threshold(blur, 78, 255, cv2.THRESH_BINARY_INV)
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        ic_like = 0
        block_like = 0
        small_like = 0
        regions = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area <= 0:
                continue
            area_ratio = area / image_area
            x, y, w, h = cv2.boundingRect(contour)
            rect_area = max(w * h, 1)
            rectangularity = area / rect_area
            aspect = max(w, h) / max(min(w, h), 1)

            region_type = None
            confidence = 0
            if 0.001 <= area_ratio <= 0.045 and rectangularity >= 0.62 and aspect <= 4.5:
                ic_like += 1
                region_type = "IC-like package"
                confidence = min(95, int(65 + rectangularity * 25))
            elif 0.008 <= area_ratio <= 0.16 and rectangularity >= 0.48:
                block_like += 1
                region_type = "Power block / transformer / relay-like"
                confidence = min(90, int(55 + rectangularity * 25))
            elif 0.00008 <= area_ratio < 0.001:
                small_like += 1

            if region_type:
                regions.append({
                    "type": region_type,
                    "x": int(x * inv_scale),
                    "y": int(y * inv_scale),
                    "w": int(w * inv_scale),
                    "h": int(h * inv_scale),
                    "confidence": confidence,
                })

        circle_blur = cv2.GaussianBlur(gray, (9, 9), 1.5)
        min_radius = max(6, int(min(width, height) * 0.012))
        max_radius = max(min_radius + 2, int(min(width, height) * 0.10))
        circles = cv2.HoughCircles(
            circle_blur,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(18, min_radius * 2),
            param1=100,
            param2=28,
            minRadius=min_radius,
            maxRadius=max_radius,
        )
        capacitor_like = 0 if circles is None else int(len(circles[0]))
        if circles is not None:
            for cx, cy, radius in np.round(circles[0]).astype(int):
                regions.append({
                    "type": "Capacitor-like round component",
                    "x": int((cx - radius) * inv_scale),
                    "y": int((cy - radius) * inv_scale),
                    "w": int(radius * 2 * inv_scale),
                    "h": int(radius * 2 * inv_scale),
                    "confidence": 70,
                })

        result["ic_like"] = ic_like
        result["capacitor_like"] = capacitor_like
        result["transformer_relay_like"] = block_like
        result["small_component_like"] = small_like
        result["regions"] = sorted(
            regions,
            key=lambda item: item["w"] * item["h"],
            reverse=True,
        )[:24]

        total_major = max(ic_like + capacitor_like + block_like, 1)
        result["logic_component_ratio"] = round(ic_like / total_major, 3)
        result["power_component_ratio"] = round((capacitor_like + block_like) / total_major, 3)

        if ic_like >= 3 and ic_like > capacitor_like + block_like:
            result["dominant_family"] = "logic_ic"
            result["notes"].append("Rectangular IC-like packages dominate the visible major components.")
        elif capacitor_like + block_like >= 3 and capacitor_like + block_like > ic_like:
            result["dominant_family"] = "power_components"
            result["notes"].append("Round capacitors and/or large block components dominate the visible layout.")
        elif ic_like or capacitor_like or block_like:
            result["dominant_family"] = "mixed"
            result["notes"].append("Mixed logic and power-component silhouettes detected.")

        if capacitor_like >= 2:
            result["notes"].append("Multiple capacitor-like circular components detected; avoid counting them as ICs.")
        if block_like >= 2:
            result["notes"].append("Multiple transformer/relay-like block regions detected; precious-metal assumptions should be conservative.")

    except Exception as exc:
        print(f"[Component Discriminator Error] {exc}")

    return result
