"""SPIKE multi-board split helper v0.2.

When the single-frame identity gate proves that several PCB bodies share one photo,
this helper tries to separate cleanly visible bodies into independent crops. It does
NOT merge identities or values. Ambiguous overlap remains a clarification problem.

Core rule: stop the merge, not the investigation.
"""
from pathlib import Path
import cv2
import numpy as np


def _filled_edge_foreground(image):
    h, w = image.shape[:2]
    area = float(max(1, h * w))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 40, 120)
    mask = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    kept = 0
    for contour in contours:
        ratio = float(cv2.contourArea(contour)) / area
        if 0.008 <= ratio <= 0.60:
            cv2.drawContours(filled, [contour], -1, 255, -1)
            kept += 1
    return filled, kept


def _seed_markers(foreground):
    h, w = foreground.shape[:2]
    area = float(max(1, h * w))
    distance = cv2.distanceTransform(foreground, cv2.DIST_L2, 5)
    maximum = float(distance.max())
    if maximum <= 0:
        return None, []
    sure = (distance > maximum * 0.25).astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(sure, 8)
    raw = []
    for label in range(1, count):
        seed_area = int(stats[label, cv2.CC_STAT_AREA])
        raw.append(
            {
                "label": label,
                "area": seed_area,
                "area_ratio": seed_area / area,
                "centroid": (float(centroids[label][0]), float(centroids[label][1])),
            }
        )
    if not raw:
        return None, []
    largest = max(x["area_ratio"] for x in raw)
    floor = max(0.0025, largest * 0.08)
    kept = [x for x in raw if x["area_ratio"] >= floor]
    if len(kept) > 6:
        kept = sorted(kept, key=lambda x: x["area"], reverse=True)[:6]

    markers = np.ones_like(labels, dtype=np.int32)
    markers[foreground > 0] = 0
    for new_label, seed in enumerate(kept, 2):
        markers[labels == seed["label"]] = new_label
        seed["watershed_label"] = new_label
    return markers, kept


def split_board_regions(image_path, max_boards=4):
    """Return isolated board-region metadata and masks for a hard multi-board frame."""
    image = cv2.imread(str(image_path))
    if image is None:
        return {
            "mode": "SPIKE Multi-Board Split v0.1",
            "status": "FRAME_UNREADABLE",
            "board_count": 0,
            "regions": [],
        }
    h, w = image.shape[:2]
    image_area = float(max(1, h * w))
    foreground, contour_count = _filled_edge_foreground(image)
    markers, seeds = _seed_markers(foreground)
    if markers is None or len(seeds) < 2:
        return {
            "mode": "SPIKE Multi-Board Split v0.1",
            "status": "SEPARATION_NOT_PROVEN",
            "board_count": 0,
            "regions": [],
            "foreground_components": contour_count,
            "seed_count": len(seeds),
            "message": "Multiple boards were detected, but SPIKE could not isolate at least two clean board bodies from this frame.",
        }

    watershed = cv2.watershed(image.copy(), markers)
    regions = []
    largest_area = 0
    raw_regions = []
    for seed in seeds:
        label = seed["watershed_label"]
        ys, xs = np.where(watershed == label)
        if len(xs) == 0:
            continue
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        pixel_area = int(len(xs))
        ratio = pixel_area / image_area
        if ratio < 0.008:
            continue
        raw_regions.append(
            {
                "label": int(label),
                "x": x0,
                "y": y0,
                "w": x1 - x0 + 1,
                "h": y1 - y0 + 1,
                "pixel_area": pixel_area,
                "area_ratio": ratio,
                "cx": (x0 + x1) / 2.0,
                "cy": (y0 + y1) / 2.0,
            }
        )
        largest_area = max(largest_area, pixel_area)

    if largest_area <= 0:
        return {
            "mode": "SPIKE Multi-Board Split v0.1",
            "status": "SEPARATION_NOT_PROVEN",
            "board_count": 0,
            "regions": [],
        }

    raw_regions = [r for r in raw_regions if r["pixel_area"] >= largest_area * 0.15]
    raw_regions.sort(key=lambda r: (r["cx"], r["cy"]))
    raw_regions = raw_regions[:max_boards]

    for index, region in enumerate(raw_regions, 1):
        mask = (watershed == region["label"]).astype(np.uint8) * 255
        pad = max(12, int(min(h, w) * 0.02))
        x0 = max(0, region["x"] - pad)
        y0 = max(0, region["y"] - pad)
        x1 = min(w, region["x"] + region["w"] + pad)
        y1 = min(h, region["y"] + region["h"] + pad)
        regions.append(
            {
                "board_index": index,
                "bbox": {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0},
                "area_ratio": round(region["area_ratio"], 4),
                "watershed_label": region["label"],
                "_mask": mask,
            }
        )

    status = "SEPARATE_BOARD_REGIONS_FOUND" if len(regions) >= 2 else "SEPARATION_NOT_PROVEN"
    return {
        "mode": "SPIKE Multi-Board Split v0.1",
        "status": status,
        "board_count": len(regions) if status == "SEPARATE_BOARD_REGIONS_FOUND" else 0,
        "regions": regions if status == "SEPARATE_BOARD_REGIONS_FOUND" else [],
        "foreground_components": contour_count,
        "seed_count": len(seeds),
        "rule": "Separate cleanly visible PCB bodies for independent analysis. Never merge their identity, grade, or economics.",
    }


def save_isolated_board_crops(image_path, output_dir, max_boards=4):
    """Write neutral-background crops for each cleanly separated board body."""
    image = cv2.imread(str(image_path))
    if image is None:
        return {"status": "FRAME_UNREADABLE", "board_count": 0, "crops": []}
    split = split_board_regions(image_path, max_boards=max_boards)
    if split.get("status") != "SEPARATE_BOARD_REGIONS_FOUND":
        return {**split, "crops": []}

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    crops = []
    stem = Path(image_path).stem
    for region in split["regions"]:
        box = region["bbox"]
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        mask = region.pop("_mask")
        crop = image[y:y+h, x:x+w].copy()
        crop_mask = mask[y:y+h, x:x+w]
        neutral = np.full_like(crop, 28)
        isolated = np.where(crop_mask[:, :, None] > 0, crop, neutral)
        filename = f"{stem}_split_board_{region['board_index']}.jpg"
        path = output_dir / filename
        cv2.imwrite(str(path), isolated, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
        crops.append(
            {
                **region,
                "crop_path": str(path),
                "crop_filename": filename,
            }
        )

    split["crops"] = crops
    split["regions"] = [{k:v for k,v in r.items() if not k.startswith("_")} for r in split["regions"]]
    return split


def choose_best_multi_board_split(image_paths, output_dir, max_boards=4):
    """Scan every uploaded view once a case is known to contain multiple boards.

    Important: the best separable view may not be the same view that triggered the
    hard multi-board identity gate. Once the case is proven multi-board, all views
    are eligible as evidence for physical separation.
    """
    best = None
    attempts = []
    for view_number, image_path in enumerate(image_paths or [], 1):
        split = save_isolated_board_crops(
            image_path,
            Path(output_dir) / f"view_{view_number}",
            max_boards=max_boards,
        )
        attempts.append({
            "view_number": view_number,
            "status": split.get("status"),
            "board_count": split.get("board_count", 0),
            "seed_count": split.get("seed_count"),
            "foreground_components": split.get("foreground_components"),
        })
        if split.get("status") != "SEPARATE_BOARD_REGIONS_FOUND":
            continue
        candidate = {
            "view_number": view_number,
            "image_path": str(image_path),
            "split": split,
        }
        if best is None:
            best = candidate
            continue
        candidate_count = int(split.get("board_count", 0) or 0)
        best_count = int(best["split"].get("board_count", 0) or 0)
        candidate_total = sum(float(x.get("area_ratio", 0) or 0) for x in split.get("regions", []))
        best_total = sum(float(x.get("area_ratio", 0) or 0) for x in best["split"].get("regions", []))
        if candidate_count > best_count or (candidate_count == best_count and candidate_total > best_total):
            best = candidate

    return {
        "mode": "SPIKE Multi-Board View Selector v0.1",
        "status": "BEST_SPLIT_FOUND" if best else "NO_CLEAN_SPLIT_FOUND",
        "best": best,
        "attempts": attempts,
        "rule": "After multi-board presence is proven, inspect every uploaded view for the cleanest independent board separation.",
    }
