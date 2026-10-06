"""Routing regressions: wide PCB photos, non-board color and real ring geometry."""
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from routes.object_gate import classify_object, _speaker_signature


def populated_board():
    image = np.full((700,260,3),35,dtype=np.uint8)
    cv2.rectangle(image,(10,10),(250,690),(35,110,40),-1)
    for y in (80,230,380):
        cv2.rectangle(image,(70,y),(190,y+70),(20,20,20),-1)
        for x in range(78,185,8):
            cv2.rectangle(image,(x,y-6),(x+3,y+3),(220,220,220),-1)
            cv2.rectangle(image,(x,y+67),(x+3,y+76),(220,220,220),-1)
    for y in range(490,660,45):
        for x in (55,130,205):
            cv2.circle(image,(x,y),14,(40,170,210),-1)
            cv2.circle(image,(x,y),8,(35,90,110),2)
    return image


class ObjectGateFramingTests(unittest.TestCase):
    def gate(self,image):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"photo.png"
            cv2.imwrite(str(path),image)
            return classify_object(str(path))

    def test_same_populated_board_routes_as_pcb_with_wide_and_close_framing(self):
        board=populated_board()
        wide=np.full((1100,900,3),35,dtype=np.uint8)
        wide[200:900,320:580]=board
        for image in (board,wide,cv2.rotate(wide,cv2.ROTATE_90_CLOCKWISE)):
            with self.subTest(shape=image.shape):
                result=self.gate(image)
                self.assertEqual(result["mode"],"board",result)
                self.assertNotEqual(result["label"],"Speaker / audio driver")

    def test_color_without_circuit_construction_cannot_rescue_a_plain_sheet(self):
        image=np.full((1100,900,3),35,dtype=np.uint8)
        cv2.rectangle(image,(320,200),(580,900),(35,110,40),-1)
        result=self.gate(image)
        self.assertFalse(result["metrics"]["localized_pcb_evidence"]["supported"])
        self.assertNotEqual(result["mode"],"board")

    def test_centered_concentric_speaker_still_routes_as_speaker(self):
        image=np.full((800,800,3),170,dtype=np.uint8)
        for radius,value in [(300,190),(280,25),(245,60),(75,15)]:
            cv2.circle(image,(400,400),radius,(value,value,value),-1)
        result=self.gate(image)
        self.assertEqual(result["label"],"Speaker / audio driver",result)
        self.assertGreaterEqual(result["metrics"]["speaker_signature"]["perimeter_sector_coverage"],.75)

    def test_partial_arcs_cannot_claim_a_complete_speaker_outline(self):
        image=np.full((800,800),35,dtype=np.uint8)
        cv2.ellipse(image,(400,400),(260,260),0,30,180,160,4)
        score,_,_= _speaker_signature(image,30,.3)
        self.assertLess(score,82)


if __name__=="__main__":
    unittest.main()
