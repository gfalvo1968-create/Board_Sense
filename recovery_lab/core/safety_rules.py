"""Shared safety policy for Recovery Lab guidance."""

HAZARDOUS_LABS = {"gold", "silver", "processors", "gold_fingers", "relays_contacts"}


def classify_recovery_risk(labs):
    keys = {lab.get("key") for lab in labs}
    hazardous = sorted(keys & HAZARDOUS_LABS)

    if hazardous:
        return {
            "level": "controlled_process",
            "hazardous_labs": hazardous,
            "mechanical_guidance": "detailed_allowed",
            "chemical_refining_guidance": "high_level_only",
            "message": "Mechanical sorting and disassembly can be detailed. Chemical/refining recovery should identify hazards and professional/refinery options rather than provide unsafe garage-scale recipes.",
        }

    return {
        "level": "mechanical",
        "hazardous_labs": [],
        "mechanical_guidance": "detailed_allowed",
        "chemical_refining_guidance": "not_applicable",
        "message": "Primary workflow is mechanical sorting, separation, and sale/recovery comparison.",
    }
