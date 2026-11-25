import unittest
import cv2
import numpy as np
from routes.board_region import _isolated_blue_surface

class BlueSurfaceTests(unittest.TestCase):
    def scene(self, populated=True):
        hsv=np.zeros((400,600,3),np.uint8)
        hsv[:]=[25,110,150]
        for x in (120,310):
            hsv[100:300,x:x+170]=[110,180,130]
            if populated:
                for y in range(110,290,16):
                    for u in range(x+10,x+160,16):
                        hsv[y:y+8,u:u+8]=[0,0,240]
        return cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR),hsv
    def test_fragmented_populated_surface(self):
        im,hsv=self.scene()
        mask=_isolated_blue_surface(im,hsv)
        self.assertGreater(cv2.countNonZero(mask),0)
        self.assertLess(cv2.countNonZero(mask)/mask.size,.4)
        self.assertEqual(int(mask[20,20]),0)
    def test_plain_blue_objects(self):
        im,hsv=self.scene(False)
        self.assertEqual(cv2.countNonZero(_isolated_blue_surface(im,hsv)),0)
    def test_full_blue_background(self):
        im,hsv=self.scene()
        hsv[:]=[110,180,130]
        im=cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
        self.assertEqual(cv2.countNonZero(_isolated_blue_surface(im,hsv)),0)
    def test_boundary_touching_surface(self):
        im,hsv=self.scene()
        hsv=np.roll(hsv,-120,axis=1)
        im=cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
        self.assertEqual(cv2.countNonZero(_isolated_blue_surface(im,hsv)),0)

if __name__=="__main__":
    unittest.main()
