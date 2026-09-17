"""Regression guardrail for two distinct PCBs touching edge-to-edge."""
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from routes.frame_identity_gate import inspect_frame


def _write_fixture(image):
    temp = TemporaryDirectory()
    path = Path(temp.name) / "fixture.png"
    cv2.imwrite(str(path), image)
    return temp, path


def test_two_distinct_pcbs_touching_edge_to_edge_are_blocked():
    """Two board planes that meet at an edge must not reconcile as one PCB."""
    image = np.zeros((900, 1200, 3), dtype=np.uint8)
    image[:] = (215, 205, 190)

    # Left PCB body.
    cv2.rectangle(image, (210, 250), (520, 690), (45, 150, 55), -1)
    cv2.rectangle(image, (210, 250), (520, 690), (18, 80, 28), 5)
    for x in range(245, 500, 42):
        cv2.line(image, (x, 285), (x, 650), (82, 185, 92), 2)

    # Right PCB body: different proportions/color, touching the left edge-to-edge.
    cv2.rectangle(image, (520, 165), (705, 760), (58, 125, 66), -1)
    cv2.rectangle(image, (520, 165), (705, 760), (20, 72, 30), 5)
    for y in range(205, 730, 44):
        cv2.line(image, (550, y), (675, y), (95, 170, 105), 2)

    temp, path = _write_fixture(image)
    try:
        decision = inspect_frame(str(path))
    finally:
        temp.cleanup()

    diagnostic = f"edge-touching decision={decision!r}"
    print("\nSPIKE EDGE-TOUCHING DIAGNOSTIC:", diagnostic)
    assert decision["block_analysis"] is True, diagnostic
    assert decision["status"] == "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED", diagnostic
    metrics = decision.get("metrics") or {}
    plane = metrics.get("secondary_plane_metrics") or {}
    adjacent = plane.get("adjacent_edge_plane_check") or {}
    assert adjacent.get("trigger") is True, diagnostic


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
