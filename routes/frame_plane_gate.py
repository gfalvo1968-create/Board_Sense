"""SPIKE Secondary Board Plane Gate v0.3.

Conservative physical-plane detectors for cases that can defeat a merged green-PCB
silhouette:
1. a smaller PCB lies under/over a larger PCB; or
2. two distinct PCBs touch edge-to-edge so the stronger morphology merges them.

The overlap detector requires a large rectangular PCB core, a substantial board-like
region outside it, and a supported physical interface edge.

The edge-touch detector is intentionally color-independent. It inspects lightly closed
external edge contours before the stronger silhouette merge and only fires when two
substantial compact planes sit directly beside one another with little box overlap and
meaningful edge alignment. This keeps irregular single motherboards from being split
merely because they have wings, necks, notches, or large internal components.
"""
from __future__ import annotations

import itertools
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


def _adjacent_edge_planes(image):
    """Find two substantial color-independent PCB-like edge bodies touching side-by-side.

    A light 3x3 close preserves the physical seam that the stronger board-surface
    morphology can erase. We only accept pairs with small mutual box overlap and
    substantial alignment along the orthogonal edge, which rejects nested internal
    rectangles on one board.
    """
    h, w = image.shape[:2]
    image_area = float(max(1, h * w))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 45, 135)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        area_ratio = area / image_area
        if area_ratio < 0.012:
            continue
        x, y, bw, bh = cv2.boundingRect(contour)
        if max(bw / max(1, w), bh / max(1, h)) < 0.12:
            continue
        rect = cv2.minAreaRect(contour)
        rw, rh = rect[1]
        rectangularity = area / max(float(rw) * float(rh), 1.0)
        hull = cv2.convexHull(contour)
        solidity = area / max(float(cv2.contourArea(hull)), 1.0)
        if rectangularity < 0.25 or solidity < 0.35:
            continue
        candidates.append(
            {
                "area_ratio": round(area_ratio, 3),
                "bbox_px": [int(x), int(y), int(bw), int(bh)],
                "bbox": [round(x / w, 3), round(y / h, 3), round(bw / w, 3), round(bh / h, 3)],
                "rectangularity": round(rectangularity, 3),
                "solidity": round(solidity, 3),
            }
        )

    pairs = []
    for first, second in itertools.combinations(candidates, 2):
        ax, ay, aw, ah = first["bbox_px"]
        bx, by, bw, bh = second["bbox_px"]
        ax2, ay2, bx2, by2 = ax + aw, ay + ah, bx + bw, by + bh

        ix = max(0, min(ax2, bx2) - max(ax, bx))
        iy = max(0, min(ay2, by2) - max(ay, by))
        inter = float(ix * iy)
        min_box_area = float(max(1, min(aw * ah, bw * bh)))
        overlap_of_smaller = inter / min_box_area

        gap_x = max(0, max(ax, bx) - min(ax2, bx2))
        gap_y = max(0, max(ay, by) - min(ay2, by2))
        vertical_alignment = iy / max(1.0, float(min(ah, bh)))
        horizontal_alignment = ix / max(1.0, float(min(aw, bw)))

        side_by_side = gap_x <= w * 0.025 and vertical_alignment >= 0.25
        top_bottom = gap_y <= h * 0.025 and horizontal_alignment >= 0.25
        separate_planes = overlap_of_smaller <= 0.22
        if not (separate_planes and (side_by_side or top_bottom)):
            continue

        axis = "vertical_interface" if side_by_side else "horizontal_interface"
        pairs.append(
            {
                "first": {k: v for k, v in first.items() if k != "bbox_px"},
                "second": {k: v for k, v in second.items() if k != "bbox_px"},
                "interface_axis": axis,
                "overlap_of_smaller": round(overlap_of_smaller, 3),
                "gap_ratio": round((gap_x / w) if side_by_side else (gap_y / h), 4),
                "orthogonal_alignment": round(vertical_alignment if side_by_side else horizontal_alignment, 3),
                "score": round(
                    min(1.0, (first["area_ratio"] + second["area_ratio"]) * 5.0)
                    * min(1.0, vertical_alignment if side_by_side else horizontal_alignment),
                    3,
                ),
            }
        )

    if not pairs:
        return {"trigger": False, "candidate_count": len(candidates), "reason": "no_distinct_adjacent_edge_planes"}

    best = max(pairs, key=lambda item: (item["orthogonal_alignment"], item["score"]))
    return {
        "trigger": True,
        "candidate_count": len(candidates),
        "pair": best,
        "reason": "two_distinct_pcb_edge_planes_touch_or_nearly_touch",
    }


def inspect_secondary_board_plane(image, board_mask):
    h, w = image.shape[:2]
    image_area = float(max(1, h * w))
    result = {
        "version": "SPIKE Secondary Board Plane Gate v0.3",
        "trigger": False,
        "primary_core": None,
        "secondary_candidate": None,
    }

    adjacent = _adjacent_edge_planes(image)
    result["adjacent_edge_plane_check"] = adjacent
    if adjacent.get("trigger"):
        result.update(
            {
                "trigger": True,
                "reason": "distinct_adjacent_pcb_edge_planes",
                "secondary_candidate": adjacent.get("pair"),
            }
        )
        return result

    lines = _boundary_lines(image, board_mask)
    if len(lines) < 4:
        result["reason"] = "insufficient_supported_edges"
        return result

    hs = _clusters(lines, "h", h, w)
    vs = _clusters(lines, "v", w, h)
    cores = []

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
                    if min(cov) < 0.30:
                        continue
                    score = ratio * fill * (0.5 + 0.5 * (sum(cov) / 4.0))
                    if score < 0.18:
                        continue
                    cores.append(
                        {
                            "box": [round(x1 / w, 3), round(y1 / h, 3), round(x2 / w, 3), round(y2 / h, 3)],
                            "area_ratio": round(ratio, 3),
                            "board_fill": round(fill, 3),
                            "edge_coverage": [round(x, 3) for x in cov],
                            "score": round(score, 3),
                            "_px": (x1, y1, x2, y2),
                        }
                    )

    if not cores:
        result["reason"] = "no_high_confidence_rectangular_core"
        return result

    # Prefer the cleanest rectangular plane, not merely the largest union.
    # This keeps a smaller overlapping PCB from being swallowed into one giant
    # high-area rectangle when the main board itself has a crisper four-edge core.
    cores.sort(
        key=lambda item: (
            item["board_fill"],
            min(item["edge_coverage"]),
            item["score"],
        ),
        reverse=True,
    )

    def secondary_for_core(core):
        x1, y1, x2, y2 = core["_px"]
        outside = (board_mask > 0).astype(np.uint8) * 255
        # The Hough-supported core usually lands a few pixels inside the actual
        # PCB perimeter. Expand the erased core slightly so that leftover edge
        # pixels do not form a giant ring that reconnects an external second PCB.
        pad = max(4, int(min(h, w) * 0.025))
        outside[
            max(0, int(y1) - pad):min(h, int(y2) + pad),
            max(0, int(x1) - pad):min(w, int(x2) + pad),
        ] = 0
        contours, _ = cv2.findContours(outside, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        found = []

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

            found.append(
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
        return found

    # A single giant rectangle can swallow the smaller PCB into its union. Check
    # several strong cores, not just the largest, and prefer the pairing with the
    # clearest physical interface edge.
    reviewed = []
    for core in cores[:40]:
        secondaries = secondary_for_core(core)
        for secondary in secondaries:
            reviewed.append((core, secondary))

    if reviewed:
        core, secondary = max(
            reviewed,
            key=lambda pair: (
                pair[1]["interface_edge_coverage"],
                pair[1]["area_ratio"],
                pair[0]["score"],
            ),
        )
        result.update(
            {
                "trigger": True,
                "primary_core": {k: v for k, v in core.items() if k != "_px"},
                "secondary_candidate": secondary,
                "reason": "rectangular_secondary_pcb_plane_across_physical_board_edge",
            }
        )
        return result

    result["primary_core"] = {k: v for k, v in cores[0].items() if k != "_px"}
    result["reason"] = "no_external_rectangular_plane_with_supported_interface"
    return result
