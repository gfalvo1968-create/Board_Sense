"""Dark, notched PCB candidate regressions for the SPIKE object gate.

These fixtures are synthetic and do not assert any particular scrap grade.
"""
import unittest
import os
import tempfile
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

    def _classify_pixels(self, image):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "case.png"
            cv2.imwrite(str(filename), image)
            return classify_object(str(filename))

    def test_complete_classifier_accepts_dark_populated_notched_pcb(self):
        image = np.full((900, 800, 3), 215, dtype=np.uint8)
        shape = np.array([
            (130, 80), (600, 80), (600, 230), (525, 230),
            (525, 660), (665, 660), (665, 835), (295, 835),
            (295, 690), (255, 690), (255, 250), (130, 250),
        ], dtype=np.int32)
        cv2.fillPoly(image, [shape], (26, 26, 26))
        # A deliberately populated component face, not a plain black shape.
        # Replicate IC bodies with contrasting pin banks along two edges.
        for x, y in ((300, 310), (400, 410), (310, 525), (430, 580)):
            cv2.rectangle(image, (x, y), (x + 62, y + 42), (8, 8, 8), -1)
            for delta in range(0, 56, 7):
                cv2.rectangle(image, (x + delta, y - 5), (x + delta + 3, y + 4), (185, 185, 185), -1)
                cv2.rectangle(image, (x + delta, y + 39), (x + delta + 3, y + 47), (185, 185, 185), -1)
        for y in range(260, 650, 18):
            for x in (280, 288, 510):
                cv2.rectangle(image, (x, y), (x + 4, y + 5), (205, 205, 205), -1)
        # Fine traces are what make this a PCB rather than a smooth dark cutout.
        # Keep traces thin and confined to the synthetic board interior.
        for x in range(270, 515, 12):
            cv2.line(image, (x, 265), (x, 635), (125, 125, 125), 1)
        for y in range(270, 640, 15):
            cv2.line(image, (270, y), (515, y), (135, 135, 135), 1)
        # Discrete solder spots between traces, kept distinct from the fine lines.
        for y in range(282, 625, 23):
            for x in range(281, 505, 21):
                cv2.circle(image, (x, y), 3, (240, 240, 240), -1)
        result = self._classify_pixels(image)
        self.assertEqual(result["mode"], "board", result)

    def test_complete_classifier_rejects_plain_dark_sheet(self):
        image = np.full((800, 800, 3), 215, dtype=np.uint8)
        cv2.rectangle(image, (110, 110), (690, 690), (27, 27, 27), -1)
        result = self._classify_pixels(image)
        self.assertNotEqual(result["mode"], "board", result)

    def test_complete_classifier_rejects_empty_fan_chassis(self):
        image = np.full((800, 800, 3), 215, dtype=np.uint8)
        cv2.rectangle(image, (95, 95), (705, 705), (32, 32, 32), -1)
        for cy in (250, 560):
            cv2.circle(image, (440, cy), 108, (65, 65, 65), -1)
            cv2.circle(image, (440, cy), 76, (18, 18, 18), -1)
            cv2.circle(image, (440, cy), 35, (105, 105, 105), 5)
        result = self._classify_pixels(image)
        self.assertNotEqual(result["mode"], "board", result)

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
