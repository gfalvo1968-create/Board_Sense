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
from routes.case_reasoner import reconcile_case
from routes.decision_guard import condition_harvest_check
from routes.board_fingerprint import extract_board_fingerprint
from routes.frame_identity_gate import inspect_frame
from routes.frame_plane_gate import inspect_secondary_board_plane
from routes.spike_tool_layer import investigate_identity
from routes.identity_clarification import _match_targeted_continuity


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


def test_long_narrow_isolated_full_board_counts_as_whole_view():
    """A complete long/narrow PCB must not be demoted just because it uses little frame area."""
    image = np.zeros((2000, 1500, 3), dtype=np.uint8)
    image[:] = (35, 35, 35)
    green = (45, 150, 55)
    # Complete tall/narrow board with clear margin on all four sides.
    cv2.rectangle(image, (540, 280), (960, 1720), green, -1)
    # Add component-like texture without changing the physical outline.
    for y in range(360, 1650, 120):
        cv2.circle(image, (700, y), 18, (190, 190, 190), -1)
        cv2.rectangle(image, (760, y - 20), (850, y + 20), (70, 70, 70), -1)
    temp, path = _write_fixture(image)
    try:
        fp = extract_board_fingerprint(str(path))
    finally:
        temp.cleanup()
    assert fp["board_area_ratio"] < .22, fp
    assert fp["frame_edge_contacts"] == 0, fp
    assert fp["isolated_full_outline"] is True, fp
    assert fp["coverage"] == "whole_or_large_view", fp
    assert fp["geometry_quality"] in {"medium", "good"}, fp


def test_long_narrow_partial_sliver_touching_frame_stays_partial():
    """The narrow-board exception must not promote a cropped sliver to whole-board evidence."""
    image = np.zeros((2000, 1500, 3), dtype=np.uint8)
    image[:] = (35, 35, 35)
    green = (45, 150, 55)
    # Same kind of narrow PCB, but cropped by the top frame edge.
    cv2.rectangle(image, (540, 0), (960, 900), green, -1)
    temp, path = _write_fixture(image)
    try:
        fp = extract_board_fingerprint(str(path))
    finally:
        temp.cleanup()
    assert fp["frame_edge_contacts"] >= 1, fp
    assert fp["isolated_full_outline"] is False, fp
    assert fp["coverage"] == "detail_or_partial_view", fp


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


def test_bottleneck_only_frame_requests_targeted_photo_instead_of_claiming_multiple_boards():
    flagged = _result(frame_block=False, fp_id="dell")
    flagged["board_blueprint"]["frame_identity_gate"] = {
        "block_analysis": True,
        "confidence": 96,
        "status": "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED",
        "metrics": {
            "base_two_region_trigger": False,
            "bottleneck_split_trigger": True,
            "multiscale_split_trigger": False,
            "bottleneck_split_metrics": {
                "axis": "y",
                "cut": 2145,
                "neck_ratio": 0.351,
                "side_balance": 0.472,
            },
        },
    }
    companion = _result(frame_block=False, fp_id="dell")
    decision = verify_same_board([flagged, companion])
    assert decision["status"] == "IDENTITY_CLARIFICATION_NEEDED"
    assert decision["same_board"] is None
    assert decision["block_reconciliation"] is True
    assert decision["clarification_needed"] is True
    assert decision["requested_photos"][0]["flagged_view"] == 1
    assert "SAME SIDE" in decision["requested_photos"][0]["instruction"]
    assert "bottleneck alone is not proof" in decision["rule"].lower()


def test_independent_region_frame_remains_hard_block():
    flagged = _result(frame_block=False, fp_id="board-a")
    flagged["board_blueprint"]["frame_identity_gate"] = {
        "block_analysis": True,
        "confidence": 96,
        "status": "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED",
        "metrics": {
            "base_two_region_trigger": True,
            "bottleneck_split_trigger": False,
            "multiscale_split_trigger": False,
        },
    }
    companion = _result(frame_block=False, fp_id="board-a")
    decision = verify_same_board([flagged, companion])
    assert decision["status"] == "MULTIPLE_BOARDS_IN_FRAME_SUSPECTED"
    assert decision["same_board"] is False
    assert decision["block_reconciliation"] is True
    assert decision["clarification_needed"] is False


def test_resolved_targeted_closeup_clears_bottleneck_only_case_block():
    flagged = _result(frame_block=False, fp_id="dell")
    flagged["board_blueprint"]["frame_identity_gate"] = {
        "block_analysis": True,
        "confidence": 96,
        "status": "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED",
        "metrics": {
            "base_two_region_trigger": False,
            "bottleneck_split_trigger": True,
            "multiscale_split_trigger": False,
            "bottleneck_split_metrics": {"axis": "y", "cut": 300},
        },
    }
    flagged["identity_clarification_evidence"] = {
        "resolved": True,
        "matched_candidate_view": 2,
        "status": "resolved",
    }
    companion = _result(frame_block=False, fp_id="dell")
    decision = verify_same_board([flagged, companion])
    assert decision["status"] == "PROBABLY_SAME_BOARD"
    assert decision["same_board"] is True
    assert decision["block_reconciliation"] is False


def test_targeted_closeup_matcher_requires_same_side_features_across_neck():
    rng = np.random.default_rng(7)
    image = np.zeros((720, 920, 3), dtype=np.uint8)
    image[:] = (35, 35, 35)
    green = (45, 150, 55)
    cv2.rectangle(image, (90, 80), (830, 640), green, -1)
    # Make an irregular narrow-neck silhouette around y=360.
    cv2.rectangle(image, (90, 315), (260, 405), (35, 35, 35), -1)
    cv2.rectangle(image, (660, 315), (830, 405), (35, 35, 35), -1)
    for _ in range(180):
        x = int(rng.integers(150, 770))
        y = int(rng.integers(160, 560))
        radius = int(rng.integers(2, 7))
        value = int(rng.integers(80, 245))
        cv2.circle(image, (x, y), radius, (value, value, value), -1)
    cv2.putText(image, "DELL-TEST-NECK", (300, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (240, 240, 240), 2, cv2.LINE_AA)

    closeup = image[230:500, 220:700].copy()
    unrelated = np.zeros_like(closeup)
    unrelated[:] = (35, 35, 35)
    cv2.rectangle(unrelated, (20, 20), (460, 250), green, -1)
    for _ in range(100):
        x = int(rng.integers(30, 450))
        y = int(rng.integers(30, 240))
        cv2.circle(unrelated, (x, y), 3, (180, 180, 180), -1)

    with TemporaryDirectory() as td:
        full_path = Path(td) / "full.png"
        close_path = Path(td) / "close.png"
        other_path = Path(td) / "other.png"
        cv2.imwrite(str(full_path), image)
        cv2.imwrite(str(close_path), closeup)
        cv2.imwrite(str(other_path), unrelated)
        bottleneck = {"axis": "y", "cut": 360}
        good = _match_targeted_continuity(str(full_path), str(close_path), bottleneck)
        bad = _match_targeted_continuity(str(full_path), str(other_path), bottleneck)

    assert good["matched"] is True, good
    assert good["matches_side_a"] >= 4 and good["matches_side_b"] >= 4, good
    assert bad["matched"] is False, bad


def test_overlapping_secondary_rectangular_pcb_plane_is_blocked():
    """A second PCB tucked under a rectangular main board must not merge as one."""
    image = np.zeros((900, 1100, 3), dtype=np.uint8)
    image[:] = (45, 45, 45)
    green = (45, 150, 55)

    # Smaller PCB first, then the main PCB on top. This preserves the main
    # board's physical edge across the overlap, matching the real gremlin setup.
    cv2.rectangle(image, (430, 700), (700, 875), green, -1)
    cv2.rectangle(image, (430, 700), (700, 875), (15, 90, 25), 5)

    # Main rectangular motherboard overlaps the upper section of the small PCB.
    cv2.rectangle(image, (140, 150), (960, 760), green, -1)
    # Strong physical outer edge on the main board remains visible across the
    # secondary PCB underneath it.
    cv2.rectangle(image, (140, 150), (960, 760), (15, 90, 25), 5)
    # A small physical shadow/gap under the overlapping board edge makes the
    # separate plane visible without creating a second huge disconnected blob.
    cv2.rectangle(image, (430, 761), (700, 773), (35, 35, 35), -1)

    # Add board-like texture so Canny/Hough sees realistic internal detail too.
    for x in range(180, 930, 55):
        cv2.line(image, (x, 190), (x, 710), (70, 185, 85), 2)
    for y in range(735, 855, 28):
        cv2.line(image, (455, y), (675, y), (70, 185, 85), 2)

    temp, path = _write_fixture(image)
    try:
        decision = inspect_frame(str(path))
    finally:
        temp.cleanup()

    diagnostic = f"secondary-plane decision={decision!r}"
    print("\nSPIKE SECONDARY PLANE DIAGNOSTIC:", diagnostic)
    assert decision["block_analysis"] is True, diagnostic
    assert decision["status"] == "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED", diagnostic
    assert decision["metrics"]["secondary_plane_trigger"] is True, diagnostic


def test_secondary_plane_detector_does_not_replace_dell_bottleneck_clarification():
    """Bottleneck-only ambiguity must remain clarification, not a hard plane split."""
    flagged = _result(frame_block=False, fp_id="dell")
    flagged["board_blueprint"]["frame_identity_gate"] = {
        "block_analysis": True,
        "confidence": 96,
        "status": "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED",
        "metrics": {
            "base_two_region_trigger": False,
            "bottleneck_split_trigger": True,
            "multiscale_split_trigger": False,
            "secondary_plane_trigger": False,
            "bottleneck_split_metrics": {"axis": "y", "cut": 2145},
        },
    }
    companion = _result(frame_block=False, fp_id="dell")
    decision = verify_same_board([flagged, companion])
    assert decision["status"] == "IDENTITY_CLARIFICATION_NEEDED"
    assert decision["same_board"] is None
    assert decision["block_reconciliation"] is True


def test_confirmed_missing_fingers_can_still_leave_pay_dirt():
    """Missing value-bearing material changes condition, not automatically the remaining-value class."""
    result = {
        "board_type": "Dense Logic Board",
        "grade": "MEDIUM",
        "score": 12,
        "signals": {
            "large_ic_chips": True,
            "dense_component_board": True,
            "processor": False,
            "gold_fingers": False,
            "gold_finger_edge": False,
        },
    }
    observations = {
        "gold_finger_edge": {
            "status": "missing_confirmed",
            "value_impact": "high",
            "note": "Edge-finger section is visibly removed from the specimen.",
        }
    }
    condition = condition_harvest_check(result, observations)
    assert condition["specimen_completeness"] == "INCOMPLETE / CONFIRMED MATERIAL MISSING"
    assert condition["condition"] == "PARTIALLY HARVESTED"
    assert condition["remaining_value_verdict"] == "PAY DIRT"
    assert condition["pay_dirt_still_present"] is True
    assert "price what remains" in condition["buyer_message"].lower()
    assert condition["condition_adjustment_required"] is True


def test_identity_uncertainty_does_not_silence_per_view_material_value():
    """SPIKE may refuse to merge identities, but should still report usable material evidence per view."""
    views = [
        _result("Dense Logic Board", fp_id="a"),
        _result("Dense Logic Board", fp_id="b"),
    ]
    for view in views:
        view["grade"] = "MEDIUM"
        view["score"] = 12
        view["signals"].update({"dense_component_board": True, "large_ic_chips": True})
        view["modification_intelligence"] = {
            "observations": {
                "gold_finger_edge": {
                    "status": "missing_confirmed",
                    "value_impact": "high",
                    "note": "Visible harvested edge.",
                }
            }
        }

    identity = {
        "status": "IDENTITY_UNCERTAIN",
        "same_board": None,
        "block_reconciliation": True,
        "identity_next_step": "Add one genuinely new whole-board view.",
    }
    with patch("routes.case_reasoner.verify_same_board", return_value=identity):
        combined = reconcile_case(views)

    assert combined["status"] == "case_identity_clarification"
    assert len(combined["per_view_material_analysis"]) == 2
    assert all(x["remaining_value_verdict"] == "PAY DIRT" for x in combined["per_view_material_analysis"])
    assert all(x["pay_dirt_still_present"] is True for x in combined["per_view_material_analysis"])
    recovery = combined["three_answers"]["recovery"]
    assert recovery["grade"] == "CASE COMBINATION WITHHELD"
    assert recovery["per_view_material_analysis_available"] is True
    assert "still reports" in recovery["message"].lower()


def test_brown_phenolic_board_on_dark_background_counts_as_whole_view():
    """A non-green component side can still be a genuine full-board identity view."""
    image = np.full((1000, 800, 3), (35, 35, 35), dtype=np.uint8)
    pts = np.array([[180,120],[570,120],[650,230],[650,780],[520,900],[210,900],[135,720],[135,240]], np.int32)
    cv2.fillPoly(image,[pts],(72,88,105))
    cv2.polylines(image,[pts],True,(125,145,165),5)
    # Mechanical/through-hole features.
    for x,y in [(240,210),(535,220),(220,760),(540,760)]:
        cv2.circle(image,(x,y),24,(18,18,18),-1)
    cv2.rectangle(image,(260,420),(410,485),(20,20,20),-1)
    cv2.circle(image,(500,525),70,(220,220,220),-1)
    temp,path=_write_fixture(image)
    try:
        fp=extract_board_fingerprint(str(path))
    finally:
        temp.cleanup()
    assert fp["available"] is True, fp
    assert fp["coverage"] == "whole_or_large_view", fp
    assert fp["coverage_basis"] in {"background_contrast","edge_contour"}, fp


def test_plain_dark_background_alone_does_not_become_whole_board():
    """Background-contrast fallback must not hallucinate a PCB from fabric-like shading."""
    image=np.full((900,700,3),(40,40,40),dtype=np.uint8)
    cv2.rectangle(image,(0,300),(700,520),(48,48,48),-1)
    temp,path=_write_fixture(image)
    try:
        fp=extract_board_fingerprint(str(path))
    finally:
        temp.cleanup()
    assert fp["coverage"] != "whole_or_large_view", fp
