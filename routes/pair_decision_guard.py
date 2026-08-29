"""SPIKE pair decision guard v1.0.

Applied after the normal pair scorer. It prevents a third family built from
weak pooled clues from defeating a high-confidence, structurally specific side.
"""

from copy import deepcopy
from routes.decision_guard import family, strong_structural_family, decision_trace


def guard_pair(side_a, side_b, paired):
    out = deepcopy(paired)
    strong_a = strong_structural_family(side_a)
    strong_b = strong_structural_family(side_b)
    candidates = [("A", side_a, strong_a), ("B", side_b, strong_b)]
    candidates = [x for x in candidates if x[2]]
    if not candidates:
        out["decision_trace"] = decision_trace(out.get("board_type", "Unknown"))
        return out

    side_name, strong_side, anchor = max(candidates, key=lambda x: x[2]["confidence"])
    other = side_b if side_name == "A" else side_a
    other_conf = float(other.get("confidence", 0) or 0)
    other_family = family(other.get("board_type"))
    paired_family = family(out.get("board_type"))

    # Preserve a structurally strong identity when the opposite face is weak or
    # when pooled weak evidence invents a third family neither side strongly chose.
    third_family = paired_family not in (anchor["family"], other_family)
    weak_opposite = other_conf <= 60
    if anchor["family"] == "motherboard" and (weak_opposite or third_family):
        out["board_type"] = "Motherboard / Main Logic Board"
        out["confidence"] = max(86, min(96, round(anchor["confidence"] - (2 if other_family != "motherboard" else 0))))
        # Preserve recovery value from the structurally informative face.
        strong_score = float(strong_side.get("score", 0) or 0)
        out["score"] = max(float(out.get("score", 0) or 0), round(strong_score * 0.90))
        out["grade"] = "MEDIUM" if out["score"] >= 9 else out.get("grade", "LOW")
        out["pay_dirt_ready"] = out["score"] >= 16
        reason = (
            f"SPIKE preserved Side {side_name} motherboard identity because strong structural architecture "
            "outranks generic capacitor/power hints from the opposite face."
        )
        out["board_type_reason"] = reason
        paired_meta = out.setdefault("paired_analysis", {})
        paired_meta["winner_family"] = "motherboard"
        paired_meta["structural_guard_applied"] = True
        paired_meta["structural_guard_side"] = side_name
        paired_meta["message"] = reason
        out["reasoning_crosscheck"] = {
            "status": "structural_guard",
            "simple_classifier": out["board_type"],
            "weighted_hypothesis": out["board_type"],
            "weighted_confidence": out["confidence"],
            "message": reason,
        }
        out["decision_trace"] = decision_trace(
            out["board_type"],
            hard=anchor.get("anchors") or ["strong motherboard architecture"],
            supporting=[f"Side {side_name} confidence {anchor['confidence']:.0f}%"],
            weak=[f"opposite-side family {other_family} at {other_conf:.0f}%"],
            contradictions=anchor.get("vetoes") or [],
        )
    else:
        out["decision_trace"] = decision_trace(
            out.get("board_type", "Unknown"),
            hard=anchor.get("anchors") or [],
            supporting=[f"strong structural evidence on Side {side_name}"],
        )
    return out
