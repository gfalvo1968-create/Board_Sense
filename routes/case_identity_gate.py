"""SPIKE Same-Board Verification Gate v1.4.

Checks single-frame identity safety first, then cross-photo semantic contradiction
and physical geometry. Conflicting classifier labels from close-ups must not
override compatible whole-board geometry. Color alone never proves identity.

v1.4 adds an evidence floor: zero usable whole-board views can never become
PROBABLY_SAME_BOARD. Downstream grading stays blocked until the user supplies a
clear whole-board identity view.
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
    version = "SPIKE Same-Board Verification Gate v1.4"
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

    frame_blocks = []
    hard_frame_blocks = []
    clarification_blocks = []
    for i, r in enumerate(results, 1):
        bp = r.get("board_blueprint") or {}
        fg = bp.get("frame_identity_gate") or r.get("frame_identity_gate") or {}
        if not fg.get("block_analysis"):
            continue
        packet = {"view": i, "frame_identity_gate": fg}
        clarification_evidence = r.get("identity_clarification_evidence") or {}
        if clarification_evidence.get("resolved"):
            packet["identity_clarification_evidence"] = clarification_evidence
        frame_blocks.append(packet)
        m = fg.get("metrics") or {}
        has_metrics = bool(m)
        two_region = bool(m.get("base_two_region_trigger"))
        multiscale = bool(m.get("multiscale_split_trigger"))
        secondary_plane = bool(m.get("secondary_plane_trigger"))
        bottleneck = bool(m.get("bottleneck_split_trigger"))
        if has_metrics and bottleneck and not two_region and not multiscale and not secondary_plane:
            if clarification_evidence.get("resolved"):
                continue
            clarification_blocks.append(packet)
        else:
            hard_frame_blocks.append(packet)

    if hard_frame_blocks:
        return {
            "version": version,
            "status": "MULTIPLE_BOARDS_IN_FRAME_SUSPECTED",
            "same_board": False,
            "confidence": max(int(x["frame_identity_gate"].get("confidence", 0) or 0) for x in hard_frame_blocks),
            "block_reconciliation": True,
            "clarification_needed": False,
            "whole_view_count": 0,
            "conflict_graph": [],
            "frame_blocks": frame_blocks,
            "identity_next_step": "Retake each hard-flagged photo with exactly one physical board in the frame, then start the case again.",
            "reasons": ["At least one uploaded photo has independent physical evidence of more than one PCB or overlapping board regions."],
            "rule": "Independent two-region, multiscale, or proven secondary-plane evidence is a hard single-frame contradiction.",
        }

    if clarification_blocks:
        requested = []
        for packet in clarification_blocks:
            view = packet["view"]
            fg = packet["frame_identity_gate"]
            m = fg.get("metrics") or {}
            neck = m.get("bottleneck_split_metrics") or {}
            axis = neck.get("axis")
            requested.append({
                "flagged_view": view,
                "request_type": "targeted_continuity_photo",
                "instruction": (
                    f"Retake Photo {view} from the SAME SIDE, centered on the narrow neck/bridge. "
                    "Include continuous PCB material on both sides of the narrow section, plus nearby mounting holes or connectors."
                ),
                "detector_reason": "bottleneck_only",
                "axis": axis,
                "cut": neck.get("cut"),
            })
        return {
            "version": version,
            "status": "IDENTITY_CLARIFICATION_NEEDED",
            "same_board": None,
            "confidence": 55,
            "block_reconciliation": True,
            "clarification_needed": True,
            "whole_view_count": 0,
            "conflict_graph": [],
            "frame_blocks": frame_blocks,
            "requested_photos": requested,
            "identity_next_step": requested[0]["instruction"],
            "reasons": [
                "SPIKE found a narrow-neck shape ambiguity, but no independent proof of multiple boards.",
                "Downstream grading stays blocked until a targeted continuity photo settles the physical shape.",
            ],
            "rule": "When evidence is insufficient, ask for the photo that can settle it. A bottleneck alone is not proof of two boards.",
        }

    resolved_clarifications = [
        {"view": i, "evidence": r.get("identity_clarification_evidence")}
        for i, r in enumerate(results, 1)
        if (r.get("identity_clarification_evidence") or {}).get("resolved")
    ]

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

    # Evidence floor: absence of a contradiction is not positive identity evidence.
    # If SPIKE has no usable whole-board geometry, it must ask for one instead of
    # converting low-quality/partial photos into a same-board claim.
    if not whole_views:
        return {
            "version": version,
            "status": "IDENTITY_UNCERTAIN",
            "same_board": None,
            "confidence": 25,
            "block_reconciliation": True,
            "clarification_needed": True,
            "families": families,
            "whole_view_count": 0,
            "whole_view_indices": [],
            "physical_pair_checks": [],
            "conflict_graph": [],
            "conflicting_views": [],
            "semantic_conflict": False,
            "positive_geometry_evidence": False,
            "coherent_geometry": False,
            "coherence_coverage": 0.0,
            "requested_photos": [
                {
                    "request_type": "whole_board_identity_photo",
                    "instruction": "Add one clear full-board photo showing the complete outline, mounting holes, and major connector positions.",
                    "detector_reason": "no_usable_whole_board_geometry",
                }
            ],
            "identity_next_step": "Add one clear full-board photo showing the complete outline, mounting holes, and major connector positions.",
            "reasons": [
                "No uploaded view provides usable whole-board geometry for identity verification.",
                "Partial or low-quality views can describe components, but they cannot prove that all photos show the same physical board.",
            ],
            "rule": "No usable whole-board evidence means identity stays unresolved. Absence of contradiction is not proof of sameness.",
        }

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
    linked = _connected_component(whole_set, compatible_edges, whole_views[0]) if whole_views else set()
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
        "resolved_clarifications": resolved_clarifications,
        "rule": "Compatible geometry must connect the complete usable whole-board set; semantic labels, color, and one matching pair alone are not proof.",
    }
