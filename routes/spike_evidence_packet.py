"""Build a compact evidence packet for SPIKE decisions and future Web Scout."""

from routes.decision_guard import strong_structural_family
from routes.web_scout import web_scout_packet


def build_evidence_packet(result, identifiers=None, web_matches=None):
    structural = strong_structural_family(result)
    anchors = structural.get("anchors", []) if structural else []
    board_type = result.get("board_type", "Unknown Board")
    return {
        "spike_decision_authority": True,
        "physical_board_first": True,
        "structural_evidence": structural,
        "web_scout": web_scout_packet(
            board_type=board_type,
            identifiers=identifiers or [],
            structural_anchors=anchors,
            matches=web_matches,
        ),
        "policy": (
            "A web match may identify the board's origin, manufacturer, model, or revision, "
            "but SPIKE decides the current physical board classification after checking for alterations."
        ),
    }
