import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from routes.case_identity_gate import verify_same_board
from routes.frame_identity_gate import inspect_frame


def view(aspect=1.5, holes=2, landmarks=20, rect=.9):
    return {
        "board_type": "phone board", "confidence": 85,
        "physical_fingerprint": {
            "available": True, "coverage": "whole_or_large_view",
            "geometry_quality": "good", "board_aspect": aspect,
            "hole_count": holes, "landmark_count": landmarks,
            "rectangularity": rect, "solidity": .9,
        },
    }


class CaseIdentityGuardTests(unittest.TestCase):
    def test_metal_shield_divides_one_pcb_surface_without_hard_stop(self):
        image = np.full((800, 1200, 3), 115, dtype=np.uint8)
        cv2.rectangle(image, (100, 130), (1100, 670), (20, 95, 20), -1)
        cv2.rectangle(image, (570, 130), (670, 670), (180, 180, 180), -1)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "shield.png")
            cv2.imwrite(path, image)
            result = inspect_frame(path)
        self.assertEqual(result["status"], "FRAME_SHAPE_AMBIGUOUS")
        self.assertFalse(result["block_analysis"])

    def test_two_separated_pcbs_still_stop(self):
        image = np.full((800, 1200, 3), 115, dtype=np.uint8)
        cv2.rectangle(image, (90, 160), (480, 660), (20, 95, 20), -1)
        cv2.rectangle(image, (650, 160), (1080, 660), (20, 95, 20), -1)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "two.png")
            cv2.imwrite(path, image)
            result = inspect_frame(path)
        self.assertTrue(result["block_analysis"])

    def test_one_noisy_view_can_be_confirmed_by_operator(self):
        photos = [view(), view(), view(), view(4.1, 9, 60, .55)]
        self.assertEqual(verify_same_board(photos)["status"], "IDENTITY_UNCERTAIN")
        result = verify_same_board(photos, operator_confirmed=True)
        self.assertEqual(result["status"], "OPERATOR_CONFIRMED_SAME_BOARD")
        self.assertFalse(result["block_reconciliation"])

    def test_two_coherent_incompatible_groups_still_stop(self):
        photos = [view(), view(), view(4.1, 9, 60, .55), view(4.1, 9, 60, .55)]
        result = verify_same_board(photos, operator_confirmed=True)
        self.assertEqual(result["status"], "MULTIPLE_BOARDS_SUSPECTED")
        self.assertTrue(result["block_reconciliation"])

    def test_pcb_review_face_blocks_automatic_same_board_confidence(self):
        front = view()
        front["object_gate"] = {"mode": "board"}
        back = view()
        back["object_gate"] = {"mode": "pcb_review"}
        back["board_type"] = "PCB-like object / manual verification required"
        back["confidence"] = 44
        result = verify_same_board([front, back])
        self.assertEqual(result["status"], "PCB_REVIEW_VIEWS_REQUIRE_CONFIRMATION")
        self.assertTrue(result["block_reconciliation"])
        self.assertIsNone(result["same_board"])
        confirmed = verify_same_board([front, back], operator_confirmed=True)
        self.assertEqual(confirmed["status"], "OPERATOR_CONFIRMED_SAME_BOARD")
        self.assertEqual(confirmed["pcb_review_views"], [2])
        self.assertFalse(confirmed["block_reconciliation"])
        self.assertLessEqual(confirmed["confidence"], 60)

    def test_operator_cannot_merge_unknown_or_component_into_board_case(self):
        front = view()
        front["object_gate"] = {"mode": "board"}
        for kind in ("unknown", "component"):
            with self.subTest(kind=kind):
                other = view()
                other["object_gate"] = {"mode": kind, "label": "unverified object"}
                result = verify_same_board([front, other], operator_confirmed=True)
                self.assertTrue(result["block_reconciliation"])
                self.assertEqual(result["status"], "NON_BOARD_VIEW_REQUIRES_RETAKE")

    def test_two_strongly_incompatible_whole_board_shapes_cannot_be_confirmed(self):
        # Two whole-board views with extreme shape AND corroborating
        # geometry differences are incompatible even with the checkbox.
        photos = [view(1.5, 2, 20, .9), view(4.1, 9, 60, .55)]
        for confirmed in (False, True):
            with self.subTest(operator_confirmed=confirmed):
                result = verify_same_board(photos, operator_confirmed=confirmed)
                self.assertEqual(result["status"], "MULTIPLE_BOARDS_SUSPECTED")
                self.assertTrue(result["block_reconciliation"])
                self.assertEqual(result["conflicting_views"], [1, 2])
                self.assertFalse(result["same_board"])

    def test_noisy_or_moderate_two_view_geometry_does_not_hard_split(self):
        for ambiguous in (
            view(3.0, 3, 20, .9),
            view(4.1, 9, 60, .55),
        ):
            with self.subTest(aspect=ambiguous["physical_fingerprint"]["board_aspect"]):
                # Medium quality is not strong enough for an automatic split.
                ambiguous["physical_fingerprint"]["geometry_quality"] = "medium"
                result = verify_same_board([view(), ambiguous], operator_confirmed=True)
                self.assertEqual(result["status"], "OPERATOR_CONFIRMED_SAME_BOARD")
                self.assertFalse(result["block_reconciliation"])

    def test_distinct_boards_same_classifier_label_cannot_be_auto_merged(self):
        # Recreates staging's false-positive class of error: two physical
        # boards both look like logic/controllers and generic outlines agree.
        first = view(aspect=1.6, holes=2, landmarks=25, rect=.85)
        second = view(aspect=1.62, holes=2, landmarks=28, rect=.84)
        for photo in (first, second):
            photo["board_type"] = "Dense Logic / Controller Board"
            photo["object_gate"] = {"mode": "board"}
        response = verify_same_board([first, second])
        self.assertEqual(response["status"], "IDENTITY_UNCERTAIN", response)
        self.assertTrue(response["block_reconciliation"])
        self.assertIsNone(response["same_board"])
        self.assertFalse(response["positive_geometry_evidence"])

    def test_confirmed_pair_is_operator_only_not_ai_verified(self):
        first, second = view(), view()
        for photo in (first, second):
            photo["object_gate"] = {"mode": "board"}
        response = verify_same_board([first, second], operator_confirmed=True)
        self.assertEqual(response["status"], "OPERATOR_CONFIRMED_SAME_BOARD")
        self.assertEqual(response["confidence"], 60)
        self.assertTrue(response["operator_confirmed"])

    def test_operator_cannot_override_separate_boards_in_one_frame(self):
        photos = [view(), view()]
        photos[0]["board_blueprint"] = {"frame_identity_gate": {"block_analysis": True, "confidence": 92}}
        self.assertTrue(verify_same_board(photos, operator_confirmed=True)["block_reconciliation"])


if __name__ == "__main__":
    unittest.main()
