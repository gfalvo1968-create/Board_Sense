"""SPIKE Recovery Grade Guard v0.1.

Prevents a confirmed processor/dense-logic board from being economically
collapsed to LOW merely because the exact equipment subtype is unresolved.
This is a conservative floor, not a precious-metal assay.
"""


def apply_recovery_grade_guard(result):
    out = dict(result)
    signals = out.get("signals") or {}
    board = str(out.get("board_type", "")).lower()
    grade = str(out.get("grade", "LOW")).upper()
    evidence = []

    logic_family = any(x in board for x in ("logic", "motherboard", "processor"))
    processor = bool(signals.get("processor"))
    large_ic = bool(signals.get("large_ic_chips") or signals.get("ic_signal_confirmed"))
    dense = bool(signals.get("dense_component_board")) or float(signals.get("component_density", 0) or 0) >= 0.18

    if logic_family: evidence.append("confirmed broad logic-board family")
    if processor: evidence.append("processor evidence")
    if large_ic: evidence.append("multiple/large logic-package evidence")
    if dense: evidence.append("dense component population")

    floor = None
    if logic_family and processor and large_ic:
        floor = "MEDIUM"
    elif logic_family and large_ic and dense:
        floor = "MEDIUM"

    order = {"N/A": -1, "LOW": 0, "MEDIUM": 1, "HIGH": 2, "VERY HIGH": 3}
    raised = bool(floor and order.get(grade, 0) < order[floor])
    if raised:
        out["grade"] = floor
        out["recommendation"] = "Sort as a logic-rich recovery board; compare sell-whole, selective strip, and full-recovery economics before processing."
        out["recovery_signals"] = list(dict.fromkeys((out.get("recovery_signals") or []) + ["logic-rich recovery floor", "processor/large-IC value-bearing evidence"]))
        out["grade_notes"] = "Recovery Grade Guard raised a LOW score to MEDIUM because independent logic/processor evidence is physically present. Exact equipment subtype is not required for the floor."

    out["recovery_grade_guard"] = {
        "active": True,
        "raised_grade": raised,
        "original_grade": grade,
        "final_grade": out.get("grade", grade),
        "floor": floor,
        "evidence": evidence,
        "pay_dirt_policy": "Grade floor does not automatically set Pay Dirt Ready. Pay Dirt remains evidence-driven.",
        "model": "SPIKE Recovery Grade Guard v0.1",
    }
    return out
