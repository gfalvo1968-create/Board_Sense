"""Permanent regression guardrails for SPIKE board identity.

These tests protect the decision contract learned from Public-Proofing:
1) coherent views of one board must not be split just because semantic labels differ;
2) a 2+2+2 mixed-board case must never be reconciled as one board;
3) a photo already flagged as containing multiple boards must stop reconciliation;
4) a single clean rectangular PCB must not be blocked by the frame gate;
5) two touching PCB bodies connected by a narrow bridge must be blocked;
6) one irregular smartphone PCB with narrow arms/notches must remain one board.

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
from routes.spike_tool_layer import investigate_identity


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
    assert decision["block_analysis"] is False, f"clean PCB unexpectedly blocked: {decision!r}"
    assert decision["status"] == "SINGLE_BOARD_NOT_CONTRADICTED"


def test_touching_two_board_frame_is_blocked():
    image = np.zeros((700, 1000, 3), dtype=np.uint8)
    image[:] = (35, 35, 35)
    cv2.rectangle(image, (390, 120), (900, 610), (45, 150, 55), -1)
    cv2.rectangle(image, (90, 250), (350, 520), (45, 150, 55), -1)
    cv2.rectangle(image, (345, 345), (410, 420), (45, 150, 55), -1)
    temp, path = _write_fixture(image)
    try:
        decision = inspect_frame(str(path))
    finally:
        temp.cleanup()
    diagnostic = f"touching-board decision={decision!r}"
    print("\nSPIKE FRAME DIAGNOSTIC:", diagnostic)
    assert decision["block_analysis"] is True, diagnostic
    assert decision["status"] == "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED", diagnostic
    assert decision["metrics"]["bottleneck_split_trigger"] is True, diagnostic


def test_irregular_smartphone_single_board_is_not_blocked():
    """One PCB may legitimately have a narrow arm, neck and stepped outline."""
    image = np.zeros((800, 1000, 3), dtype=np.uint8)
    image[:] = (35, 35, 35)
    green = (45, 150, 55)
    # Main phone logic-board body.
    cv2.rectangle(image, (300, 160), (700, 610), green, -1)
    # Legitimate integral PCB arms/projections, deliberately asymmetric.
    cv2.rectangle(image, (210, 245), (330, 355), green, -1)
    cv2.rectangle(image, (670, 430), (790, 515), green, -1)
    # Small edge step/notch geometry common on compact device boards.
    cv2.rectangle(image, (360, 610), (455, 665), green, -1)
    cv2.rectangle(image, (545, 120), (625, 180), green, -1)
    temp, path = _write_fixture(image)
    try:
        decision = inspect_frame(str(path))
    finally:
        temp.cleanup()
    diagnostic = f"smartphone-single-board decision={decision!r}"
    print("\nSPIKE SMARTPHONE DIAGNOSTIC:", diagnostic)
    assert decision["block_analysis"] is False, diagnostic
    assert decision["status"] == "SINGLE_BOARD_NOT_CONTRADICTED", diagnostic


@patch("routes.spike_tool_layer.search_visual_matches")
def test_spike_tool_layer_calls_web_match_without_overriding_identity(web_match):
    web_match.side_effect = [
        {
            "status": "searched",
            "matches": [
                {"title": "Dell Latitude motherboard LA-J371P", "source": "example-a"},
                {"title": "Dell Latitude system board LA-J371P", "source": "example-b"},
            ],
        },
        {
            "status": "searched",
            "matches": [
                {"title": "Dell Latitude motherboard LA-J371P reverse side", "source": "example-c"},
                {"title": "Dell Latitude LA-J371P board", "source": "example-d"},
            ],
        },
    ]
    views = [
        _result("Motherboard / Main Logic Board", fp_id="dell"),
        _result("Motherboard / Main Logic Board", fp_id="dell"),
    ]
    views[0]["view_number"] = 1
    views[1]["view_number"] = 2
    identity = {
        "status": "MULTIPLE_BOARDS_IN_FRAME_SUSPECTED",
        "block_reconciliation": True,
    }
    packet = investigate_identity(views, ["/tmp/front.jpg", "/tmp/back.jpg"], identity)
    assert web_match.call_count == 2
    assert "spike_glass_web_match" in packet["tools_used"]
    assert packet["reference_consensus"]["support"] == "reference_corroboration"
    assert packet["identity_override"] is False
    assert "manufacture identity" in packet["rule"].lower()


@patch("routes.spike_tool_layer.search_visual_matches")
def test_spike_web_match_stays_image_first_without_specific_markings(web_match):
    web_match.side_effect = [
        {"status": "searched", "matches": [{"title": "Dell Latitude motherboard", "source": "example"}]},
        {"status": "searched", "matches": [{"title": "Dell Latitude motherboard reverse", "source": "example"}]},
    ]
    views = [
        _result("Power-Control / Controller Board", fp_id="dell"),
        _result("Dense Logic / Controller Board", fp_id="dell"),
    ]
    views[0]["view_number"] = 1
    views[1]["view_number"] = 2
    identity = {"status": "MULTIPLE_BOARDS_IN_FRAME_SUSPECTED", "block_reconciliation": True}
    investigate_identity(views, ["/tmp/front.jpg", "/tmp/back.jpg"], identity)
    first = web_match.call_args_list[0].kwargs
    second = web_match.call_args_list[1].kwargs
    assert first["query"] is None
    assert second["query"] is None


@patch("routes.spike_tool_layer.search_visual_matches")
def test_dell_brand_overlap_counts_as_reference_evidence_not_marketplace_noise(web_match):
    web_match.side_effect = [
        {
            "status": "searched",
            "matches": [
                {"title": "Dell Inspiron 1150 Laptop Intel System Motherboard", "source": "eBay"},
                {"title": "Dell Vostro motherboard", "source": "eBay"},
            ],
        },
        {
            "status": "searched",
            "matches": [
                {"title": "Dell Inspiron motherboard reverse side", "source": "marketplace"},
                {"title": "Dell laptop mainboard", "source": "catalog"},
            ],
        },
    ]
    views = [_result(fp_id="dell"), _result(fp_id="dell")]
    views[0]["view_number"] = 1
    views[1]["view_number"] = 2
    identity = {"status": "MULTIPLE_BOARDS_IN_FRAME_SUSPECTED", "block_reconciliation": True}
    packet = investigate_identity(views, ["/tmp/front.jpg", "/tmp/back.jpg"], identity)
    assert "dell" in packet["reference_consensus"]["common_tokens"]
