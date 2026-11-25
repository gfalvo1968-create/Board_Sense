import unittest
import numpy as np
from routes.physical_layout_registration import compare_layouts

class PhysicalLayoutTests(unittest.TestCase):
    def setUp(self):
        self.a=np.array([[.08,.12],[.89,.10],[.13,.82],[.76,.91]])
    def test_reflected_opposite_face(self):
        b=self.a.copy()
        b[:,0]=1-b[:,0]
        result=compare_layouts(self.a,b[::-1])
        self.assertTrue(result["compatible"])
        self.assertEqual(result["matched_holes"],4)
        self.assertTrue(result["inspection_only"])
    def test_rotated_layout(self):
        b=self.a[:,::-1].copy()
        b[:,0]=1-b[:,0]
        self.assertTrue(compare_layouts(self.a,b)["compatible"])
    def test_small_measurement_error(self):
        self.assertTrue(compare_layouts(self.a,self.a+.008)["compatible"])
    def test_different_layout(self):
        b=self.a.copy()
        b[3]=[.52,.60]
        self.assertFalse(compare_layouts(self.a,b)["compatible"])
    def test_missing_hole(self):
        self.assertFalse(compare_layouts(self.a,self.a[:3])["compatible"])
    def test_duplicate_hole(self):
        b=self.a.copy()
        b[3]=b[0]
        self.assertFalse(compare_layouts(self.a,b)["compatible"])
    def test_collinear_holes(self):
        a=[[.1,.1],[.4,.1],[.8,.1]]
        self.assertFalse(compare_layouts(a,a)["compatible"])
    def test_nonfinite_or_invalid_coordinates(self):
        for val in (float("nan"),-1,2):
            b=self.a.copy()
            b[0,0]=val
            self.assertFalse(compare_layouts(self.a,b)["compatible"])

if __name__=="__main__":
    unittest.main()
