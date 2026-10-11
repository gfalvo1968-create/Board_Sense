"""User-declared loose CPU inspection, without whole-board valuation.

This is an explicit item context, not automatic recognition or an assay.
Views remain separate: board identity heuristics cannot verify opened CPU parts.
"""
from copy import deepcopy
from routes.photo_quality import assess_photo_quality


def inspect_processor(image_path):
    return {
        "status": "component_inspection", "board_type": "Loose processor / CPU (user identified)",
        "grade": "WITHHELD", "score": None, "confidence": None,
        "identity_basis": "USER_SELECTED_COMPONENT", "pay_dirt_ready": False,
        "object_gate": {"mode": "component", "label": "Loose processor / CPU",
                        "confirmed_pcb": False, "block_downstream": True,
                        "message": "You selected a loose processor. Whole-board grading and pricing are disabled."},
        "photo_quality": assess_photo_quality(image_path),
        "recommendation": "Keep the package, marked lid, and exposed parts together. Record readable model markings and whether the package is opened or damaged. Obtain a processor-specific buyer quote before valuing it.",
        "recovery_signals": ["Processor family supplied by the user; not independently recognized.",
                             "Gold content, plating, recoverable quantity, and payout remain unmeasured."],
        "board_blueprint": {"available": False, "component_index": []},
        "recovery_lab": {"labs": [], "decision_options": ["RECORD MARKINGS", "CHECK CONDITION", "GET PROCESSOR QUOTE"]},
        "model": "SPIKE Processor Context v0.1",
    }


def processor_case(results):
    result = deepcopy(results[0])
    result["case_analysis"] = {"mode": "component_inspection", "views_analyzed": len(results),
                               "message": "Photos inspected separately under user-selected processor context. Same-item identity has not been independently verified."}
    result["three_answers"] = {
        "identity": {"answer": result["board_type"], "subtype": "Model markings require manual confirmation"},
        "recovery": {"grade": "WITHHELD", "condition": "MANUAL INSPECTION REQUIRED"},
        "economics": {"winner": None, "needs_values": True, "message": "A processor-specific buyer quote and condition check are required. No whole-board price or gold yield applies."},
    }
    return result
