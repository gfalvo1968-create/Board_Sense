"""Dark, notched PCB candidate regressions for the SPIKE object gate.

These fixtures are synthetic and do not assert any particular scrap grade.
"""
import unittest
import os
from pathlib import Path
import cv2
import numpy as np

from routes.object_gate import _localized_pcb_evidence, classify_object


class DarkIrregularPCBTests(unittest.TestCase):
    def test_dark_notched_surface_with_distributed_components_is_supported(self):
        image = np.full((800, 800, 3), 215, dtype=np.uint8)
        # Long notched shape: the board is far from rectangular.
        polygon = np.array([
            (110, 80), (620, 80), (620, 180), (500, 180),
            (500, 520), (640, 520), (640, 720), (380, 720),
            (380, 620), (260, 620), (260, 220), (110, 220)
        ], dtype=np.int32)
        cv2.fillPoly(image, [polygon], (27, 27, 27))
        # Repeated small pads and routed component edges on the PCB surface.
        for y in range(240, 585, 16):
            for x in range(275, 475, 16):
                cv2.rectangle(image, (x, y), (x + 6, y + 6),
                              (200, 200, 200), -1)
        components = {
            "regions": [
                {"type": "IC-like package", "x": 330, "y": 300, "w": 32, "h": 32},
                {"type": "IC-like package", "x": 400, "y": 410, "w": 32, "h": 32},
            ],
            "solder_side_likelihood": 0,
            "solder_joint_like": 0,
            "contact_pad_like": 0,
            "contact_pattern_score": 0,
        }
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 55, 145)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        evidence = _localized_pcb_evidence(hsv, edges, components)
        self.assertTrue(evidence["supported"], evidence)
        self.assertGreaterEqual(evidence["supported_local_packages"], 2)

    def test_empty_dark_chassis_with_fans_does_not_rescue_as_pcb(self):
        image = np.full((800, 800, 3), 215, dtype=np.uint8)
        cv2.rectangle(image, (95, 95), (705, 705), (32, 32, 32), -1)
        # Fan rings, vents, and screw heads are not populated PCB evidence.
        for cy in (250, 560):
            cv2.circle(image, (440, cy), 108, (65, 65, 65), -1)
            cv2.circle(image, (440, cy), 76, (18, 18, 18), -1)
            cv2.circle(image, (440, cy), 35, (105, 105, 105), 5)
        for y in range(150, 670, 24):
            for x in (145, 185):
                cv2.rectangle(image, (x, y), (x + 8, y + 10),
                              (185, 185, 185), -1)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 55, 145)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        evidence = _localized_pcb_evidence(hsv, edges, {
            "regions": [], "solder_side_likelihood": 0,
            "solder_joint_like": 0, "contact_pad_like": 0,
            "contact_pattern_score": 0,
        })
        self.assertFalse(evidence["supported"], evidence)

    def test_optional_private_laptop_photo_routes_as_board(self):
        """Opt-in real specimen; never commit private operator photographs."""
        image_path = os.environ.get("BOARD_SENSE_LAPTOP_PCB_PHOTO")
        if not image_path:
            self.skipTest("Private laptop PCB specimen not configured")
        self.assertTrue(Path(image_path).is_file())
        result = classify_object(image_path)
        self.assertEqual(result["mode"], "board", result)
        self.assertNotEqual(result["label"], "Speaker / audio driver")

    def test_plain_dark_sheet_remains_unconfirmed(self):
        image = np.full((800, 800, 3), 215, dtype=np.uint8)
        cv2.rectangle(image, (100, 100), (680, 680), (27, 27, 27), -1)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 55, 145)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        evidence = _localized_pcb_evidence(hsv, edges, {"regions": []})
        self.assertFalse(evidence["supported"], evidence)


if __name__ == "__main__":
    unittest.main()
