import unittest
import cv2
import numpy as np
from routes.landmark_registration import compare_landmarks

class LandmarkRegistrationTests(unittest.TestCase):
    def scene(self, seed):
        rng=np.random.default_rng(seed)
        image=np.zeros((480,640,3),np.uint8)
        image[50:430,60:580]=[45,95,50]
        mask=np.zeros(image.shape[:2],np.uint8)
        mask[50:430,60:580]=255
        for _ in range(260):
            x,y=int(rng.integers(75,565)),int(rng.integers(65,415))
            color=tuple(int(v) for v in rng.integers(15,255,3))
            cv2.rectangle(image,(x,y),(x+int(rng.integers(4,13)),y+int(rng.integers(4,13))),color,-1)
        return image,mask
    def test_same_face_rotated(self):
        a,m=self.scene(42)
        b=cv2.rotate(a,cv2.ROTATE_90_CLOCKWISE)
        n=cv2.rotate(m,cv2.ROTATE_90_CLOCKWISE)
        result=compare_landmarks(a,b,m,n)
        self.assertTrue(result["supported"],result)
        self.assertTrue(result["inspection_only"])
    def test_unrelated_patterns(self):
        a,m=self.scene(42)
        b,n=self.scene(73)
        self.assertFalse(compare_landmarks(a,b,m,n)["supported"])
    def test_missing_mask(self):
        a,m=self.scene(42)
        self.assertFalse(compare_landmarks(a,a,None,m)["supported"])
    def test_blank_board(self):
        a,m=self.scene(42)
        a[:]=80
        self.assertFalse(compare_landmarks(a,a,m,m)["supported"])
    def test_shared_background_excluded(self):
        a,m=self.scene(42)
        b,n=self.scene(73)
        rng=np.random.default_rng(13)
        background=rng.integers(0,256,a.shape,dtype=np.uint8)
        a[m==0]=background[m==0]
        b[n==0]=background[n==0]
        self.assertFalse(compare_landmarks(a,b,m,n)["supported"])

if __name__=="__main__":
    unittest.main()
