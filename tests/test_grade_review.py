import unittest
from routes.recovery_grade_guard import apply_recovery_grade_guard, apply_grade_review

class GradeReviewTests(unittest.TestCase):
    def test_sparse_logic_withholds_grade_without_adding_points(self):
        original = {'board_type':'Motherboard / Main Logic Board','grade':'LOW','score':3,
                    'signals':{'large_ic_chips':True,'component_count':3},
                    'recovery_signals':['limited precious metal recovery']}
        result = apply_recovery_grade_guard(original)
        self.assertEqual(result['grade'], 'MANUAL REVIEW')
        self.assertEqual(result['score'], 3)
        self.assertEqual(result['grade_assessment']['provisional_grade'], 'LOW')
        self.assertNotIn('limited precious metal recovery', result['recovery_signals'])
        self.assertEqual(apply_recovery_grade_guard(result)['grade'], 'MANUAL REVIEW')
        self.assertEqual(original['grade'], 'LOW')

    def test_corroborated_logic_keeps_medium(self):
        result = apply_recovery_grade_guard({'board_type':'Logic Board','grade':'LOW','score':3,
                    'signals':{'large_ic_chips':True,'dense_component_board':True}})
        self.assertEqual(result['grade'], 'MEDIUM')

    def test_power_board_not_promoted_or_withheld_by_identity(self):
        result = apply_grade_review({'board_type':'Power Supply Board','grade':'LOW','score':0})
        self.assertEqual(result['grade'], 'LOW')

    def test_unresolved_package_is_review_not_recovery_points(self):
        result = apply_grade_review({'board_type':'General PCB','grade':'LOW','score':0,
                    'component_intelligence':{'regions':[{'type':'Exposed-die / package candidate'}]}})
        self.assertEqual(result['grade'], 'MANUAL REVIEW')
        self.assertEqual(result['score'], 0)

    def test_repeated_review_emits_one_warning_without_mutating_input(self):
        original = {'board_type':'Motherboard / Main Logic Board','grade':'LOW','score':3,
                    'signals':{'large_ic_chips':True}, 'recovery_signals':['visible logic packages']}
        result = apply_grade_review(original)
        for _ in range(3):
            result = apply_recovery_grade_guard(result)
        warnings = [x for x in result['recovery_signals'] if x.startswith('Recovery grade withheld')]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(result['score'], 3)
        self.assertEqual(result['grade'], 'MANUAL REVIEW')
        self.assertEqual(original['recovery_signals'], ['visible logic packages'])
