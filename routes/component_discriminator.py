"""Visual component-family discrimination for Board Sense.

This is deliberately a conservative heuristic layer, not exact part
identification. v0.5 follows a prove-it-before-you-name-it rule: a silhouette
must have supporting visual evidence before it is allowed to influence the Jury
or appear as a confident Board Blueprint marker.
"""

import cv2
import numpy as np


def _board_mask(image):
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    green = cv2.inRange(hsv, np.array([28, 38, 24]), np.array([105, 255, 250]))
    green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    green = cv2.morphologyEx(green, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    if cv2.countNonZero(green) / max(h * w, 1) >= 0.08:
        contours, _ = cv2.findContours(green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            mask = np.zeros((h, w), dtype=np.uint8)
            for c in contours:
                if cv2.contourArea(c) >= h * w * 0.01:
                    cv2.drawContours(mask, [c], -1, 255, -1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
            if cv2.countNonZero(mask) / max(h * w, 1) >= 0.08:
                return mask
    band_h, band_w = max(2, h // 20), max(2, w // 20)
    border = np.concatenate([gray[:band_h, :].ravel(), gray[-band_h:, :].ravel(), gray[:, :band_w].ravel(), gray[:, -band_w:].ravel()])
    bg = int(np.median(border))
    diff = cv2.absdiff(gray, np.full_like(gray, bg))
    _, fg = cv2.threshold(diff, 24, 255, cv2.THRESH_BINARY)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((13, 13), np.uint8))
    contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return np.full((h, w), 255, dtype=np.uint8)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(mask, [max(contours, key=cv2.contourArea)], -1, 255, -1)
    return mask


def _inside(mask, cx, cy, radius=0):
    h, w = mask.shape[:2]
    cx, cy = int(cx), int(cy)
    if cx < 0 or cy < 0 or cx >= w or cy >= h or mask[cy, cx] == 0:
        return False
    if radius <= 1:
        return True
    points = [(cx + radius, cy), (cx - radius, cy), (cx, cy + radius), (cx, cy - radius)]
    good = 0
    for x, y in points:
        x, y = min(w - 1, max(0, x)), min(h - 1, max(0, y))
        good += 1 if mask[y, x] else 0
    return good >= 3


def _gold_ratio(hsv_roi):
    if hsv_roi.size == 0:
        return 0.0
    gold = cv2.inRange(hsv_roi, np.array([7, 55, 55]), np.array([38, 255, 255]))
    return float(cv2.countNonZero(gold) / max(gold.size, 1))


def _roi_metrics(gray, hsv, edges, x, y, w, h):
    roi_gray = gray[y:y+h, x:x+w]
    roi_hsv = hsv[y:y+h, x:x+w]
    roi_edges = edges[y:y+h, x:x+w]
    if roi_gray.size == 0:
        return 0.0, 0.0, 0.0, 0.0
    edge_density = float(cv2.countNonZero(roi_edges) / max(roi_edges.size, 1))
    darkness = float(np.mean(roi_gray < 105))
    saturation = float(np.mean(roi_hsv[:, :, 1])) if roi_hsv.size else 0.0
    gold = _gold_ratio(roi_hsv)
    return edge_density, darkness, saturation, gold


def discriminate_components(image_path):
    result = {"ic_like": 0, "capacitor_like": 0, "contact_pad_like": 0, "transformer_relay_like": 0, "small_component_like": 0, "uncertain_like": 0, "dominant_family": "unknown", "logic_component_ratio": 0.0, "power_component_ratio": 0.0, "regions": [], "notes": []}
    try:
        image = cv2.imread(image_path)
        if image is None:
            return result
        oh, ow = image.shape[:2]
        height, width, scale = oh, ow, 1.0
        if max(width, height) > 1400:
            scale = 1400.0 / max(width, height)
            image = cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
            height, width = image.shape[:2]
        inv_scale = 1.0 / scale
        board_mask = _board_mask(image)
        board_area = max(cv2.countNonZero(board_mask), 1)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 60, 155)
        _, dark = cv2.threshold(blur, 78, 255, cv2.THRESH_BINARY_INV)
        dark = cv2.bitwise_and(dark, board_mask)
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        ic_like = block_like = small_like = uncertain_like = 0
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
            rectangularity = area / max(w * h, 1)
            aspect = max(w, h) / max(min(w, h), 1)
            edge_density, darkness, mean_sat, gold = _roi_metrics(gray, hsv, edges, x, y, w, h)
            region_type, confidence = None, 0
            # ICs need a dark, compact rectangular body plus enough local edge
            # structure to support a packaged component rather than a shadow/slot.
            ic_shape = 0.001 <= area_ratio <= 0.040 and rectangularity >= 0.70 and aspect <= 3.6
            ic_support = darkness >= 0.58 and edge_density >= 0.055 and gold < 0.30
            if ic_shape and ic_support:
                ic_like += 1
                region_type = "IC-like package"
                confidence = min(91, int(52 + rectangularity * 24 + min(edge_density, .18) * 70))
            else:
                block_shape = 0.012 <= area_ratio <= 0.15 and rectangularity >= 0.58 and aspect <= 3.8
                block_support = edge_density >= 0.045 and darkness >= 0.28 and gold < 0.35
                if block_shape and block_support:
                    block_like += 1
                    region_type = "Power block / transformer / relay-like"
                    confidence = min(86, int(47 + rectangularity * 23 + min(edge_density, .18) * 60))
                elif 0.00008 <= area_ratio < 0.001:
                    small_like += 1
                elif ic_shape or (0.008 <= area_ratio <= 0.16 and rectangularity >= 0.50):
                    uncertain_like += 1
                    # Keep weak evidence available for debugging, but do not let
                    # it masquerade as a named component in the Blueprint/Jury.
            if region_type and confidence >= 62:
                regions.append({"type": region_type, "x": int(x * inv_scale), "y": int(y * inv_scale), "w": int(w * inv_scale), "h": int(h * inv_scale), "confidence": confidence, "evidence": {"edge_density": round(edge_density, 3), "darkness": round(darkness, 3), "rectangularity": round(rectangularity, 3)}})

        circle_blur = cv2.GaussianBlur(gray, (11, 11), 1.8)
        min_radius = max(8, int(min(width, height) * 0.016))
        max_radius = max(min_radius + 2, int(min(width, height) * 0.075))
        circles = cv2.HoughCircles(circle_blur, cv2.HOUGH_GRADIENT, dp=1.25, minDist=max(28, min_radius * 2.8), param1=120, param2=36, minRadius=min_radius, maxRadius=max_radius)
        capacitor_candidates, contact_candidates = [], []
        circle_edges = cv2.Canny(circle_blur, 70, 170)
        saturation = hsv[:, :, 1]
        if circles is not None:
            for cx, cy, radius in np.round(circles[0]).astype(int):
                if not _inside(board_mask, cx, cy, max(2, int(radius * 0.8))):
                    continue
                x1, y1, x2, y2 = max(0, cx-radius), max(0, cy-radius), min(width, cx+radius+1), min(height, cy+radius+1)
                roi_edges, roi_sat, roi_hsv = circle_edges[y1:y2, x1:x2], saturation[y1:y2, x1:x2], hsv[y1:y2, x1:x2]
                if roi_edges.size == 0:
                    continue
                edge_density = cv2.countNonZero(roi_edges) / roi_edges.size
                mean_sat = float(np.mean(roi_sat)) if roi_sat.size else 0.0
                gold_ratio = _gold_ratio(roi_hsv)
                if edge_density < 0.085:
                    continue
                if gold_ratio >= 0.28 and mean_sat >= 48:
                    contact_candidates.append((cx, cy, radius, edge_density, gold_ratio))
                elif edge_density >= 0.115:
                    capacitor_candidates.append((cx, cy, radius, edge_density))
        capacitor_candidates = sorted(capacitor_candidates, key=lambda c: c[2], reverse=True)[:18]
        contact_candidates = sorted(contact_candidates, key=lambda c: c[2], reverse=True)[:24]
        for cx, cy, radius, ed in capacitor_candidates:
            confidence = min(86, int(52 + ed * 165))
            if confidence >= 62:
                regions.append({"type": "Capacitor-like round component", "x": int((cx-radius)*inv_scale), "y": int((cy-radius)*inv_scale), "w": int(radius*2*inv_scale), "h": int(radius*2*inv_scale), "confidence": confidence})
        for cx, cy, radius, ed, gold in contact_candidates:
            confidence = min(93, int(59 + gold * 55 + ed * 42))
            if confidence >= 65:
                regions.append({"type": "Plated contact / keypad pad", "x": int((cx-radius)*inv_scale), "y": int((cy-radius)*inv_scale), "w": int(radius*2*inv_scale), "h": int(radius*2*inv_scale), "confidence": confidence})
        capacitor_like, contact_pad_like = len(capacitor_candidates), len(contact_candidates)
        result.update({"ic_like": ic_like, "capacitor_like": capacitor_like, "contact_pad_like": contact_pad_like, "transformer_relay_like": block_like, "small_component_like": small_like, "uncertain_like": uncertain_like})
        result["regions"] = sorted(regions, key=lambda item: (item["confidence"], item["w"] * item["h"]), reverse=True)[:24]
        total_major = max(ic_like + capacitor_like + block_like, 1)
        result["logic_component_ratio"] = round(ic_like / total_major, 3)
        result["power_component_ratio"] = round((capacitor_like + block_like) / total_major, 3)
        if ic_like >= 3 and ic_like > capacitor_like + block_like:
            result["dominant_family"] = "logic_ic"
        elif capacitor_like + block_like >= 4 and capacitor_like + block_like > ic_like * 1.35:
            result["dominant_family"] = "power_components"
        elif ic_like or capacitor_like or block_like:
            result["dominant_family"] = "mixed"
        result["notes"].append("v0.5 prove-it-before-you-name-it filtering is active.")
        result["notes"].append("Named regions require shape plus independent local visual support.")
        if uncertain_like:
            result["notes"].append(f"Suppressed {uncertain_like} weak rectangular candidates rather than naming them confidently.")
        if contact_pad_like:
            result["notes"].append(f"Separated {contact_pad_like} plated/contact-pad candidates from capacitor evidence.")
    except Exception as exc:
        print(f"[Component Discriminator Error] {exc}")
    return result
