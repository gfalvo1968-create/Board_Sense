"""Dark, notched PCB candidate regressions for the SPIKE object gate.

These fixtures are synthetic and do not assert any particular scrap grade.
"""
import unittest
import cv2
import numpy as np

from routes.object_gate import _localized_pcb_evidence


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
        for y in range(265, 570, 20):
            for x in (288, 318, 348, 378, 408, 438):
                cv2.rectangle(image, (x, y), (x + 7, y + 6),
                              (165, 165, 165), -1)
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
