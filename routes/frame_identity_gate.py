"""SPIKE Single-Frame Board Identity Gate v0.5.

Blocks a single uploaded photograph when strong physical evidence says more than
one PCB is present. PCB confirmation and board identity remain separate gates.
Color is only used to find candidate PCB regions; geometry supplies the block.

v0.5 adds a bottleneck split pass for the failure mode seen in Chaos testing:
two physical boards can touch or overlap enough to look like one green blob, but
the merged silhouette still contains a narrow neck between two substantial PCB
bodies. The gate detects that neck before reconciliation or blueprinting.
"""
import cv2
import numpy as np


def _component_stats(mask, image_area, min_ratio=0.025):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in contours:
        a = float(cv2.contourArea(c))
        if a < image_area * min_ratio:
            continue
        x, y, w, h = cv2.boundingRect(c)
        rect = cv2.minAreaRect(c)
        rw, rh = rect[1]
        rw, rh = max(float(rw), 1.0), max(float(rh), 1.0)
        rectangularity = a / max(rw * rh, 1.0)
        out.append({
            "area": a,
            "ratio": a / image_area,
            "bbox": (x, y, w, h),
            "rectangularity": rectangularity,
            "cx": x + w / 2.0,
            "cy": y + h / 2.0,
        })
    out.sort(key=lambda d: d["area"], reverse=True)
    return out


def _two_substantial_regions(regions, image_area, image_w, image_h):
    if len(regions) < 2:
        return False, None
    a, b = regions[0], regions[1]
    substantial = (
        a["ratio"] >= 0.10
        and b["ratio"] >= 0.045
        and (a["ratio"] + b["ratio"]) >= 0.20
        and a["rectangularity"] >= 0.35
        and b["rectangularity"] >= 0.35
    )
    if not substantial:
        return False, None

    dx = abs(a["cx"] - b["cx"]) / max(float(image_w), 1.0)
    dy = abs(a["cy"] - b["cy"]) / max(float(image_h), 1.0)
    if max(dx, dy) < 0.16:
        return False, None
    return True, {
        "largest_region_area_ratio": round(a["ratio"], 3),
        "second_region_area_ratio": round(b["ratio"], 3),
        "center_separation_x": round(dx, 3),
        "center_separation_y": round(dy, 3),
    }


def _bottleneck_axis(mask, axis, image_area):
    """Find a narrow neck separating two substantial portions of one green blob."""
    binary = (mask > 0).astype(np.uint8)
    profile = binary.sum(axis=0 if axis == "x" else 1).astype(np.float32)
    nonzero = np.flatnonzero(profile > 0)
    if len(nonzero) < 12:
        return None

    lo, hi = int(nonzero[0]), int(nonzero[-1])
    span = hi - lo + 1
    if span < 30:
        return None

    start = lo + int(span * 0.18)
    end = lo + int(span * 0.82)
    if end <= start:
        return None

    total = float(binary.sum())
    best = None
    window = max(5, span // 12)

    for cut in range(start, end + 1):
        if axis == "x":
            left = float(binary[:, :cut].sum())
            right = float(binary[:, cut:].sum())
        else:
            left = float(binary[:cut, :].sum())
            right = float(binary[cut:, :].sum())

        small_ratio = min(left, right) / max(image_area, 1.0)
        large_ratio = max(left, right) / max(image_area, 1.0)
        if small_ratio < 0.055 or large_ratio < 0.14:
            continue

        l0 = max(lo, cut - window)
        r1 = min(hi + 1, cut + window + 1)
        left_band = profile[l0:cut]
        right_band = profile[cut + 1:r1]
        left_ref = float(np.percentile(left_band[left_band > 0], 70)) if np.any(left_band > 0) else 0.0
        right_ref = float(np.percentile(right_band[right_band > 0], 70)) if np.any(right_band > 0) else 0.0
        shoulder = min(left_ref, right_ref)
        if shoulder <= 0:
            continue

        neck = float(profile[cut])
        neck_ratio = neck / shoulder
        balance = min(left, right) / max(max(left, right), 1.0)

        # Require a real neck, not just an ordinary board taper. The smaller side
        # must still be meaningful and the two sides cannot be wildly imbalanced.
        if neck_ratio <= 0.46 and balance >= 0.16 and total / max(image_area, 1.0) >= 0.18:
            score = (1.0 - neck_ratio) * balance
            candidate = {
                "axis": axis,
                "cut": int(cut),
                "neck_ratio": round(neck_ratio, 3),
                "side_balance": round(balance, 3),
                "smaller_side_area_ratio": round(small_ratio, 3),
                "larger_side_area_ratio": round(large_ratio, 3),
                "score": round(score, 3),
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate
    return best


def _bottleneck_split(mask, image_area):
    x = _bottleneck_axis(mask, "x", image_area)
    y = _bottleneck_axis(mask, "y", image_area)
    choices = [c for c in (x, y) if c]
    if not choices:
        return False, None
    best = max(choices, key=lambda c: c["score"])
    return True, best


def inspect_frame(image_path):
    result = {
        "version": "SPIKE Single-Frame Board Identity Gate v0.5",
        "status": "SINGLE_BOARD_NOT_CONTRADICTED",
        "block_analysis": False,
        "confidence": 0,
        "evidence": [],
        "next_step": "Continue normal board analysis.",
    }
    try:
        im = cv2.imread(image_path)
        if im is None:
            result.update({"status": "FRAME_UNREADABLE", "confidence": 0})
            return result

        h, w = im.shape[:2]
        area = float(max(1, h * w))
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
        raw = cv2.inRange(hsv, np.array([28, 35, 22]), np.array([105, 255, 255]))

        # Pass 1: independently visible PCB bodies.
        k0 = max(3, (min(h, w) // 110) | 1)
        separated = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, np.ones((k0, k0), np.uint8), iterations=1)
        base_regions = _component_stats(separated, area, 0.025)
        two_regions, two_metrics = _two_substantial_regions(base_regions, area, w, h)

        # Pass 2: merged touching boards often form one compound silhouette with
        # a narrow neck. Test both image axes for two substantial lobes joined by
        # a much thinner bridge.
        bottleneck_trigger, bottleneck_metrics = _bottleneck_split(separated, area)

        # Pass 3: multiscale opening removes narrow bridges and asks whether the
        # silhouette resolves into two substantial board-like bodies.
        split_trigger = False
        split_metrics = None
        split_scale = None
        scales = sorted({
            max(5, (min(h, w) // 85) | 1),
            max(7, (min(h, w) // 60) | 1),
            max(9, (min(h, w) // 42) | 1),
        })
        for ks in scales:
            opened = cv2.morphologyEx(raw, cv2.MORPH_OPEN, np.ones((ks, ks), np.uint8), iterations=1)
            kc = max(3, (ks // 3) | 1)
            opened = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, np.ones((kc, kc), np.uint8), iterations=1)
            regs = _component_stats(opened, area, 0.02)
            ok, metrics = _two_substantial_regions(regs, area, w, h)
            if ok:
                split_trigger = True
                split_metrics = metrics
                split_scale = ks
                break

        # Pass 4: compound silhouette corroboration.
        k = max(5, (min(h, w) // 45) | 1)
        mask = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8), iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [c for c in contours if cv2.contourArea(c) >= area * 0.12]

        profile_a = profile_b = profile_c = False
        area_ratio = solidity = rectangularity = deepest = 0.0
        deep_count = 0

        if contours:
            c = max(contours, key=cv2.contourArea)
            board_area = float(cv2.contourArea(c))
            rect = cv2.minAreaRect(c)
            rw, rh = rect[1]
            rw, rh = max(float(rw), 1.0), max(float(rh), 1.0)
            hull = cv2.convexHull(c)
            hull_area = max(float(cv2.contourArea(hull)), 1.0)
            solidity = board_area / hull_area
            rectangularity = board_area / max(rw * rh, 1.0)
            hull_idx = cv2.convexHull(c, returnPoints=False)
            defects = cv2.convexityDefects(c, hull_idx) if hull_idx is not None and len(hull_idx) >= 3 and len(c) >= 4 else None
            deep = []
            scale = max(rw, rh)
            if defects is not None:
                for d in defects[:, 0]:
                    depth = float(d[3]) / 256.0
                    if depth >= scale * 0.04:
                        deep.append(depth / scale)
            area_ratio = board_area / area
            deep_count = len(deep)
            deepest = max(deep) if deep else 0.0

            profile_a = 0.20 <= area_ratio <= 0.80 and solidity < 0.91 and rectangularity < 0.82 and deep_count >= 5 and deepest >= 0.08
            profile_b = 0.40 <= area_ratio <= 0.85 and solidity < 0.94 and rectangularity < 0.86 and deep_count >= 4 and deepest >= 0.07
            profile_c = 0.28 <= area_ratio <= 0.88 and solidity < 0.90 and rectangularity < 0.80 and deep_count >= 2 and deepest >= 0.12

        suspicious = bool(two_regions or bottleneck_trigger or split_trigger or profile_a or profile_b or profile_c)
        result["metrics"] = {
            "pcb_region_area_ratio": round(area_ratio, 3),
            "solidity": round(solidity, 3),
            "rectangularity": round(rectangularity, 3),
            "deep_concavity_count": int(deep_count),
            "deepest_concavity_ratio": round(deepest, 3),
            "base_independent_pcb_regions": len(base_regions),
            "base_two_region_trigger": bool(two_regions),
            "base_two_region_metrics": two_metrics,
            "bottleneck_split_trigger": bool(bottleneck_trigger),
            "bottleneck_split_metrics": bottleneck_metrics,
            "multiscale_split_trigger": bool(split_trigger),
            "multiscale_split_kernel": split_scale,
            "multiscale_split_metrics": split_metrics,
            "compound_profile_a": bool(profile_a),
            "compound_profile_b": bool(profile_b),
            "compound_profile_c": bool(profile_c),
        }

        if suspicious:
            why = []
            if two_regions:
                why.append("Two independently substantial PCB-like regions are visible in the same photograph.")
            if bottleneck_trigger:
                why.append("One merged PCB-colored silhouette contains a narrow neck separating two substantial physical regions.")
            if split_trigger:
                why.append("A compound PCB silhouette separates into two substantial board-like bodies when narrow bridges are removed.")
            if profile_a or profile_b or profile_c:
                why.append("The PCB-like silhouette has compound geometry consistent with touching or overlapping physical boards.")
            why.append("Board grading and blueprinting are withheld until one physical board is isolated.")
            confidence = 96 if bottleneck_trigger else (94 if (two_regions or split_trigger) else (88 if profile_c else 84))
            result.update({
                "status": "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED",
                "block_analysis": True,
                "confidence": confidence,
                "evidence": why,
                "next_step": "Retake the photo with exactly one physical board in the frame, separated from other boards.",
            })
        return result
    except Exception as exc:
        result["status"] = "FRAME_GATE_UNCERTAIN"
        result["error"] = str(exc)
        return result
