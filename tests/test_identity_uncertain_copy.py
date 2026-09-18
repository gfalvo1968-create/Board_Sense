from unittest.mock import patch

from routes.case_reasoner import reconcile_case


def _minimal_view():
    return {
        "board_type": "Power-Control / Controller Board",
        "confidence": 82,
        "signals": {},
        "board_blueprint": {"frame_identity_gate": {"block_analysis": False}},
        "physical_fingerprint": {
            "coverage": "detail_or_partial_view",
            "geometry_quality": "low",
        },
    }


@patch("routes.case_reasoner.verify_same_board")
def test_identity_uncertain_is_not_called_multiple_boards(mock_identity):
    mock_identity.return_value = {
        "status": "IDENTITY_UNCERTAIN",
        "same_board": None,
        "block_reconciliation": True,
        "whole_view_count": 0,
        "identity_next_step": "Add one clear full-board photo showing the complete outline, mounting holes, and major connector positions.",
        "reasons": ["No uploaded view provides usable whole-board geometry for identity verification."],
    }

    result = reconcile_case([_minimal_view(), _minimal_view()])

    assert result["status"] == "case_identity_clarification"
    assert result["board_type"] == "Identity Evidence Needed"
    assert result["same_board_verification"]["status"] == "IDENTITY_UNCERTAIN"
    assert result["three_answers"]["identity"]["answer"] == "Identity Evidence Needed"
    assert result["three_answers"]["recovery"]["grade"] == "CASE COMBINATION WITHHELD"


@patch("routes.case_reasoner.verify_same_board")
def test_confirmed_multi_board_stop_keeps_case_split_wording(mock_identity):
    mock_identity.return_value = {
        "status": "MULTIPLE_BOARDS_IN_FRAME_SUSPECTED",
        "same_board": False,
        "block_reconciliation": True,
        "reasons": ["Two independently substantial PCB-like regions are visible in the same photograph."],
    }

    result = reconcile_case([_minimal_view(), _minimal_view()])

    assert result["status"] == "case_identity_failed"
    assert result["board_type"] == "Multiple Boards / Case Split Required"
    assert result["three_answers"]["identity"]["answer"] == "Multiple Boards / Case Split Required"
