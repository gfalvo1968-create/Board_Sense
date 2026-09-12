"""Permanent regression guardrails for SPIKE board identity.

These tests protect the decision contract learned from Public-Proofing:
1) coherent views of one board must not be split just because semantic labels differ;
2) a 2+2+2 mixed-board case must never be reconciled as one board;
3) a photo already flagged as containing multiple boards must stop reconciliation.

The fingerprints below are synthetic fixtures. The photographed Archer C54 and Chaos
cases remain the required live acceptance tests before production deployment.
"""
from unittest.mock import patch

from routes.case_identity_gate import verify_same_board


def _result(board_type="Dense Logic Board", frame_block=False, fp_id="a"):
    return {
        "board_type": board_type,
        "confidence": 90,
        "signals": {"large_ic_chips": True},
        "physical_fingerprint": {
            "coverage": "whole_or_large_view",
            "geometry_quality": "good",
            "fixture_id": fp_id,
        },
        "board_blueprint": {
            "frame_identity_gate": {
                "block_analysis": frame_block,
                "confidence": 96 if frame_block else 0,
            }
        },
    }


def _fixture_compare(a, b):
    """Synthetic physical comparison used only by these regression tests."""
    same = a.get("fixture_id") == b.get("fixture_id")
    return {
        "conflict": not same,
        "confidence": 94 if not same else 90,
        "reason": "synthetic regression fixture",
    }


@patch("routes.case_identity_gate.fingerprint_conflict", side_effect=_fixture_compare)
def test_archer_style_same_board_survives_semantic_disagreement(_cmp):
    # Same physical board, but close-ups may receive different semantic labels.
    views = [
        _result("Dense Logic Board", fp_id="archer"),
        _result("Control Board", fp_id="archer"),
        _result("Dense Logic Board", fp_id="archer"),
        _result("Control Board", fp_id="archer"),
        _result("Dense Logic Board", fp_id="archer"),
        _result("Control Board", fp_id="archer"),
    ]
    decision = verify_same_board(views)
    assert decision["status"] == "PROBABLY_SAME_BOARD"
    assert decision["same_board"] is True
    assert decision["block_reconciliation"] is False
    assert decision["coherent_geometry"] is True


@patch("routes.case_identity_gate.fingerprint_conflict", side_effect=_fixture_compare)
def test_chaos_2_plus_2_plus_2_never_reconciles_as_one_board(_cmp):
    # Two views each from three different physical boards.
    views = [
        _result("Dense Logic Board", fp_id="board-a"),
        _result("Dense Logic Board", fp_id="board-a"),
        _result("Control Board", fp_id="board-b"),
        _result("Control Board", fp_id="board-b"),
        _result("Power Board", fp_id="board-c"),
        _result("Power Board", fp_id="board-c"),
    ]
    decision = verify_same_board(views)
    assert decision["status"] in {"MULTIPLE_BOARDS_SUSPECTED", "IDENTITY_UNCERTAIN"}
    assert decision["same_board"] is not True
    assert decision["block_reconciliation"] is True


def test_two_boards_in_one_photo_stops_before_reconciliation():
    views = [
        _result(frame_block=True, fp_id="board-a"),
        _result(fp_id="board-a"),
    ]
    decision = verify_same_board(views)
    assert decision["status"] == "MULTIPLE_BOARDS_IN_FRAME_SUSPECTED"
    assert decision["same_board"] is False
    assert decision["block_reconciliation"] is True
