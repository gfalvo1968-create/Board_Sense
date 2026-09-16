"""SPIKE Identity Clarification Matcher v0.1.

Uses local feature overlap to decide whether a requested close-up actually spans the
same narrow PCB neck/bridge that triggered a bottleneck-only frame warning.

This is deliberately conservative:
- it never clears independent two-region or multiscale split evidence;
- it only evaluates bottleneck-only ambiguity;
- the close-up must match the flagged SAME SIDE and contain matched features on
  both sides of the reported bottleneck cut.
"""
from __future__ import annotations

import cv2
import numpy as np


def _frame_gate(result: dict) -> dict:
    bp = result.get("board_blueprint") or {}
    return bp.get("frame_identity_gate") or result.get("frame_identity_gate") or {}


def _load_gray(path: str, max_side: int = 1600):
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None, 1.0
    h, w = image.shape[:2]
    scale = min(1.0, max_side / float(max(h, w)))
    if scale < 1.0:
        image = cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))))
    return image, scale


def _match_targeted_continuity(flagged_path: str, candidate_path: str, bottleneck: dict) -> dict:
    a, scale_a = _load_gray(flagged_path)
    b, _ = _load_gray(candidate_path)
    base = {
        "matched": False,
        "method": "ORB targeted continuity overlap",
        "good_matches": 0,
        "target_band_matches": 0,
        "matches_side_a": 0,
        "matches_side_b": 0,
        "homography_inliers": 0,
        "homography_inlier_ratio": 0.0,
    }
    if a is None or b is None:
        base["reason"] = "image_unreadable"
        return base

    orb = cv2.ORB_create(nfeatures=3500, fastThreshold=7, edgeThreshold=15)
    kp1, des1 = orb.detectAndCompute(a, None)
    kp2, des2 = orb.detectAndCompute(b, None)
    if des1 is None or des2 is None or len(kp1) < 20 or len(kp2) < 20:
        base["reason"] = "insufficient_local_features"
        return base

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(des1, des2, k=2)
    good = [m for m, n in pairs if m.distance < 0.74 * n.distance]
    base["good_matches"] = len(good)
    if len(good) < 18:
        base["reason"] = "too_few_feature_matches"
        return base

    axis = bottleneck.get("axis")
    raw_cut = bottleneck.get("cut")
    if axis not in {"x", "y"} or raw_cut is None:
        base["reason"] = "missing_bottleneck_location"
        return base

    cut = float(raw_cut) * scale_a
    span = float(a.shape[1] if axis == "x" else a.shape[0])
    band = max(45.0, span * 0.20)

    target = []
    side_a = 0
    side_b = 0
    for m in good:
        x, y = kp1[m.queryIdx].pt
        coord = x if axis == "x" else y
        if abs(coord - cut) <= band:
            target.append(m)
            if coord < cut:
                side_a += 1
            else:
                side_b += 1

    base["target_band_matches"] = len(target)
    base["matches_side_a"] = side_a
    base["matches_side_b"] = side_b

    inliers = 0
    inlier_ratio = 0.0
    if len(good) >= 8:
        src = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        try:
            _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
            if mask is not None:
                inliers = int(mask.ravel().sum())
                inlier_ratio = inliers / max(1, len(good))
        except cv2.error:
            pass
    base["homography_inliers"] = inliers
    base["homography_inlier_ratio"] = round(inlier_ratio, 3)

    # The candidate must visibly overlap the reported neck and carry enough
    # same-side geometry on BOTH sides of that neck. Homography support helps
    # reject lookalike circuit texture from unrelated boards.
    matched = (
        len(good) >= 24
        and len(target) >= 12
        and side_a >= 4
        and side_b >= 4
        and inliers >= 10
        and inlier_ratio >= 0.28
    )
    base["matched"] = bool(matched)
    base["reason"] = (
        "same_side_closeup_spans_reported_neck"
        if matched
        else "closeup_does_not_yet_span_and_match_both_sides_of_neck"
    )
    return base


def apply_identity_clarifications(results: list[dict], image_paths: list[str]) -> list[dict]:
    """Attach clarification evidence to bottleneck-only flagged views.

    Results are mutated in place and also returned for convenience.
    """
    if not results or len(results) != len(image_paths):
        return results

    for i, result in enumerate(results):
        fg = _frame_gate(result)
        if not fg.get("block_analysis"):
            continue
        m = fg.get("metrics") or {}
        if not (
            m.get("bottleneck_split_trigger")
            and not m.get("base_two_region_trigger")
            and not m.get("multiscale_split_trigger")
        ):
            continue

        bottleneck = m.get("bottleneck_split_metrics") or {}
        candidates = []
        for j, candidate in enumerate(results):
            if i == j:
                continue
            cfg = _frame_gate(candidate)
            # A clarification photo cannot itself be a hard suspicious frame.
            if cfg.get("block_analysis"):
                continue
            matched = _match_targeted_continuity(image_paths[i], image_paths[j], bottleneck)
            matched["candidate_view"] = j + 1
            candidates.append(matched)

        resolved = next((c for c in candidates if c.get("matched")), None)
        result["identity_clarification_evidence"] = {
            "version": "SPIKE Identity Clarification Matcher v0.1",
            "status": "resolved" if resolved else "still_needed",
            "resolved": bool(resolved),
            "flagged_view": i + 1,
            "matched_candidate_view": resolved.get("candidate_view") if resolved else None,
            "candidate_checks": candidates,
            "rule": "A bottleneck-only warning may be cleared only by a same-side close-up that locally matches and spans both sides of the reported neck. Hard multi-board evidence is never overridden.",
        }

    return results
