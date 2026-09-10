"""SPIKE Same-Board Verification Gate v1.0.

Checks single-frame identity safety first, then cross-photo semantic contradiction
and physical geometry. Conflicting classifier labels from close-ups must not
override compatible whole-board geometry. Color alone never proves identity.

v1.0 rule: if any uploaded photo itself is flagged as containing multiple boards
or overlapping PCB regions, the entire case stops before evidence reconciliation.
One compatible pair also cannot prove an entire multi-photo case is one board.
"""
from routes.board_fingerprint import fingerprint_conflict


def _family(r):
    t = str(r.get("board_type", "unknown")).lower()
    if "motherboard" in t or "main logic" in t or "dense logic" in t:
        return "logic"
    if "power" in t or "supply" in t:
        return "power"
    if "expansion" in t or "gold finger" in t:
        return "expansion"
    if "control" in t:
        return "control"
    if "phone" in t or "mobile" in t:
        return "mobile"
    return "unknown"


def _anchors(r):
    s = r.get("signals") or {}
    return {
        "processor": bool(s.get("processor")),
        "ram": bool(s.get("ram") or s.get("possible_ram")),
        "large_ic": bool(s.get("large_ic_chips")),
        "power": bool(s.get("possible_power_board") or s.get("power_board")),
        "gold_edge": bool(s.get("gold_fingers") or s.get("gold_finger_edge")),
        "motherboard": bool(s.get("possible_motherboard")),
    }


def _usable_whole(f):
    return f.get("coverage") == "whole_or_large_view" and f.get("geometry_quality") in ("good", "medium")


def _connected_component(nodes, edges, start):
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for nxt in nodes:
            if nxt not in seen and (min(cur, nxt), max(cur, nxt)) in edges:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def verify_same_board(results):
    n = len(results or [])
    version = "SPIKE Same-Board Verification Gate v1.0"
    if n < 2:
        return {
            "version": version,
            "status": "INSUFFICIENT_VIEWS",
            "same_board": None,
            "confidence": 0,
            "block_reconciliation": False,
            "whole_view_count": 0,
            "conflict_graph": [],
            "identity_next_step": "Add at least one more photo of the same physical board.",
            "reasons": ["At least two views are needed for a multi-photo identity check."],
        }

    # Single-frame safety gate comes first. A photo that may contain two physical
    # boards must never be merged into a one-board case, even if other views match.
    frame_blocks = []
    for i, r in enumerate(results, 1):
        bp = r.get("board_blueprint") or {}
        fg = bp.get("frame_identity_gate") or r.get("frame_identity_gate") or {}
        if fg.get("block_analysis"):
            frame_blocks.append({"view": i, "frame_identity_gate": fg})
    if frame_blocks:
        return {
            "version": version,
            "status": "MULTIPLE_BOARDS_IN_FRAME_SUSPECTED",
            "same_board": False,
            "confidence": max(int(x["frame_identity_gate"].get("confidence", 0) or 0) for x in frame_blocks),
            "block_reconciliation": True,
            "whole_view_count": 0,
            "conflict_graph": [],
            "frame_blocks": frame_blocks,
            "identity_next_step": "Retake each flagged photo with exactly one physical board in the frame, then start the case again.",
            "reasons": ["At least one uploaded photo may contain more than one physical PCB or overlapping board regions."],
            "rule": "One physical board per photo is required before multi-photo same-board verification can begin.",
        }

    families = [_family(r) for r in results]
    known = [f for f in families if f != "unknown"]
    unique = set(known)
    anchors = [_anchors(r) for r in results]
    semantic_conflict = False
    physical_outlier = False
    uncertain_physical = False
    reasons = []
    physical = []
    counts = {f: known.count(f) for f in unique}
    fps = [r.get("physical_fingerprint") or {} for r in results]
    whole_views = [i + 1 for i, f in enumerate(fps) if _usable_whole(f)]

    if len(unique) >= 2:
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        a, b = ranked[0], ranked[1]
        high = {
            f: max([float(r.get("confidence", 0) or 0) for r in results if _family(r) == f] or [0])
            for f in unique
        }
        if ((a[1] >= 2 and b[1] >= 2 and high[a[0]] >= 75 and high[b[0]] >= 75)
                or (high[a[0]] >= 90 and high[b[0]] >= 90)):
            semantic_conflict = True
            reasons.append("Strong views support conflicting board families: " + a[0] + " versus " + b[0] + ".")

    power_views = sum(1 for a in anchors if a["power"] and not a["motherboard"])
    logic_views = sum(1 for a in anchors if a["motherboard"] or a["processor"] or a["ram"])
    if power_views >= 2 and logic_views >= 2 and len(unique) >= 2 and "power" in unique and "logic" in unique:
        reasons.append("Power and logic structures coexist; treating topology as mixed until physical identity is checked rather than automatically splitting the case.")

    for i in range(n):
        for j in range(i + 1, n):
            c = fingerprint_conflict(fps[i], fps[j])
            if c:
                physical.append({"views": [i + 1, j + 1], **c})

    conflicts = [p for p in physical if p.get("conflict")]
    compatible = [p for p in physical if not p.get("conflict")]
    compatible_pairs = len(compatible)
    conflict_views = {v for p in conflicts for v in p.get("views", [])}
    per_view = {i: 0 for i in range(1, n + 1)}
    for p in conflicts:
        for v in p.get("views", []):
            per_view[v] = per_view.get(v, 0) + 1

    conflict_graph = [
        {"view": i, "conflict_degree": per_view.get(i, 0)}
        for i in range(1, n + 1)
        if per_view.get(i, 0) > 0
    ]
    outliers = [i for i, d in per_view.items() if d >= 2]
    if outliers:
        physical_outlier = True
        reasons.append("A usable whole-board view conflicts with at least two other usable board geometries, forming a corroborated physical outlier.")
    elif conflicts:
        uncertain_physical = True
        reasons.append("Physical fingerprint disagreement exists, but it does not yet form a corroborated multiple-board cluster.")

    whole_set = set(whole_views)
    compatible_edges = {
        (min(p["views"]), max(p["views"]))
        for p in compatible
        if p["views"][0] in whole_set and p["views"][1] in whole_set
    }
    if whole_views:
        linked = _connected_component(whole_set, compatible_edges, whole_views[0])
    else:
        linked = set()
    coherent_geometry = len(whole_views) >= 2 and linked == whole_set
    coherence_coverage = round(len(linked) / max(1, len(whole_views)), 3)

    positive_geometry = coherent_geometry and compatible_pairs >= 1 and not uncertain_physical and not physical_outlier

    if physical_outlier:
        return {
            "version": version,
            "status": "MULTIPLE_BOARDS_SUSPECTED",
            "same_board": False,
            "confidence": 92,
            "block_reconciliation": True,
            "families": families,
            "whole_view_count": len(whole_views),
            "whole_view_indices": whole_views,
            "physical_pair_checks": physical,
            "conflict_graph": conflict_graph,
            "conflicting_views": sorted(conflict_views),
            "semantic_conflict": semantic_conflict,
            "positive_geometry_evidence": positive_geometry,
            "coherent_geometry": coherent_geometry,
            "coherence_coverage": coherence_coverage,
            "identity_next_step": "Split the photos by physical board and start a separate case for each board.",
            "reasons": reasons,
            "rule": "Only corroborated physical geometry conflict can hard-split a multi-photo case. One compatible pair never proves identity for the entire case.",
        }

    incomplete_coherence = len(whole_views) >= 3 and not coherent_geometry
    if incomplete_coherence:
        reasons.append("Usable whole-board views do not form one coherent physical-geometry cluster across the complete case.")
        reasons.append("A matching pair is not enough to prove that every uploaded photo belongs to the same board.")
        return {
            "version": version,
            "status": "IDENTITY_UNCERTAIN",
            "same_board": None,
            "confidence": 45,
            "block_reconciliation": True,
            "families": families,
            "whole_view_count": len(whole_views),
            "whole_view_indices": whole_views,
            "physical_pair_checks": physical,
            "conflict_graph": conflict_graph,
            "conflicting_views": sorted(conflict_views),
            "semantic_conflict": semantic_conflict,
            "positive_geometry_evidence": False,
            "coherent_geometry": False,
            "coherence_coverage": coherence_coverage,
            "identity_next_step": "Add clear full-board views showing outline, mounting holes, and major connector positions, or split photos into separate board cases.",
            "reasons": reasons,
            "rule": "High-confidence same-board identity requires compatible physical evidence connecting every usable whole-board view in the case.",
        }

    if positive_geometry:
        status = "PROBABLY_SAME_BOARD"
        conf = min(94, 84 + min(10, (len(whole_views) - 2) * 3 + compatible_pairs))
        if semantic_conflict:
            reasons.append("Conflicting classifier labels were treated as view-role differences because coherent whole-board geometry positively links the complete usable-view set.")
        reasons.append("All usable whole-board views belong to one connected compatibility cluster with no corroborated physical outlier.")
        next_step = "No extra identity photo required unless a later view introduces a physical contradiction."
    elif uncertain_physical or semantic_conflict or len(unique) > 1:
        status = "IDENTITY_UNCERTAIN"
        conf = 50 if uncertain_physical and len(whole_views) <= 2 else (55 if uncertain_physical else 60)
        reasons.append("SPIKE will not grant high combined confidence until board identity is better established.")
        next_step = "Add one clear full-board photo that shows the complete board outline, mounting holes, and major connector positions."
    else:
        status = "PROBABLY_SAME_BOARD"
        conf = 82
        reasons.append("No strong cross-view family or corroborated physical-geometry contradiction was found.")
        next_step = "No extra identity photo required unless the case result remains otherwise uncertain."

    return {
        "version": version,
        "status": status,
        "same_board": True if status == "PROBABLY_SAME_BOARD" else None,
        "confidence": conf,
        "block_reconciliation": False,
        "families": families,
        "whole_view_count": len(whole_views),
        "whole_view_indices": whole_views,
        "physical_pair_checks": physical,
        "conflict_graph": conflict_graph,
        "conflicting_views": sorted(conflict_views),
        "semantic_conflict": semantic_conflict,
        "identity_next_step": next_step,
        "reasons": reasons,
        "positive_geometry_evidence": positive_geometry,
        "coherent_geometry": coherent_geometry,
        "coherence_coverage": coherence_coverage,
        "rule": "Compatible geometry must connect the complete usable whole-board set; semantic labels, color, and one matching pair alone are not proof.",
    }
