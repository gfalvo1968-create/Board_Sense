"""SPIKE Secondary Board Plane Gate v0.1.

A conservative edge-supported detector for the case that defeated the green-silhouette
gate: a smaller PCB lies under/over a large rectangular PCB so the two green surfaces
merge into one silhouette.

The detector only fires when all of these agree:
1. a large rectangular PCB core has four independently supported outer edges;
2. a substantial rectangular board-like region exists outside that core;
3. the outside region meets the core at a strong physical edge line.

This is intentionally stricter than a generic shape detector so irregular single
motherboards (for example the Dell regression specimen) are not split merely because
they have wings, necks, or notches.
"""
from __future__ import annotations

import math
import cv2
import numpy as np


def _boundary_lines(image, board_mask):
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 45, 135)
    raw = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=60,
        minLineLength=max(40, int(min(h, w) * 0.08)),
        maxLineGap=max(12, int(min(h, w) * 0.025)),
    )
    if raw is None:
        return []

    green = board_mask > 0
    out = []
    for x1, y1, x2, y2 in np.asarray(raw).reshape(-1, 4):
        dx, dy = int(x2 - x1), int(y2 - y1)
        length = math.hypot(dx, dy)
        if length <= 1:
            continue
        angle = math.degrees(math.atan2(dy, dx)) % 180
        if min(angle, 180 - angle) <= 10:
            axis = "h"
        elif abs(angle - 90) <= 10:
            axis = "v"
        else:
            continue

        # A real PCB perimeter should have board surface on one side and visibly
        # different image content on the other. Internal slots/traces usually do not.
        t = np.linspace(0.0, 1.0, 28)
        xs = x1 + (x2 - x1) * t
        ys = y1 + (y2 - y1) * t
        nx, ny = -dy / length, dx / length
        plus, minus = [], []
        for offset in (8, 16, 24):
            xa = np.clip(np.rint(xs + nx * offset).astype(int), 0, w - 1)
            ya = np.clip(np.rint(ys + ny * offset).astype(int), 0, h - 1)
            xb = np.clip(np.rint(xs - nx * offset).astype(int), 0, w - 1)
            yb = np.clip(np.rint(ys - ny * offset).astype(int), 0, h - 1)
            plus.append(float(green[ya, xa].mean()))
            minus.append(float(green[yb, xb].mean()))
        a, b = float(np.mean(plus)), float(np.mean(minus))
        contrast = abs(a - b)
        if contrast < 0.35 or max(a, b) < 0.50:
            continue
        out.append(
            {
                "axis": axis,
                "pos": float((y1 + y2) / 2 if axis == "h" else (x1 + x2) / 2),
                "length": float(length),
                "contrast": round(contrast, 3),
                "coords": (int(x1), int(y1), int(x2), int(y2)),
            }
        )
    return out


def _clusters(lines, axis, span, full_length):
    items = sorted((x for x in lines if x["axis"] == axis), key=lambda x: x["pos"])
    tol = span * 0.035
    groups = []
    for item in items:
        if not groups:
            groups.append([item])
            continue
        prev = groups[-1]
        center = np.average([x["pos"] for x in prev], weights=[x["length"] for x in prev])
        if abs(item["pos"] - center) > tol:
            groups.append([item])
        else:
            prev.append(item)

    out = []
    for group in groups:
        pos = float(np.average([x["pos"] for x in group], weights=[x["length"] for x in group]))
        support = min(1.0, sum(x["length"] for x in group) / max(float(full_length), 1.0))
        out.append({"pos": pos, "support": support})
    return out


def _coverage(lines, axis, pos, a, b, h, w):
    tol = (h if axis == "h" else w) * 0.04
    total = 0.0
    for line in lines:
        if line["axis"] != axis or abs(line["pos"] - pos) > tol:
            continue
        x1, y1, x2, y2 = line["coords"]
        lo = min(x1, x2) if axis == "h" else min(y1, y2)
        hi = max(x1, x2) if axis == "h" else max(y1, y2)
        total += max(0.0, min(float(hi), b) - max(float(lo), a))
    return min(1.0, total / max(1.0, b - a))


def inspect_secondary_board_plane(image, board_mask):
    h, w = image.shape[:2]
    image_area = float(max(1, h * w))
    result = {
        "version": "SPIKE Secondary Board Plane Gate v0.1",
        "trigger": False,
        "primary_core": None,
        "secondary_candidate": None,
    }

    lines = _boundary_lines(image, board_mask)
    if len(lines) < 4:
        result["reason"] = "insufficient_supported_edges"
        return result

    hs = _clusters(lines, "h", h, w)
    vs = _clusters(lines, "v", w, h)
    best = None

    for li in range(len(vs)):
        for ri in range(li + 1, len(vs)):
            x1, x2 = vs[li]["pos"], vs[ri]["pos"]
            if x2 - x1 < w * 0.35:
                continue
            for ti in range(len(hs)):
                for bi in range(ti + 1, len(hs)):
                    y1, y2 = hs[ti]["pos"], hs[bi]["pos"]
                    rect_area = (x2 - x1) * (y2 - y1)
                    ratio = rect_area / image_area
                    if ratio < 0.20 or ratio > 0.90:
                        continue
                    xi1, xi2 = max(0, int(x1)), min(w, int(x2))
                    yi1, yi2 = max(0, int(y1)), min(h, int(y2))
                    if xi2 <= xi1 or yi2 <= yi1:
                        continue
                    fill = float((board_mask[yi1:yi2, xi1:xi2] > 0).mean())
                    if fill < 0.50:
                        continue
                    cov = [
                        _coverage(lines, "h", y1, x1, x2, h, w),
                        _coverage(lines, "h", y2, x1, x2, h, w),
                        _coverage(lines, "v", x1, y1, y2, h, w),
                        _coverage(lines, "v", x2, y1, y2, h, w),
                    ]
                    # Four-sided support is the Dell guardrail. Irregular single PCBs
                    # often have strong internal lines but do not form one clean core.
                    if min(cov) < 0.30:
                        continue
                    score = ratio * fill * (0.5 + 0.5 * (sum(cov) / 4.0))
                    candidate = {
                        "box": [round(x1 / w, 3), round(y1 / h, 3), round(x2 / w, 3), round(y2 / h, 3)],
                        "area_ratio": round(ratio, 3),
                        "board_fill": round(fill, 3),
                        "edge_coverage": [round(x, 3) for x in cov],
                        "score": round(score, 3),
                        "_px": (x1, y1, x2, y2),
                    }
                    if best is None or score > best["score"]:
                        best = candidate

    if best is None or best["score"] < 0.18:
        result["reason"] = "no_high_confidence_rectangular_core"
        return result

    result["primary_core"] = {k: v for k, v in best.items() if k != "_px"}
    x1, y1, x2, y2 = best["_px"]

    # Remove the rectangular core and inspect board-coloured material that remains
    # outside it. A real second board should form a substantial, compact slab.
    outside = (board_mask > 0).astype(np.uint8) * 255
    outside[max(0, int(y1)):min(h, int(y2)), max(0, int(x1)):min(w, int(x2))] = 0
    contours, _ = cv2.findContours(outside, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    secondary = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        area_ratio = area / image_area
        if area_ratio < 0.025:
            continue
        x, y, bw, bh = cv2.boundingRect(contour)
        rect = cv2.minAreaRect(contour)
        rw, rh = rect[1]
        rectangularity = area / max(float(rw) * float(rh), 1.0)
        hull = cv2.convexHull(contour)
        solidity = area / max(float(cv2.contourArea(hull)), 1.0)
        if rectangularity < 0.62 or solidity < 0.78:
            continue

        # Find which primary edge the outside slab meets, then demand a physical
        # edge line across that shared interface. That is the key distinction
        # between an overlapping second PCB and an integral motherboard wing.
        X1, Y1, X2, Y2 = float(x), float(y), float(x + bw), float(y + bh)
        adjacency = []
        if Y1 >= y2 - h * 0.06:
            adjacency.append(("bottom", abs(Y1 - y2), _coverage(lines, "h", y2, X1, X2, h, w)))
        if Y2 <= y1 + h * 0.06:
            adjacency.append(("top", abs(Y2 - y1), _coverage(lines, "h", y1, X1, X2, h, w)))
        if X1 >= x2 - w * 0.06:
            adjacency.append(("right", abs(X1 - x2), _coverage(lines, "v", x2, Y1, Y2, h, w)))
        if X2 <= x1 + w * 0.06:
            adjacency.append(("left", abs(X2 - x1), _coverage(lines, "v", x1, Y1, Y2, h, w)))
        if not adjacency:
            continue
        side, distance, interface = max(adjacency, key=lambda item: item[2])
        if interface < 0.50:
            continue

        secondary.append(
            {
                "area_ratio": round(area_ratio, 3),
                "rectangularity": round(rectangularity, 3),
                "solidity": round(solidity, 3),
                "bbox": [round(x / w, 3), round(y / h, 3), round(bw / w, 3), round(bh / h, 3)],
                "adjacent_edge": side,
                "interface_edge_coverage": round(interface, 3),
                "interface_distance_px": round(float(distance), 1),
            }
        )

    if secondary:
        best_secondary = max(secondary, key=lambda x: (x["interface_edge_coverage"], x["area_ratio"]))
        result.update(
            {
                "trigger": True,
                "secondary_candidate": best_secondary,
                "reason": "rectangular_secondary_pcb_plane_across_physical_board_edge",
            }
        )
    else:
        result["reason"] = "no_external_rectangular_plane_with_supported_interface"

    return result
