"""Non-authoritative photo-overlap diagnostics for staging multi-photo PCB cases.

Matching visual features can support review but cannot prove that two images
depict the same physical item: two mass-produced boards may share a layout,
and opposite PCB faces may have no matching visual features. This module
NEVER authorizes combined grades, payout, or automatic case reconciliation.
"""
from itertools import combinations
from hashlib import sha256
import cv2
import numpy as np


def _features(path):
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    h, w = image.shape[:2]
    if min(w, h) < 100:
        return None
    scale = min(1.0, 1050.0 / max(w, h))
    if scale < 1:
        image = cv2.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    detector = cv2.ORB_create(nfeatures=1400, scaleFactor=1.2, nlevels=8, fastThreshold=12)
    keypoints, descriptors = detector.detectAndCompute(image, None)
    if descriptors is None or len(keypoints) < 30:
        return None
    return keypoints, descriptors, (image.shape[1], image.shape[0])


def _pair(a, b):
    if a is None or b is None:
        return {"status": "insufficient_image_features", "independent_physical_identity_verified": False}
    keypoints_a, desc_a, (wa, ha) = a
    keypoints_b, desc_b, (wb, hb) = b
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    forward = matcher.knnMatch(desc_a, desc_b, k=2)
    reverse = matcher.knnMatch(desc_b, desc_a, k=2)

    def good(matches):
        return {m.queryIdx: m.trainIdx for pair in matches if len(pair) == 2
                for m, n in [pair] if m.distance < 0.70 * n.distance}

    f, r = good(forward), good(reverse)
    mutual = [(i, j) for i, j in f.items() if r.get(j) == i]
    if len(mutual) < 20:
        return {"status": "inconclusive", "mutual_matches": len(mutual),
                "independent_physical_identity_verified": False}
    pa = np.float32([keypoints_a[i].pt for i, j in mutual])
    pb = np.float32([keypoints_b[j].pt for i, j in mutual])
    hmat, inliers = cv2.findHomography(pa.reshape(-1, 1, 2), pb.reshape(-1, 1, 2),
                                       cv2.RANSAC, 3.0, maxIters=2000, confidence=0.995)
    if hmat is None or inliers is None:
        return {"status": "inconclusive", "mutual_matches": len(mutual),
                "independent_physical_identity_verified": False}
    mask = inliers.ravel().astype(bool)
    n = int(mask.sum())
    fraction = n / max(1, len(mutual))
    points = pa[mask]
    spread_x = float(np.ptp(points[:, 0])) / wa if n else 0
    spread_y = float(np.ptp(points[:, 1])) / ha if n else 0
    # Reject dense clusters of repeated pins/markings; require broad image
    # coverage and geometrically consistent feature correspondences.
    candidate = n >= 26 and fraction >= 0.68 and spread_x >= 0.18 and spread_y >= 0.16
    return {
        "status": "overlapping_view_candidate" if candidate else "inconclusive",
        "mutual_matches": len(mutual),
        "geometric_inliers": n,
        "inlier_fraction": round(fraction, 3),
        "inlier_spread": [round(spread_x, 3), round(spread_y, 3)],
        "independent_physical_identity_verified": False,
    }


def _file_digest(path):
    """Private exact-upload detector; no digest leaves this module."""
    digest = sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.digest()


def examine_photo_overlap(paths):
    """Return optional per-pair diagnostic evidence, never proof of identity.

    The input photographs are processed in memory and are not copied or
    retained by this module. No image contents, filenames, or hashes appear
    in the diagnostic response.
    """
    try:
        sampled_paths = paths[:6]
        digests = [_file_digest(path) for path in sampled_paths]
        # Avoid manufacturing hundreds of impressive "landmarks" from an
        # identical upload: identical file bytes are not independent evidence.
        features = [_features(path) for path in sampled_paths]
        pairs = []
        for i, j in combinations(range(len(features)), 2):
            if digests[i] == digests[j]:
                pairs.append({
                    "views": [i + 1, j + 1],
                    "status": "duplicate_upload",
                    "exact_duplicate": True,
                    "independent_physical_identity_verified": False,
                })
            else:
                pairs.append({"views": [i + 1, j + 1], **_pair(features[i], features[j])})
        duplicates = [p["views"] for p in pairs if p.get("exact_duplicate")]
        return {
            "status": "duplicate_uploads_detected" if duplicates else "diagnostic_only",
            "duplicate_photo_pairs": duplicates,
            "pairs": pairs,
            "independent_physical_identity_verified": False,
            "interpretation": (
                "Exact duplicate uploads are not independent evidence. Visual correspondences cannot prove physical identity: boards of the same model "
                "may match, and opposite faces may share no visual landmarks. Never merge grades or "
                "economics based on these metrics."
            ),
        }
    except (cv2.error, ValueError, TypeError):
        return {
            "status": "unavailable", "pairs": [],
            "independent_physical_identity_verified": False,
            "interpretation": "Diagnostic unavailable; no identity or grading inference permitted.",
        }
