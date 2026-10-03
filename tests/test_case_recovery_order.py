from copy import deepcopy
from itertools import permutations
import unittest

from routes.case_reasoner import reconcile_case


def board_view(score, count, label="Dense Logic / Controller Board", confidence=85):
    return {
        "board_type": label,
        "confidence": confidence,
        "grade": "LOW",
        "score": score,
        "signals": {
            "large_ic_chips": True,
            "dense_component_board": True,
            "component_count": count,
        },
        "physical_fingerprint": {
            "available": True,
            "coverage": "whole_or_large_view",
            "geometry_quality": "good",
            "board_aspect": 1.5,
            "hole_count": 2,
            "landmark_count": 20,
            "rectangularity": .9,
            "solidity": .9,
        },
        "model": "Board Sense v4.4 + Board Blueprint v1.1",
    }


class CaseRecoveryOrderTests(unittest.TestCase):
    def test_equal_confidence_keeps_recovery_score_in_both_photo_orders(self):
        # Exercise label voting, the structural veto, and the edge-vote fallback.
        for label in (
            "Dense Logic / Controller Board",
            "Embedded Main Logic Board",
            "Edge-Connector Board",
        ):
            views = [board_view(5, 8, label), board_view(9, 24, label)]
            original = deepcopy(views)
            for order in permutations(views):
                with self.subTest(label=label, scores=[r["score"] for r in order]):
                    case = reconcile_case(list(order))
                    self.assertEqual(case["score"], 9)
                    expected_grade = "LOW" if label == "Edge-Connector Board" else "MEDIUM"
                    self.assertEqual(case["grade"], expected_grade)
                    self.assertEqual(case["three_answers"]["recovery"]["score"], 9)
                    self.assertEqual(case["signals"]["component_count"], 24)
                    self.assertFalse(case["same_board_verification"]["block_reconciliation"])
                    self.assertEqual(case["recovery_economics"]["status"], "needs_values")
                    self.assertIn("Board Blueprint v1.1", case["model"])
            self.assertEqual(views, original)

    def test_duplicate_photos_do_not_add_recovery_scores(self):
        weaker = board_view(5, 8)
        stronger = board_view(9, 24)
        for order in permutations([weaker, stronger, deepcopy(stronger)]):
            case = reconcile_case(list(order))
            self.assertEqual(case["score"], 9)
            self.assertEqual(case["case_analysis"]["independent_evidence_patterns"], 1)
            self.assertTrue(case["case_analysis"]["duplicate_evidence_guard"]["active"])

    def test_higher_confidence_still_outranks_a_higher_recovery_score(self):
        views = [board_view(5, 8, confidence=90), board_view(9, 24)]
        for order in permutations(views):
            case = reconcile_case(list(order))
            self.assertEqual(case["score"], 5)
            self.assertEqual(case["confidence"], 90)

    def test_recovery_tie_cannot_override_separate_boards_in_one_frame(self):
        views = [board_view(5, 8), board_view(9, 24)]
        views[1]["board_blueprint"] = {
            "frame_identity_gate": {"block_analysis": True, "confidence": 92}
        }
        for order in permutations(views):
            case = reconcile_case(list(order), operator_same_board_confirmation=True)
            self.assertEqual(case["status"], "case_identity_failed")
            self.assertEqual(case["score"], 0)
            self.assertEqual(case["three_answers"]["recovery"]["grade"], "WITHHELD")


if __name__ == "__main__":
    unittest.main()
