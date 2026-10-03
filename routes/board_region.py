"""Conservative PCB surface support for component and connector geometry.

The photo boundary is never evidence of a PCB perimeter. An uncertain outline
returns an empty mask rather than admitting the whole textured background.
"""
import cv2
import numpy as np


def board_region_mask(image):
    h, w = image.shape[:2]
    area = max(1, h * w)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Include warm-lit green solder mask. Saturation excludes most gray cloth;
    # color locates a surface only and supplies no board identity or value.
    surface = cv2.inRange(hsv, np.array([18, 70, 22]), np.array([105, 255, 255]))
    k = max(3, (min(h, w) // 85) | 1)
    surface = cv2.morphologyEx(surface, cv2.MORPH_CLOSE,
                               np.ones((k, k), np.uint8), iterations=2)
    contours, _ = cv2.findContours(surface, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for c in contours:
        a = cv2.contourArea(c)
        rw, rh = cv2.minAreaRect(c)[1]
        if .08 <= a / area <= .95 and a / max(1, rw * rh) >= .55:
            candidates.append(c)
    if candidates:
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(mask, [max(candidates, key=cv2.contourArea)], -1, 255, -1)
        return mask

    # Non-green boards can still have a clear outline against a plain surface.
    # A variable border (folds, shadows, weave) cannot support this fallback.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bh, bw = max(2, h // 20), max(2, w // 20)
    border = np.concatenate([gray[:bh, :].ravel(), gray[-bh:, :].ravel(),
                             gray[:, :bw].ravel(), gray[:, -bw:].ravel()])
    if np.std(border) > 24:
        return np.zeros((h, w), dtype=np.uint8)
    diff = cv2.absdiff(gray, np.full_like(gray, int(np.median(border))))
    _, foreground = cv2.threshold(diff, 22, 255, cv2.THRESH_BINARY)
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE,
                                  np.ones((k, k), np.uint8), iterations=2)
    contours, _ = cv2.findContours(foreground, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = [c for c in contours if .08 <= cv2.contourArea(c) / area <= .95]
    mask = np.zeros((h, w), dtype=np.uint8)
    if candidates:
        cv2.drawContours(mask, [max(candidates, key=cv2.contourArea)], -1, 255, -1)
    return mask


def region_on_board(mask, region, minimum_coverage=.65):
    h, w = mask.shape[:2]
    x, y = int(region.get('x', 0)), int(region.get('y', 0))
    rw, rh = int(region.get('w', 0)), int(region.get('h', 0))
    if rw <= 0 or rh <= 0 or x < 0 or y < 0 or x + rw > w or y + rh > h:
        return False
    if not mask[y + rh // 2, x + rw // 2]:
        return False
    return cv2.countNonZero(mask[y:y + rh, x:x + rw]) / (rw * rh) >= minimum_coverage
