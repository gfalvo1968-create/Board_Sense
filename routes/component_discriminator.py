"""Visual component-family discrimination for Board Sense.

This is a heuristic layer, not exact part identification. It separates common
component silhouettes so dark/large parts are not automatically treated as ICs.
It also preserves candidate coordinates so Board Blueprint can show users where
the detected evidence appears on their actual uploaded board photo.

v0.3 adds a board-region mask and a much stricter round-component filter so
solder pads, holes, blanket/background texture, and printed circles are not all
promoted to capacitors.
"""

import cv2
import numpy as np


def _board_mask(image):
    """Return a conservative mask for the main PCB/foreground region."""
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Prefer common green PCB solder mask when it occupies a meaningful area.
    green = cv2.inRange(hsv, np.array([28, 38, 24]), np.array([105, 255, 250]))
    green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    green = cv2.morphologyEx(green, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    if cv2.countNonZero(green) / max(h * w, 1) >= 0.08:
        contours, _ = cv2.findContours(green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            mask = np.zeros((h, w), dtype=np.uint8)
            # Keep substantial green regions; components may split the board surface.
            for c in contours:
                if cv2.contourArea(c) >= h * w * 0.01:
                    cv2.drawContours(mask, [c], -1, 255, -1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
            if cv2.countNonZero(mask) / max(h * w, 1) >= 0.08:
                return mask

    # Fallback: estimate foreground from the border background tone.
    band_h = max(2, h // 20)
    band_w = max(2, w // 20)
    border = np.concatenate([
        gray[:band_h, :].ravel(), gray[-band_h:, :].ravel(),
        gray[:, :band_w].ravel(), gray[:, -band_w:].ravel(),
    ])
    bg = int(np.median(border))
    diff = cv2.absdiff(gray, np.full_like(gray, bg))
    _, fg = cv2.threshold(diff, 24, 255, cv2.THRESH_BINARY)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((13, 13), np.uint8))
    contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return np.full((h, w), 255, dtype=np.uint8)
    c = max(contours, key=cv2.contourArea)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(mask, [c], -1, 255, -1)
    return mask


def _inside(mask, cx, cy, radius=0):
    h, w = mask.shape[:2]
    cx, cy = int(cx), int(cy)
    if cx < 0 or cy < 0 or cx >= w or cy >= h or mask[cy, cx] == 0:
        return False
    if radius <= 1:
        return True
    # Require most cardinal points of the candidate to stay on the board.
    points = [
        (cx + radius, cy), (cx - radius, cy),
        (cx, cy + radius), (cx, cy - radius),
    ]
    good = 0
    for x, y in points:
        x = min(w - 1, max(0, x)); y = min(h - 1, max(0, y))
        good += 1 if mask[y, x] else 0
    return good >= 3


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
        board_mask = _board_mask(image)
        board_area = max(cv2.countNonZero(board_mask), 1)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        _, dark = cv2.threshold(blur, 78, 255, cv2.THRESH_BINARY_INV)
        dark = cv2.bitwise_and(dark, board_mask)
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
            x, y, w, h = cv2.boundingRect(contour)
            cx, cy = x + w // 2, y + h // 2
            if not _inside(board_mask, cx, cy):
                continue
            area_ratio = area / board_area
            rect_area = max(w * h, 1)
            rectangularity = area / rect_area
            aspect = max(w, h) / max(min(w, h), 1)

            region_type = None
            confidence = 0
            if 0.001 <= area_ratio <= 0.045 and rectangularity >= 0.66 and aspect <= 4.2:
                ic_like += 1
                region_type = "IC-like package"
                confidence = min(95, int(66 + rectangularity * 25))
            elif 0.010 <= area_ratio <= 0.16 and rectangularity >= 0.52:
                block_like += 1
                region_type = "Power block / transformer / relay-like"
                confidence = min(90, int(56 + rectangularity * 25))
            elif 0.00008 <= area_ratio < 0.001:
                small_like += 1

            if region_type:
                regions.append({
                    "type": region_type,
                    "x": int(x * inv_scale), "y": int(y * inv_scale),
                    "w": int(w * inv_scale), "h": int(h * inv_scale),
                    "confidence": confidence,
                })

        # Round-component pass. Hough circles alone are too permissive on PCBs,
        # so candidates must be on the board, reasonably sized, and have local
        # edge/contrast evidence consistent with a physical cylindrical part.
        circle_blur = cv2.GaussianBlur(gray, (11, 11), 1.8)
        min_radius = max(8, int(min(width, height) * 0.016))
        max_radius = max(min_radius + 2, int(min(width, height) * 0.075))
        circles = cv2.HoughCircles(
            circle_blur, cv2.HOUGH_GRADIENT,
            dp=1.25,
            minDist=max(28, min_radius * 2.8),
            param1=120,
            param2=36,
            minRadius=min_radius,
            maxRadius=max_radius,
        )

        accepted_circles = []
        edges = cv2.Canny(circle_blur, 70, 170)
        saturation = hsv[:, :, 1]
        if circles is not None:
            for cx, cy, radius in np.round(circles[0]).astype(int):
                if not _inside(board_mask, cx, cy, max(2, int(radius * 0.8))):
                    continue
                x1, y1 = max(0, cx-radius), max(0, cy-radius)
                x2, y2 = min(width, cx+radius+1), min(height, cy+radius+1)
                roi_edges = edges[y1:y2, x1:x2]
                roi_sat = saturation[y1:y2, x1:x2]
                if roi_edges.size == 0:
                    continue
                edge_density = cv2.countNonZero(roi_edges) / roi_edges.size
                mean_sat = float(np.mean(roi_sat)) if roi_sat.size else 0.0
                # Reject smooth printed circles/holes and weak background texture.
                if edge_density < 0.075:
                    continue
                if edge_density < 0.11 and mean_sat < 28:
                    continue
                accepted_circles.append((cx, cy, radius, edge_density))

        # Extra safety valve: a real whole board can have many capacitors, but
        # hundreds of accepted Hough circles is still diagnostic of false positives.
        accepted_circles = sorted(accepted_circles, key=lambda c: c[2], reverse=True)[:40]
        capacitor_like = len(accepted_circles)
        for cx, cy, radius, edge_density in accepted_circles:
            confidence = min(88, int(55 + edge_density * 170))
            regions.append({
                "type": "Capacitor-like round component",
                "x": int((cx - radius) * inv_scale),
                "y": int((cy - radius) * inv_scale),
                "w": int(radius * 2 * inv_scale),
                "h": int(radius * 2 * inv_scale),
                "confidence": confidence,
            })

        result["ic_like"] = ic_like
        result["capacitor_like"] = capacitor_like
        result["transformer_relay_like"] = block_like
        result["small_component_like"] = small_like
        result["regions"] = sorted(
            regions,
            key=lambda item: (item["confidence"], item["w"] * item["h"]),
            reverse=True,
        )[:24]

        total_major = max(ic_like + capacitor_like + block_like, 1)
        result["logic_component_ratio"] = round(ic_like / total_major, 3)
        result["power_component_ratio"] = round((capacitor_like + block_like) / total_major, 3)

        if ic_like >= 3 and ic_like > capacitor_like + block_like:
            result["dominant_family"] = "logic_ic"
            result["notes"].append("Rectangular IC-like packages dominate the visible major components.")
        elif capacitor_like + block_like >= 4 and capacitor_like + block_like > ic_like * 1.35:
            result["dominant_family"] = "power_components"
            result["notes"].append("Filtered round/power components dominate the visible board region.")
        elif ic_like or capacitor_like or block_like:
            result["dominant_family"] = "mixed"
            result["notes"].append("Mixed logic and power-component silhouettes detected.")

        result["notes"].append("Component candidates are filtered to the estimated PCB/foreground region.")
        if capacitor_like:
            result["notes"].append(f"Accepted {capacitor_like} round-component candidates after stricter filtering.")

    except Exception as exc:
        print(f"[Component Discriminator Error] {exc}")

    return result
