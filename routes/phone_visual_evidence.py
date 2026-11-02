"""Phase 7D conservative visual handset candidate signals.

This does not assert phone origin, RF circuitry, plating, value, or device model.
A tall PCB plus a repeated keypad bank may also be a remote or controller.
"""
def observe_handset_candidate(fingerprint, keypad):
    out = {
        "handset_mainboard_outline": False,
        "handset_contact_layout": False,
        "rf_antenna_section": False,
        "phone_connector_arrangement": False,
        "status": "insufficient_evidence",
        "model": "SPIKE Handset Candidate Geometry v0.1",
        "rule": "Geometry and keypad contacts alone cannot identify a mobile phone.",
    }
    if not isinstance(fingerprint, dict) or not isinstance(keypad, dict):
        return out
    quality = fingerprint.get("geometry_quality")
    aspect = fingerprint.get("board_aspect")
    try:
        aspect = float(aspect)
    except (ValueError, TypeError):
        return out
    if (fingerprint.get("coverage") != "whole_or_large_view"
            or quality not in ("medium", "good") or not 2.2 <= aspect <= 5.8):
        return out
    out["handset_mainboard_outline"] = True
    if keypad.get("supported") is True and int(keypad.get("contact_count") or 0) >= 9:
        out["handset_contact_layout"] = True
        out["status"] = "handset_candidate_requires_independent_rf_or_connector_evidence"
    else:
        out["status"] = "elongated_pcb_only"
    out["observations"] = [
        "elongated full-board shape measured by physical fingerprint",
        "repeated keypad-contact bank" if out["handset_contact_layout"] else "keypad pattern not corroborated",
    ]
    return out
