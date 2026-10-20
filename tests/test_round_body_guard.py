import os
import unittest
from pathlib import Path
import cv2
import numpy as np
from routes.component_discriminator import _round_body_support,discriminate_components
from routes.analysis_image import board_analysis_image


class RoundBodyGuardTests(unittest.TestCase):
    def image(self):
        return np.full((300,300,3),(30,110,40),np.uint8)

    def test_continuous_round_body_rim_is_retained_at_several_sizes(self):
        for radius in (12,25,40,60):
            image=self.image()
            cv2.circle(image,(150,150),radius,(145,145,145),-1)
            self.assertTrue(_round_body_support(image,150,150,np.int64(radius)))

    def test_square_and_hole_do_not_qualify_as_round_component_bodies(self):
        square=self.image();cv2.rectangle(square,(110,110),(190,190),(50,50,50),-1)
        self.assertFalse(_round_body_support(square,150,150,40))
        hole=self.image();cv2.circle(hole,(150,150),40,(170,170,170),-1)
        cv2.circle(hole,(150,150),22,(10,10,10),-1)
        self.assertFalse(_round_body_support(hole,150,150,40))

    def test_scattered_texture_and_clipped_circles_are_rejected(self):
        for seed in (1,42,123):
            image=np.random.default_rng(seed).integers(20,200,(300,300,3),dtype=np.uint8)
            self.assertFalse(_round_body_support(image,150,150,40))
        self.assertFalse(_round_body_support(self.image(),10,10,40))

    @unittest.skipUnless(os.getenv('BOARD_SENSE_ACER_FIXTURES'),'Optional private original-photo fixtures')
    def test_acer_round_markers_do_not_occupy_detected_packages(self):
        root=Path(os.environ['BOARD_SENSE_ACER_FIXTURES'])
        for name,front in [('IMG_5284.jpeg',True),('IMG_5285.jpeg',False)]:
            with board_analysis_image(root/name) as working:
                result=discriminate_components(str(working))
            guard=result['round_body_guard']
            self.assertGreater(guard['rejected_candidates'],0)
            caps=[r for r in result['regions'] if r['type']=='Capacitor-like round component']
            packages=[r for r in result['regions'] if r['type'] in ('IC-like package','Unverified package-like region','Exposed-die / package candidate')]
            if front:self.assertTrue(caps)
            else:self.assertFalse(caps)
            for cap in caps:
                cx,cy=cap['x']+cap['w']/2,cap['y']+cap['h']/2
                self.assertFalse(any(p['x']<=cx<=p['x']+p['w'] and p['y']<=cy<=p['y']+p['h'] for p in packages))
