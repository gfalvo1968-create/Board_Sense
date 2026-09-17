"""Cost guardrails for SPIKE identity tool use."""
from unittest.mock import patch

from routes.spike_tool_layer import investigate_identity


def _partial_result(view_number):
    return {
        "view_number": view_number,
        "board_type": "Power-Control / Controller Board",
        "confidence": 82,
        "physical_fingerprint": {
            "coverage": "detail_or_partial_view",
            "geometry_quality": "low",
        },
    }


@patch("routes.spike_tool_layer.search_visual_matches")
def test_zero_whole_board_views_do_not_spend_web_searches(web_match):
    results = [_partial_result(1), _partial_result(2), _partial_result(3)]
    identity = {
        "status": "IDENTITY_UNCERTAIN",
        "same_board": None,
        "block_reconciliation": True,
        "whole_view_count": 0,
        "identity_next_step": (
            "Add one clear full-board photo showing the complete outline, "
            "mounting holes, and major connector positions."
        ),
    }

    packet = investigate_identity(
        results,
        ["/tmp/photo1.jpg", "/tmp/photo2.jpg", "/tmp/photo3.jpg"],
        identity,
    )

    web_match.assert_not_called()
    assert packet["status"] == "identity_photo_needed"
    assert packet["web_reference_searches"] == []
    assert "spike_glass_web_match" not in packet["tools_used"]
    assert packet["identity_override"] is False
    assert "new identity photo" in packet["note"].lower()
