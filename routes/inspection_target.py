"""Target-aware SPIKE inspection context.

This layer never changes ordinary board grading. It only tells SPIKE whether the
current generic visual recognition actually supports the inspection mission that
came from Scrap Radar.
"""
import json

SOURCE_SUPPORT = {
    "hard-drive": ("magnet", "actuator", "hard drive", "voice coil"),
    "speaker": ("speaker", "magnet", "voice coil"),
    "motor": ("motor", "rotor", "magnet", "generator"),
    "nimh": ("nimh", "battery", "pack", "cell"),
    "li-ion": ("lithium", "li-ion", "battery", "pack", "cell"),
    "display": ("display", "touchscreen", "screen", "led", "phosphor"),
    "semiconductor": ("ic / logic", "semiconductor", "rf", "power", "logic package"),
    "capacitors": ("capacitor", "tantalum"),
    "carbide": ("carbide", "tool", "insert", "tungsten"),
    "solar": ("solar", "photovoltaic", "module"),
    "optics": ("optic", "laser", "fiber"),
    "alloy": ("alloy", "solder"),
}


def parse_inspection_target(raw):
    if not raw:
        return None
    if isinstance(raw, dict):
        packet = raw
    else:
        try:
            packet = json.loads(raw)
        except Exception:
            return None
    if not isinstance(packet, dict) or not packet.get("target"):
        return None
    return packet


def _text(*values):
    return " ".join(str(v or "") for v in values).lower()


def apply_inspection_target(result, packet):
    packet = parse_inspection_target(packet)
    if not packet:
        return result

    spike = result.get("spike_glass") or {}
    top = spike.get("top_match") or {}
    source_id = str(packet.get("sourceId") or "").strip()
    source_name = str(packet.get("sourceName") or "Scrap Radar source")
    target = str(packet.get("target") or "Saved inspection target")
    haystack = _text(
        top.get("label"),
        top.get("family"),
        result.get("board_type"),
        (result.get("object_gate") or {}).get("label"),
    )
    support_terms = SOURCE_SUPPORT.get(source_id, ())
    supported = bool(support_terms and any(term in haystack for term in support_terms))

    if supported:
        status = "target_candidate"
        message = (
            "Current visual recognition overlaps the saved inspection mission. "
            "Treat this as a target candidate only; composition and recoverable mass remain unproven."
        )
    else:
        status = "target_not_confirmed"
        generic = top.get("label") or result.get("board_type") or "generic visual features"
        message = (
            f"Current image produced generic recognition '{generic}', but that does not confirm "
            f"the saved target '{target}'. Reframe closer on the target area and include enough "
            "surrounding context to place it on the item."
        )

    target_result = {
        "status": status,
        "source_id": source_id,
        "source_name": source_name,
        "target": target,
        "where": packet.get("where") or "",
        "look": packet.get("look") or "",
        "preserve": packet.get("preserve") or "",
        "watch": packet.get("watch") or "",
        "materials": packet.get("materials") if isinstance(packet.get("materials"), list) else [],
        "message": message,
        "generic_top_match": {
            "label": top.get("label"),
            "family": top.get("family"),
            "confidence": spike.get("confidence"),
        },
        "rule": "Inspection context can narrow what SPIKE is trying to confirm, but it cannot manufacture visual evidence, composition, recoverable mass, or cash value.",
    }
    result["inspection_target"] = target_result
    spike["target_mode"] = True
    spike["target_status"] = status
    spike["target_name"] = target
    result["spike_glass"] = spike
    return result
