"""Regression checks for diagnostic-only visual correspondence.

These tests explicitly forbid photo matching from establishing a physical
identity, even when two photos contain many geometrically aligned features.
"""
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from routes.photo_overlap_diagnostics import examine_photo_overlap


def patterned_board(seed):
    rng = np.random.default_rng(seed)
    image = np.full((700, 1000, 3), 230, dtype=np.uint8)
    cv2.rectangle(image, (80, 60), (910, 640), (28, 47, 55), -1)
    for i in range(230):
        x, y = int(rng.integers(95, 895)), int(rng.integers(75, 625))
        color = tuple(int(v) for v in rng.integers(90, 230, size=3))
        cv2.rectangle(image, (x, y),
                      (x + int(rng.integers(3, 17)), y + int(rng.integers(3, 16))),
                      color, -1)
        cv2.putText(image, str(i), (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.24, (230, 230, 230), 1)
    return image


class PhotoOverlapDiagnosticTests(unittest.TestCase):
    def test_overlapping_same_surface_can_produce_candidate_not_verification(self):
        image = patterned_board(41)
        homography = np.float32([[1.02, .03, 11], [-.03, 1.01, -5],
                                 [.00003, -.00002, 1]])
        shifted = cv2.warpPerspective(image, homography, (1000, 700),
                                      borderValue=(230, 230, 230))
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.png", Path(directory) / "b.png"
            cv2.imwrite(str(a), image)
            cv2.imwrite(str(b), shifted)
            result = examine_photo_overlap([a, b])
        self.assertEqual(result["status"], "diagnostic_only")
        self.assertFalse(result["independent_physical_identity_verified"])
        self.assertEqual(result["pairs"][0]["status"], "overlapping_view_candidate")
        self.assertFalse(result["pairs"][0]["independent_physical_identity_verified"])
        self.assertNotIn("same_board", result)
        self.assertNotIn("grade", result)

    def test_different_patterned_boards_do_not_generate_overlap_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.png", Path(directory) / "b.png"
            cv2.imwrite(str(a), patterned_board(41))
            cv2.imwrite(str(b), patterned_board(88))
            result = examine_photo_overlap([a, b])
        self.assertEqual(result["status"], "diagnostic_only")
        self.assertEqual(result["pairs"][0]["status"], "inconclusive")
        self.assertFalse(result["pairs"][0]["independent_physical_identity_verified"])

    def test_blank_photo_reports_inconclusive_without_proving_difference(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.png", Path(directory) / "b.png"
            cv2.imwrite(str(a), patterned_board(41))
            cv2.imwrite(str(b), np.full((700, 1000, 3), 235, dtype=np.uint8))
            result = examine_photo_overlap([a, b])
        self.assertEqual(result["pairs"][0]["status"], "insufficient_image_features")
        self.assertFalse(result["pairs"][0]["independent_physical_identity_verified"])


if __name__ == "__main__":
    unittest.main()
