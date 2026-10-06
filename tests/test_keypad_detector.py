import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import cv2
import numpy as np

from routes.keypad_detector import detect_keypad
from routes.board_scoring import calculate_score
from routes.board_type import classify_board_type
from routes.case_reasoner import reconcile_case
from test_case_recovery_order import board_view


def keypad_scene():
    image=np.full((900,650,3),35,dtype=np.uint8)
    cv2.rectangle(image,(180,80),(460,820),(35,95,40),-1)
    for y in range(220,721,100):
        for x in (225,320,415):
            cv2.circle(image,(x,y),28,(50,170,220),-1)
            cv2.circle(image,(x,y),12,(35,90,110),2)
    return image


class KeypadDetectorTests(unittest.TestCase):
    def detect(self,image):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"photo.png";cv2.imwrite(str(p),image)
            return detect_keypad(p)

    def test_keypad_is_recognized_after_rotation_and_wider_framing(self):
        image=keypad_scene()
        wide=np.full((1300,1000,3),35,dtype=np.uint8);wide[200:1100,175:825]=image
        for view in (image,wide,cv2.rotate(wide,cv2.ROTATE_90_CLOCKWISE)):
            self.assertTrue(self.detect(view)["supported"])

    def test_isolated_mounting_contacts_do_not_establish_a_keypad(self):
        image=np.full((900,650,3),35,dtype=np.uint8)
        for center in [(150,150),(500,150),(150,700),(500,700)]:
            cv2.circle(image,center,28,(50,170,220),-1)
        self.assertFalse(self.detect(image)["supported"])

    def test_one_row_of_contacts_is_not_a_two_dimensional_keypad(self):
        image=np.full((500,1000,3),35,dtype=np.uint8)
        for x in range(100,901,80):cv2.circle(image,(x,250),18,(50,170,220),-1)
        self.assertFalse(self.detect(image)["supported"])

    def test_keypad_context_does_not_add_recovery_points(self):
        features={"large_ic_chips":True,"component_count":2}
        score=calculate_score(features)
        features["keypad_contact_array"]=True
        self.assertEqual(calculate_score(features),score)
        self.assertEqual(classify_board_type(features,{}, {},{})["type"],"Keypad / Handheld Controller Board")

    def test_verified_case_keeps_keypad_family_in_both_orders_without_yields(self):
        front=board_view(3,2,"Keypad / Handheld Controller Board",70)
        front["signals"]["dense_component_board"]=False
        front["keypad_intelligence"]={"supported":True,"contact_count":18}
        back=deepcopy(front);back.pop("keypad_intelligence");back["board_type"]="Power-Control / Controller Board"
        for views in ([front,back],[back,front]):
            case=reconcile_case(views)
            self.assertEqual(case["board_type"],"Keypad / Handheld Controller Board")
            self.assertEqual(case["score"],3)
            self.assertEqual(case["grade"],"LOW")
            self.assertEqual(case["recovery_economics"]["status"],"needs_values")
            self.assertIn("Unconfirmed",case["equipment_subtype"]["subtype"])

    def test_mixed_board_stop_precedes_keypad_identity(self):
        front=board_view(3,2,"Keypad / Handheld Controller Board")
        front["keypad_intelligence"]={"supported":True}
        front["frame_identity_gate"]={"block_analysis":True,"confidence":95}
        case=reconcile_case([front,deepcopy(front)])
        self.assertEqual(case["status"],"case_identity_failed")
        self.assertNotEqual(case["board_type"],"Keypad / Handheld Controller Board")
