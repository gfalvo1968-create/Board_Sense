import unittest
import cv2
import numpy as np
from routes.board_visual import _localized_contact_geometry

class LocalizedContactTests(unittest.TestCase):
    def scene(self, contacts=True):
        hsv=np.zeros((500,800,3),dtype=np.uint8)
        hsv[:]=[0,0,160]
        hsv[100:350,150:650]=[65,160,140]
        gold=np.zeros((500,800),dtype=np.uint8)
        if contacts:
            for x in range(180,600,12):
                gold[330:350,x:x+6]=255
                hsv[330:350,x:x+6]=[25,200,220]
        return hsv,gold
    def test_margin_and_rotation(self):
        hsv,gold=self.scene()
        result=_localized_contact_geometry(hsv,gold)
        self.assertIsNotNone(result)
        self.assertTrue(result["inspection_only"])
        self.assertIsNotNone(_localized_contact_geometry(cv2.rotate(hsv,cv2.ROTATE_90_CLOCKWISE),cv2.rotate(gold,cv2.ROTATE_90_CLOCKWISE)))
    def test_no_substrate(self):
        hsv,gold=self.scene()
        hsv[:]=[0,0,160]
        self.assertIsNone(_localized_contact_geometry(hsv,gold))
    def test_background_contacts(self):
        hsv,gold=self.scene(False)
        for x in range(180,600,12):
            gold[430:450,x:x+6]=255
        self.assertIsNone(_localized_contact_geometry(hsv,gold))
    def test_no_contacts(self):
        self.assertIsNone(_localized_contact_geometry(*self.scene(False)))
if __name__=="__main__":
    unittest.main()
