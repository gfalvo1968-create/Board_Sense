"""No-fusion regression tests for distinct circuit boards in one photograph."""
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from routes.multi_board_independent import (
    inspect_independent_regions, analyze_independent_boards,
)


def frame(count=2, populated=True, background=116):
    height, width = 800, 1200
    image = np.full((height, width, 3), background, dtype=np.uint8)
    margin = 70
    gap = 90
    bw = (width - 2 * margin - (count - 1) * gap) // count
    for i in range(count):
        left = margin + i * (bw + gap)
        top, bottom = 145, 665
        cv2.rectangle(image, (left, top), (left+bw, bottom), (22, 115, 30), -1)
        if populated:
            for y in range(top+20, bottom-30, 61):
                for x in range(left+18, left+bw-36, 52):
                    cv2.rectangle(image, (x, y), (x+34, y+30), (24, 27, 29), -1)
                    cv2.line(image, (x+3, y+35), (x+30, y+35), (220, 220, 220), 2)
    return image


class SeparateBoardPreviewTests(unittest.TestCase):
    def run_photo(self, image, fn):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "photo.png"
            cv2.imwrite(str(path), image)
            return fn(path)

    def test_two_boards_are_two_independent_grades_no_combined_fields(self):
        seen = []
        def analyze(path):
            seen.append(str(path))
            grade = "LOW" if len(seen) == 1 else "MEDIUM"
            return {
                "object_gate": {"mode": "board"},
                "confidence": 82,
                "board_type": "Board type " + str(len(seen)),
                "grade": grade,
                "recommendation": "Independent inspection only",
                "board_blueprint": {"available": False},
            }
        def check(path):
            response = analyze_independent_boards(path, analyzer=analyze)
            self.assertEqual(response["status"], "separate_reports", response)
            self.assertEqual(response["board_count"], 2)
            self.assertEqual([r["provisional_grade"] for r in response["reports"]], ["LOW", "MEDIUM"])
            self.assertEqual([r["board_index"] for r in response["reports"]], [1, 2])
            self.assertNotIn("combined", response)
            self.assertIsNone(response["combined_grade"])
            self.assertIsNone(response["combined_recovery_economics"])
            self.assertTrue(all(r["recovery_economics"]["status"] == "unpriced" for r in response["reports"]))
        self.run_photo(frame(), check)
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(not Path(p).exists() for p in seen), "Private crops must be deleted")

    def test_three_boards_never_share_a_grade(self):
        calls = []
        def analyze(path):
            calls.append(path)
            return {"object_gate": {"mode": "board"}, "confidence": 85,
                    "grade": ("LOW", "MEDIUM", "HIGH")[len(calls)-1],
                    "board_type": "Separate PCB", "board_blueprint": {"available": False}}
        def check(path):
            response = analyze_independent_boards(path, analyzer=analyze)
            self.assertEqual(response["status"], "separate_reports", response)
            self.assertEqual(response["board_count"], 3)
            self.assertEqual(len(response["reports"]), 3)
            self.assertEqual([r["provisional_grade"] for r in response["reports"]],
                             ["LOW", "MEDIUM", "HIGH"])
        self.run_photo(frame(3), check)

    def test_one_uncertain_board_gets_manual_review_not_a_borrowed_grade(self):
        seen = []
        def analyze(_path):
            seen.append(True)
            if len(seen) == 1:
                return {"object_gate": {"mode": "board"}, "grade": "LOW",
                        "confidence": 82, "board_type": "Board one"}
            return {"object_gate": {"mode": "unknown"}, "grade": "HIGH",
                    "confidence": 28, "board_type": "Unverified"}
        result = self.run_photo(frame(), lambda path: analyze_independent_boards(path, analyzer=analyze))
        self.assertEqual([r["provisional_grade"] for r in result["reports"]],
                         ["LOW", "MANUAL REVIEW"])
        self.assertEqual(result["reports"][1]["board_type"], "UNVERIFIED")

    def test_plain_colored_rectangles_are_not_graded_as_boards(self):
        def check(path):
            response = inspect_independent_regions(path)
            self.assertEqual(response["status"], "manual_review_required", response)
            self.assertEqual(response["reports"], [])
        self.run_photo(frame(populated=False), check)

    def test_one_board_split_by_a_shield_is_not_two_independent_boards(self):
        image = np.full((800, 1200, 3), 115, dtype=np.uint8)
        cv2.rectangle(image, (100, 130), (1100, 670), (20, 95, 20), -1)
        cv2.rectangle(image, (570, 130), (670, 670), (180, 180, 180), -1)
        self.run_photo(image, lambda p: self.assertEqual(
            inspect_independent_regions(p)["status"], "manual_review_required"))

    def test_unrelated_noisy_image_never_becomes_multiple_boards(self):
        rng = np.random.default_rng(121)
        image = rng.integers(40, 150, (800, 1200, 3), dtype=np.uint8)
        self.run_photo(image, lambda p: self.assertEqual(
            inspect_independent_regions(p)["status"], "manual_review_required"))


if __name__ == "__main__":
    unittest.main()
