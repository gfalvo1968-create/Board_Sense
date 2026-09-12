"""Permanent regression guardrails for SPIKE board identity.

These tests protect the decision contract learned from Public-Proofing:
1) coherent views of one board must not be split just because semantic labels differ;
2) a 2+2+2 mixed-board case must never be reconciled as one board;
3) a photo already flagged as containing multiple boards must stop reconciliation;
4) a single clean rectangular PCB must not be blocked by the frame gate;
5) two touching PCB bodies connected by a narrow bridge must be blocked.

The photographed Archer C54 and Chaos cases remain required live acceptance tests
before production deployment.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cv2
import numpy as np

from routes.case_identity_gate import verify_same_board
from routes.frame_identity_gate import inspect_frame


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
    same = a.get("fixture_id") == b.get("fixture_id")
    return {
        "conflict": not same,
        "confidence": 94 if not same else 90,
        "reason": "synthetic regression fixture",
    }


def _write_fixture(image):
    temp = TemporaryDirectory()
    path = Path(temp.name) / "fixture.png"
    cv2.imwrite(str(path), image)
    return temp, path


@patch("routes.case_identity_gate.fingerprint_conflict", side_effect=_fixture_compare)
def test_archer_style_same_board_survives_semantic_disagreement(_cmp):
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


def test_single_clean_pcb_frame_is_not_blocked():
    image = np.zeros((600, 800, 3), dtype=np.uint8)
    image[:] = (40, 40, 40)
    cv2.rectangle(image, (170, 140), (630, 470), (45, 150, 55), -1)
    temp, path = _write_fixture(image)
    try:
        decision = inspect_frame(str(path))
    finally:
        temp.cleanup()
    assert decision["block_analysis"] is False
    assert decision["status"] == "SINGLE_BOARD_NOT_CONTRADICTED"


def test_touching_two_board_frame_is_blocked():
    image = np.zeros((700, 1000, 3), dtype=np.uint8)
    image[:] = (35, 35, 35)
    # Large main board.
    cv2.rectangle(image, (390, 120), (900, 610), (45, 150, 55), -1)
    # Smaller second board on the left.
    cv2.rectangle(image, (90, 250), (350, 520), (45, 150, 55), -1)
    # Narrow physical overlap/bridge that makes the green mask one connected blob.
    cv2.rectangle(image, (345, 345), (410, 420), (45, 150, 55), -1)
    temp, path = _write_fixture(image)
    try:
        decision = inspect_frame(str(path))
    finally:
        temp.cleanup()
    assert decision["block_analysis"] is True
    assert decision["status"] == "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED"
    assert decision["metrics"]["bottleneck_split_trigger"] is True
