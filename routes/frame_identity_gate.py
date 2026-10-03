"""SPIKE Single-Frame Board Identity Gate v0.5.

Blocks a single uploaded photograph when strong physical evidence says more than
one PCB is present. PCB confirmation and board identity remain separate gates.
Color is only used to find candidate PCB regions; geometry supplies the block.

Green PCB surface can split around a large shield on one physical board. A
multi-board stop now requires an exterior background gap between substantial
regions. Ambiguous green splits remain inspection cues, not identity verdicts.
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
    # Each body must be meaningful on its own, together cover a useful part of
    # the frame, and have nontrivial board-like geometry.
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
    separated_centers = max(dx, dy) >= 0.16
    if not separated_centers:
        return False, None
    return True, {
        "largest_region_area_ratio": round(a["ratio"], 3),
        "second_region_area_ratio": round(b["ratio"], 3),
        "center_separation_x": round(dx, 3),
        "center_separation_y": round(dy, 3),
    }


def _exterior_gap_support(im, regions):
    """Require visible background between bodies, connected to the frame edge.

    A dark RF shield can divide one PCB's green surface into two regions, but
    its metal face is not the surrounding background. A touching pair without
    a clear gap remains uncertain rather than becoming a hard split.
    """
    if len(regions) < 2:
        return False
    h, w = im.shape[:2]
    a, b = regions[:2]
    ax, ay, aw, ah = a["bbox"]
    bx, by, bw, bh = b["bbox"]
    if ax > bx:
        ax, ay, aw, ah, bx, by, bw, bh = bx, by, bw, bh, ax, ay, aw, ah
    horizontal = bx - (ax + aw)
    if ay > by:
        ay, ah, by, bh = by, bh, ay, ah
    vertical = by - (ay + ah)
    if max(horizontal / max(w, 1), vertical / max(h, 1)) < .025:
        return False

    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.int16)
    edge = max(4, int(min(h, w) * .035))
    border = np.concatenate((lab[:edge].reshape(-1, 3), lab[-edge:].reshape(-1, 3),
                             lab[:, :edge].reshape(-1, 3), lab[:, -edge:].reshape(-1, 3)))
    median = np.median(border, axis=0)
    # A varied background cannot supply reliable negative evidence.
    if np.median(np.linalg.norm(border - median, axis=1)) > 26:
        return False
    background = (np.linalg.norm(lab - median, axis=2) < 30).astype(np.uint8)
    _, labels = cv2.connectedComponents(background, connectivity=8)
    edge_labels = np.unique(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1])))
    exterior = np.isin(labels, edge_labels[edge_labels != 0])

    if horizontal / max(w, 1) >= vertical / max(h, 1):
        left, right = sorted(regions[:2], key=lambda r: r["bbox"][0])
        lx, ly, lw, lh = left["bbox"]
        rx, ry, rw, rh = right["bbox"]
        y0, y1 = max(ly, ry), min(ly + lh, ry + rh)
        cy = (y0 + y1) // 2 if y1 > y0 else int((left["cy"] + right["cy"]) / 2)
        xs = np.linspace(lx + lw + 2, rx - 2, 11).astype(int)
        ys = np.full_like(xs, cy)
    else:
        top, bottom = sorted(regions[:2], key=lambda r: r["bbox"][1])
        tx, ty, tw, th = top["bbox"]
        bx, by, bw, bh = bottom["bbox"]
        x0, x1 = max(tx, bx), min(tx + tw, bx + bw)
        cx = (x0 + x1) // 2 if x1 > x0 else int((top["cx"] + bottom["cx"]) / 2)
        ys = np.linspace(ty + th + 2, by - 2, 11).astype(int)
        xs = np.full_like(ys, cx)
    xs = np.clip(xs, 0, w - 1)
    ys = np.clip(ys, 0, h - 1)
    return float(np.mean(exterior[ys, xs])) >= .8


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

        # Pass 1: preserve independently visible PCB bodies.
        k0 = max(3, (min(h, w) // 110) | 1)
        separated = cv2.morphologyEx(
            raw, cv2.MORPH_CLOSE, np.ones((k0, k0), np.uint8), iterations=1
        )
        base_regions = _component_stats(separated, area, 0.025)
        two_regions, two_metrics = _two_substantial_regions(base_regions, area, w, h)

        # Pass 2: touching boards can be welded by a narrow green bridge. Use
        # several opening scales to remove those bridges, then ask whether the
        # shape consistently resolves into two substantial board-like bodies.
        split_trigger = False
        split_metrics = None
        split_scale = None
        split_regions = None
        scales = sorted({
            max(5, (min(h, w) // 85) | 1),
            max(7, (min(h, w) // 60) | 1),
            max(9, (min(h, w) // 42) | 1),
        })
        for ks in scales:
            opened = cv2.morphologyEx(
                raw, cv2.MORPH_OPEN, np.ones((ks, ks), np.uint8), iterations=1
            )
            # A light close restores ordinary board texture after the opening,
            # without rebuilding the narrow bridge we just removed.
            kc = max(3, (ks // 3) | 1)
            opened = cv2.morphologyEx(
                opened, cv2.MORPH_CLOSE, np.ones((kc, kc), np.uint8), iterations=1
            )
            regs = _component_stats(opened, area, 0.02)
            ok, metrics = _two_substantial_regions(regs, area, w, h)
            if ok:
                split_trigger = True
                split_metrics = metrics
                split_scale = ks
                split_regions = regs
                break

        # Pass 3: inspect the largest merged silhouette for extreme compound
        # geometry. This remains a corroborating path, not the primary detector.
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
                # OpenCV bindings may return N x 1 x 4 or N x 4 defects.
                for d in np.asarray(defects).reshape(-1, 4):
                    depth = float(d[3]) / 256.0
                    if depth >= scale * 0.04:
                        deep.append(depth / scale)
            area_ratio = board_area / area
            deep_count = len(deep)
            deepest = max(deep) if deep else 0.0

            profile_a = (
                0.20 <= area_ratio <= 0.80
                and solidity < 0.91
                and rectangularity < 0.82
                and deep_count >= 5
                and deepest >= 0.08
            )
            profile_b = (
                0.40 <= area_ratio <= 0.85
                and solidity < 0.94
                and rectangularity < 0.86
                and deep_count >= 4
                and deepest >= 0.07
            )
            profile_c = (
                0.28 <= area_ratio <= 0.88
                and solidity < 0.90
                and rectangularity < 0.80
                and deep_count >= 2
                and deepest >= 0.12
            )

        green_split = bool(two_regions or split_trigger)
        exterior_gap = bool((two_regions and _exterior_gap_support(im, base_regions))
                            or (split_trigger and _exterior_gap_support(im, split_regions)))
        suspicious = bool(green_split and exterior_gap)
        result["metrics"] = {
            "pcb_region_area_ratio": round(area_ratio, 3),
            "solidity": round(solidity, 3),
            "rectangularity": round(rectangularity, 3),
            "deep_concavity_count": int(deep_count),
            "deepest_concavity_ratio": round(deepest, 3),
            "base_independent_pcb_regions": len(base_regions),
            "base_two_region_trigger": bool(two_regions),
            "multiscale_split_trigger": bool(split_trigger),
            "multiscale_split_kernel": split_scale,
            "multiscale_split_metrics": split_metrics,
            "compound_profile_a": bool(profile_a),
            "compound_profile_b": bool(profile_b),
            "compound_profile_c": bool(profile_c),
            "exterior_background_gap": exterior_gap,
        }

        if suspicious:
            why = []
            if two_regions:
                why.append("Two substantial PCB-like regions have an exterior background gap between them.")
            if split_trigger:
                why.append("The separation persists in a multiscale pass.")
            why.append("Board grading and blueprinting are withheld until one physical board is isolated.")
            confidence = 94 if two_regions and split_trigger else 88
            result.update({
                "status": "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED",
                "block_analysis": True,
                "confidence": confidence,
                "evidence": why,
                "next_step": "Retake the photo with exactly one physical board in the frame, separated from other boards.",
            })
        elif green_split or profile_a or profile_b or profile_c:
            result.update({
                "status": "FRAME_SHAPE_AMBIGUOUS",
                "confidence": 45,
                "evidence": ["Green surface regions or contour shape are ambiguous; RF shields and components can split one board visually."],
                "next_step": "Continue cross-photo identity review; use the outer board outline and matching connectors.",
            })
        return result
    except Exception as exc:
        result["status"] = "FRAME_GATE_UNCERTAIN"
        result["error"] = str(exc)
        return result
