"""Build SPIKE's verification-first evidence packet.

Identity is not value. A label, visual resemblance, or web match can establish a
hypothesis, but purchase value is based on independently verified physical
condition and the recoverable features that remain.
"""

from routes.decision_guard import strong_structural_family, condition_harvest_check
from routes.web_scout import web_scout_packet


def build_evidence_packet(result, identifiers=None, web_matches=None, condition_observations=None):
    structural = strong_structural_family(result)
    anchors = structural.get("anchors", []) if structural else []
    board_type = result.get("board_type", "Unknown Board")
    condition = condition_harvest_check(result, condition_observations)
    return {
        "spike_decision_authority": True,
        "physical_board_first": True,
        "verification_doctrine": {
            "rule": "Never price from a label or reference alone. Verify value-bearing evidence independently.",
            "sequence": [
                "claim_or_identity",
                "physical_inspection",
                "independent_verification",
                "alteration_and_harvest_check",
                "remaining_value",
                "quantity_exposure",
                "buy_decision",
            ],
        },
        "structural_evidence": structural,
        "condition_and_harvest": condition,
        "web_scout": web_scout_packet(
            board_type=board_type,
            identifiers=identifiers or [],
            structural_anchors=anchors,
            matches=web_matches,
        ),
        "policy": (
            "A web match may identify the board's origin, manufacturer, model, or revision, "
            "but SPIKE decides the current physical classification and purchase condition."
        ),
    }
