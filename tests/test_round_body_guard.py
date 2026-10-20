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

    def test_shaded_open_centers_are_rejected_by_relative_rim_contrast(self):
        for center in (20,40,65,100):
            image=self.image()
            cv2.circle(image,(150,150),40,(180,180,180),-1)
            cv2.circle(image,(150,150),16,(center,center,center),-1)
            self.assertFalse(_round_body_support(image,150,150,40))

    def test_uniform_shaded_top_and_small_vent_mark_remain_candidates(self):
        for level in (65,100,145):
            image=self.image()
            cv2.circle(image,(150,150),40,(level,level,level),-1)
            self.assertTrue(_round_body_support(image,150,150,40))
        image=self.image()
        cv2.circle(image,(150,150),40,(160,160,160),-1)
        cv2.line(image,(126,150),(174,150),(45,45,45),2)
        cv2.line(image,(150,126),(150,174),(45,45,45),2)
        self.assertTrue(_round_body_support(image,150,150,40))

    @unittest.skipUnless(os.getenv('BOARD_SENSE_ACER_FIXTURES'),'Optional private original-photo fixtures')
    def test_acer_lower_mounting_hole_is_not_a_capacitor_marker(self):
        from PIL import Image,ImageOps
        import tempfile
        root=Path(os.environ['BOARD_SENSE_ACER_FIXTURES'])
        with Image.open(root/'IMG_5284.jpeg') as source:
            for side in (2048,4032):
                image=ImageOps.exif_transpose(source).convert('RGB').resize((side*3//4,side))
                with tempfile.TemporaryDirectory() as directory:
                    path=Path(directory)/'view.jpg';image.save(path,quality=95)
                    with board_analysis_image(path) as working:
                        result=discriminate_components(str(working))
                        height,width=cv2.imread(str(working)).shape[:2]
                caps=[r for r in result['regions'] if r['type']=='Capacitor-like round component']
                # Independently inspected mounting-hole location in this private
                # fixture, expressed as image fractions (not production rules).
                self.assertFalse(any(abs((r['x']+r['w']/2)/width-.20)<.025 and
                                     abs((r['y']+r['h']/2)/height-.775)<.025 for r in caps))
