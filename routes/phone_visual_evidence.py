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
    # An explicit coordinate bank is more useful than a detector's bare yes/no.
    # Some older detector outputs contain only a count, so leave those as
    # candidates, but record that the location itself is not confirmed.
    coords = keypad.get("contacts")
    positional_support = False
    if isinstance(coords, list) and len(coords) >= 9:
        try:
            xs = [float(p["x"]) for p in coords if isinstance(p, dict)]
            ys = [float(p["y"]) for p in coords if isinstance(p, dict)]
            if len(xs) >= 9 and len(ys) >= 9:
                # Real key matrices spread over both axes; a straight row
                # of plated vias/edge contacts is not a keypad field.
                radius = sorted(float(p.get("radius", 0)) for p in coords if isinstance(p,dict))
                middle = radius[len(radius)//2] if radius else 0
                positional_support = (middle > 0 and
                    (max(xs)-min(xs)) >= 5*middle and
                    (max(ys)-min(ys)) >= 5*middle)
        except (KeyError, TypeError, ValueError):
            positional_support = False
    if keypad.get("supported") is True and int(keypad.get("contact_count") or 0) >= 9 and (
            not isinstance(coords, list) or positional_support):
        out["handset_contact_layout"] = True
        out["status"] = "handset_candidate_requires_independent_rf_or_connector_evidence"\n        out["keypad_spatial_evidence"] = "two_axis_contact_spread" if positional_support else "legacy_detector_no_positions"
    else:
        out["status"] = "elongated_pcb_only"
    out["observations"] = [
        "elongated full-board shape measured by physical fingerprint",
        "repeated keypad-contact bank" if out["handset_contact_layout"] else "keypad pattern not corroborated",
    ]
    return out
