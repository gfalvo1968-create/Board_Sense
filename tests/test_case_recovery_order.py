from copy import deepcopy
from itertools import permutations
import unittest
from unittest.mock import patch

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

    
def reconcile_with_test_only_verified_identity(views):
    """Exercise recovery mechanics AFTER an explicitly mocked identity pass.

    This mock is not physical image registration. Production must establish
    an independently supported identity before granting automated grades.
    """
    identity = {
        "version": "TEST FIXTURE: independently verified identity only",
        "status": "PROBABLY_SAME_BOARD",
        "same_board": True,
        "confidence": 94,
        "block_reconciliation": False,
        "whole_view_count": len(views),
        "identity_next_step": "No additional identity check required in this unit test.",
    }
    with patch("routes.case_reasoner.verify_same_board", return_value=identity):
        return reconcile_case(views)


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
                    case = reconcile_with_test_only_verified_identity(list(order))
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
            case = reconcile_with_test_only_verified_identity(list(order))
            self.assertEqual(case["score"], 5)
            self.assertEqual(case["confidence"], 90)

    def test_distinct_logic_boards_never_get_unverified_combined_medium_grade(self):
        first = board_view(3, 6, confidence=60)
        second = board_view(9, 24, confidence=78)
        for r in (first, second):
            r["object_gate"] = {"mode": "board"}
        # Identical generic board outline and same classifier family are not
        # proof of one physical item, as demonstrated by the field test.
        unconfirmed = reconcile_case([first, second])
        self.assertEqual(unconfirmed["status"], "case_identity_failed")
        self.assertEqual(unconfirmed["grade"], "UNRESOLVED")
        self.assertEqual(unconfirmed["score"], 0)
        self.assertIsNone(unconfirmed["three_answers"]["economics"]["winner"])
        confirmed = reconcile_case([first, second], operator_same_board_confirmation=True)
        self.assertEqual(confirmed["same_board_verification"]["status"], "OPERATOR_CONFIRMED_SAME_BOARD")
        self.assertEqual(confirmed["grade"], "MANUAL REVIEW")
        self.assertFalse(confirmed["pay_dirt_ready"])
        self.assertLessEqual(confirmed["confidence"], 60)
        self.assertEqual(confirmed["recovery_economics"]["status"], "board_verification_required")
        self.assertIsNone(confirmed["three_answers"]["economics"]["winner"])
        self.assertTrue(confirmed["requires_manual_board_verification"])

    def test_user_confirmed_pcb_like_reverse_cannot_assign_case_grade(self):
        populated = board_view(9, 24)
        populated["object_gate"] = {"mode": "board"}
        reverse = board_view(0, 0, label="PCB-like object / manual verification required", confidence=44)
        reverse["object_gate"] = {"mode": "pcb_review"}
        reverse["grade"] = "N/A"
        reverse["signals"] = {}
        for order in permutations([populated, reverse]):
            with self.subTest(order=[v["board_type"] for v in order]):
                blocked = reconcile_case(list(order))
                self.assertEqual(blocked["status"], "case_identity_failed")
                self.assertEqual(blocked["grade"], "UNRESOLVED")
                result = reconcile_case(list(order), operator_same_board_confirmation=True)
                self.assertEqual(result["board_type"], "Dense Logic / Controller Board")
                self.assertEqual(result["grade"], "MANUAL REVIEW")
                self.assertLessEqual(result["confidence"], 60)
                self.assertFalse(result["pay_dirt_ready"])
                self.assertEqual(result["grade_assessment"]["status"], "MANUAL_REVIEW_REQUIRED")
                self.assertIsNone(result["recovery_economics"]["winner"])
                self.assertTrue(result["requires_manual_board_verification"])
                self.assertEqual(result["three_answers"]["recovery"]["grade"], "MANUAL REVIEW")

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
