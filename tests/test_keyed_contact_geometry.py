import unittest
import cv2
import numpy as np
from routes.board_visual import _confirmed_gold_finger_geometry

class KeyedContactTests(unittest.TestCase):
    def mask(self):
        return np.zeros((400,800),dtype=np.uint8)
    def test_keyed_rows(self):
        m=self.mask()
        for start in (100,300,510):
            for i in range(10):
                cv2.rectangle(m,(start+i*12,380),(start+i*12+5,399),255,-1)
        self.assertTrue(_confirmed_gold_finger_geometry(m,800,400)["confirmed"])
        rotated=cv2.rotate(m,cv2.ROTATE_90_CLOCKWISE)
        self.assertTrue(_confirmed_gold_finger_geometry(rotated,400,800)["confirmed"])
    def test_interior_contacts_not_confirmed(self):
        m=self.mask()
        for i in range(30):
            cv2.rectangle(m,(100+i*12,200),(105+i*12,219),255,-1)
        self.assertFalse(_confirmed_gold_finger_geometry(m,800,400)["confirmed"])
    def test_solid_strip_not_confirmed(self):
        m=self.mask()
        cv2.rectangle(m,(100,380),(650,399),255,-1)
        self.assertFalse(_confirmed_gold_finger_geometry(m,800,400)["confirmed"])
    def test_round_pads_not_confirmed(self):
        m=self.mask()
        for i in range(30):
            cv2.circle(m,(100+i*12,390),4,255,-1)
        self.assertFalse(_confirmed_gold_finger_geometry(m,800,400)["confirmed"])
if __name__=="__main__":
    unittest.main()
