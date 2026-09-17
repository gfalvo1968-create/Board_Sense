"""SPIKE Local Zoom + Visual-Evidence Independence Guard v0.1.

Two rules live here:
1. SPIKE may digitally crop/zoom an uploaded photo to inspect a suspicious region.
   A digital zoom is a tool view, never a new independent photograph.
2. A user-supplied crop/zoom or near-duplicate of another uploaded photo must not
   multiply identity confidence as if it were fresh physical evidence.

This module never manufactures SAME_BOARD identity and never clears hard
multi-board evidence. It only describes local pixels and visual overlap.
"""
from __future__ import annotations

import cv2
import numpy as np


def _load_gray(path: str, max_side: int = 1600):
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None, 1.0
    h, w = image.shape[:2]
    scale = min(1.0, max_side / float(max(h, w)))
    if scale < 1.0:
        image = cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))))
    return image, scale


def _hull_coverage(points, shape) -> float:
    if points is None or len(points) < 3:
        return 0.0
    pts = np.float32(points).reshape(-1, 1, 2)
    hull = cv2.convexHull(pts)
    area = float(cv2.contourArea(hull))
    h, w = shape[:2]
    return area / max(1.0, float(w * h))


def compare_visual_source(path_a: str, path_b: str) -> dict:
    """Detect a crop/zoom/near-duplicate relationship using local geometry.

    The classification intentionally says *non-independent visual evidence* rather
    than proving that the files came from the same camera exposure. Separately
    captured nearly identical views may also be grouped, which is conservative for
    identity confidence and avoids duplicate-evidence inflation.
    """
    a, _ = _load_gray(path_a)
    b, _ = _load_gray(path_b)
    out = {
        "relation": "independent_or_unresolved",
        "non_independent": False,
        "method": "ORB + RANSAC homography overlap",
        "good_matches": 0,
        "homography_inliers": 0,
        "homography_inlier_ratio": 0.0,
        "coverage_a": 0.0,
        "coverage_b": 0.0,
    }
    if a is None or b is None:
        out["reason"] = "image_unreadable"
        return out

    orb = cv2.ORB_create(nfeatures=3200, fastThreshold=7, edgeThreshold=15)
    kp1, des1 = orb.detectAndCompute(a, None)
    kp2, des2 = orb.detectAndCompute(b, None)
    if des1 is None or des2 is None or len(kp1) < 20 or len(kp2) < 20:
        out["reason"] = "insufficient_local_features"
        return out

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(des1, des2, k=2)
    good = [m for pair in pairs if len(pair) == 2 for m, n in [pair] if m.distance < 0.74 * n.distance]
    out["good_matches"] = len(good)
    if len(good) < 20:
        out["reason"] = "too_few_feature_matches"
        return out

    src = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    try:
        _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.5)
    except cv2.error:
        mask = None
    if mask is None:
        out["reason"] = "homography_unresolved"
        return out

    keep = mask.ravel().astype(bool)
    inliers = int(keep.sum())
    ratio = inliers / max(1, len(good))
    pts_a = [kp1[m.queryIdx].pt for m, ok in zip(good, keep) if ok]
    pts_b = [kp2[m.trainIdx].pt for m, ok in zip(good, keep) if ok]
    cov_a = _hull_coverage(pts_a, a.shape)
    cov_b = _hull_coverage(pts_b, b.shape)
    out.update({
        "homography_inliers": inliers,
        "homography_inlier_ratio": round(ratio, 3),
        "coverage_a": round(cov_a, 3),
        "coverage_b": round(cov_b, 3),
    })

    # Crop/zoom evidence normally covers a substantial part of one image and a
    # smaller but still meaningful part of the source image. Near-duplicate full
    # views cover substantial regions in both. Either way, they should not count
    # as two independent identity witnesses.
    non_independent = (
        inliers >= 18
        and ratio >= 0.50
        and max(cov_a, cov_b) >= 0.28
        and min(cov_a, cov_b) >= 0.055
    )
    out["non_independent"] = bool(non_independent)
    out["relation"] = "same_visual_source_or_near_duplicate" if non_independent else "independent_or_unresolved"
    out["reason"] = (
        "strong_local_geometry_overlap_across_the_views"
        if non_independent
        else "overlap_not_strong_enough_to_group_the_views"
    )
    return out


def annotate_visual_independence(results: list[dict], image_paths: list[str]) -> dict:
    """Group uploaded views that are crops/zooms/near-duplicates of one another."""
    n = min(len(results or []), len(image_paths or []))
    if n == 0:
        return {"groups": [], "independent_group_count": 0, "pair_checks": []}

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    checks = []
    for i in range(n):
        for j in range(i + 1, n):
            rel = compare_visual_source(image_paths[i], image_paths[j])
            checks.append({"views": [i + 1, j + 1], **rel})
            if rel.get("non_independent"):
                union(i, j)

    group_map = {}
    next_group = 1
    groups = []
    for i in range(n):
        root = find(i)
        if root not in group_map:
            group_map[root] = next_group
            next_group += 1
        group = group_map[root]
        groups.append(group)
        results[i]["visual_evidence_group"] = group
        results[i]["visual_evidence_independent"] = (i == min(k for k in range(n) if find(k) == root))

    packet = {
        "version": "SPIKE Visual Evidence Independence Guard v0.1",
        "groups": groups,
        "independent_group_count": len(set(groups)),
        "pair_checks": checks,
        "rule": "A crop, digital zoom, or near-duplicate may help inspection but cannot count as a second independent identity witness.",
    }
    for result in results[:n]:
        result["visual_evidence_independence"] = {
            "version": packet["version"],
            "group": result.get("visual_evidence_group"),
            "independent_group_count": packet["independent_group_count"],
            "rule": packet["rule"],
        }
    return packet


def inspect_identity_zoom(image_path: str, axis: str, cut, band_fraction: float = 0.22) -> dict:
    """Inspect a bottleneck region by cropping existing pixels around the cut.

    This is deliberately advisory. Upscaling cannot create missing detail, so the
    output may tell SPIKE whether the existing pixels are worth inspecting but may
    never be treated as a fresh photograph or an identity override.
    """
    image = cv2.imread(image_path)
    out = {
        "status": "unavailable",
        "method": "local digital crop around identity bottleneck",
        "axis": axis,
        "cut": cut,
        "independent_evidence": False,
        "identity_override": False,
    }
    if image is None or axis not in {"x", "y"} or cut is None:
        out["reason"] = "missing_image_or_target"
        return out

    h, w = image.shape[:2]
    span = w if axis == "x" else h
    c = int(round(float(cut)))
    c = max(0, min(span - 1, c))
    half = max(40, int(span * max(0.08, min(0.35, band_fraction))))
    if axis == "x":
        x1, x2 = max(0, c - half), min(w, c + half)
        y1, y2 = 0, h
    else:
        y1, y2 = max(0, c - half), min(h, c + half)
        x1, x2 = 0, w
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        out["reason"] = "empty_crop"
        return out

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    edges = cv2.Canny(gray, 45, 135)
    edge_density = float(np.count_nonzero(edges)) / max(1.0, float(edges.size))
    corners = cv2.goodFeaturesToTrack(gray, maxCorners=250, qualityLevel=0.025, minDistance=8)
    feature_count = 0 if corners is None else len(corners)
    usable = crop.shape[0] >= 120 and crop.shape[1] >= 120 and sharpness >= 35 and feature_count >= 12
    out.update({
        "status": "inspectable_existing_pixels" if usable else "new_photo_still_needed",
        "crop_box": [int(x1), int(y1), int(x2), int(y2)],
        "crop_size": [int(crop.shape[1]), int(crop.shape[0])],
        "sharpness": round(sharpness, 2),
        "edge_density": round(edge_density, 4),
        "feature_count": int(feature_count),
        "reason": "existing_pixels_support_local_review" if usable else "digital_zoom_cannot_create_the_missing_detail",
        "rule": "Digital zoom focuses existing pixels only. It is never independent evidence and cannot clear a hard multi-board contradiction by itself.",
    })
    return out
