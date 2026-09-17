"""Regression guardrails for edge-touching boards and identity evidence floors."""
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from routes.case_identity_gate import verify_same_board
from routes.frame_identity_gate import inspect_frame


def _write_fixture(image):
    temp = TemporaryDirectory()
    path = Path(temp.name) / "fixture.png"
    cv2.imwrite(str(path), image)
    return temp, path


def _partial_result(frame_decision=None):
    return {
        "board_type": "Power-Control / Controller Board",
        "confidence": 82,
        "signals": {},
        "physical_fingerprint": {
            "coverage": "detail_or_partial_view",
            "geometry_quality": "low",
            "aspect_ratio": 1.6,
        },
        "board_blueprint": {
            "frame_identity_gate": frame_decision
            or {
                "block_analysis": False,
                "status": "SINGLE_BOARD_NOT_CONTRADICTED",
                "metrics": {},
            }
        },
    }


def test_two_distinct_pcbs_touching_edge_to_edge_cannot_be_reconciled_without_whole_views():
    """Ambiguous touching boards may be hard-blocked or clarified, but never called same-board."""
    image = np.zeros((900, 1200, 3), dtype=np.uint8)
    image[:] = (215, 205, 190)

    cv2.rectangle(image, (210, 250), (520, 690), (45, 150, 55), -1)
    cv2.rectangle(image, (210, 250), (520, 690), (18, 80, 28), 5)
    for x in range(245, 500, 42):
        cv2.line(image, (x, 285), (x, 650), (82, 185, 92), 2)

    cv2.rectangle(image, (520, 165), (705, 760), (58, 125, 66), -1)
    cv2.rectangle(image, (520, 165), (705, 760), (20, 72, 30), 5)
    for y in range(205, 730, 44):
        cv2.line(image, (550, y), (675, y), (95, 170, 105), 2)

    temp, path = _write_fixture(image)
    try:
        frame = inspect_frame(str(path))
    finally:
        temp.cleanup()

    decision = verify_same_board([_partial_result(frame), _partial_result(frame)])
    diagnostic = f"frame={frame!r} identity={decision!r}"
    print("\nSPIKE EDGE-TOUCHING CASE DIAGNOSTIC:", diagnostic)

    assert decision["status"] != "PROBABLY_SAME_BOARD", diagnostic
    assert decision["same_board"] is not True, diagnostic
    assert decision["block_reconciliation"] is True, diagnostic
    assert decision["status"] in {
        "IDENTITY_UNCERTAIN",
        "MULTIPLE_BOARDS_IN_FRAME_SUSPECTED",
    }, diagnostic


def test_zero_usable_whole_views_requires_identity_clarification():
    """No whole-board geometry means absence of contradiction cannot prove sameness."""
    decision = verify_same_board([_partial_result(), _partial_result(), _partial_result()])
    diagnostic = f"zero-whole decision={decision!r}"
    print("\nSPIKE ZERO-WHOLE-VIEW DIAGNOSTIC:", diagnostic)
    assert decision["status"] == "IDENTITY_UNCERTAIN", diagnostic
    assert decision["same_board"] is None, diagnostic
    assert decision["block_reconciliation"] is True, diagnostic
    assert decision["whole_view_count"] == 0, diagnostic
    assert "full-board" in decision["identity_next_step"].lower(), diagnostic


def test_nested_internal_rectangle_is_not_a_second_board_plane():
    """A large component/shield contained inside one PCB must not look like board #2."""
    image = np.zeros((900, 1200, 3), dtype=np.uint8)
    image[:] = (45, 45, 45)
    green = (45, 150, 55)
    cv2.rectangle(image, (185, 135), (1015, 765), green, -1)
    cv2.rectangle(image, (185, 135), (1015, 765), (18, 80, 28), 5)
    cv2.rectangle(image, (340, 250), (590, 480), (120, 120, 120), -1)
    cv2.rectangle(image, (340, 250), (590, 480), (35, 35, 35), 4)
    for x in range(230, 980, 55):
        cv2.line(image, (x, 560), (x, 710), (75, 180, 85), 2)

    temp, path = _write_fixture(image)
    try:
        decision = inspect_frame(str(path))
    finally:
        temp.cleanup()

    diagnostic = f"nested-feature decision={decision!r}"
    print("\nSPIKE NESTED-FEATURE DIAGNOSTIC:", diagnostic)
    assert decision["block_analysis"] is False, diagnostic
