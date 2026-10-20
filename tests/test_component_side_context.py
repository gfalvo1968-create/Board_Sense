import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from PIL import Image, ImageOps
from routes.component_discriminator import discriminate_components
from routes.board_analyzer import _supported_recovery_population


class ComponentSideContextTests(unittest.TestCase):
    def analyze(self, image, circles=None):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'board.png'
            cv2.imwrite(str(path), image)
            if circles is None:return discriminate_components(str(path))
            with patch('routes.component_discriminator.cv2.HoughCircles', return_value=circles):
                return discriminate_components(str(path))

    def scene(self, packages=0):
        image=np.full((800,1100,3),175,np.uint8)
        cv2.rectangle(image,(200,100),(950,700),(28,140,36),-1)
        for i in range(packages):
            x,y=300+i*180,230
            cv2.rectangle(image,(x,y),(x+100,y+60),(24,24,24),-1)
            for px in range(x+8,x+94,8):
                cv2.rectangle(image,(px,y-6),(px+3,y+4),(210,210,210),-1)
                cv2.rectangle(image,(px,y+56),(px+3,y+66),(210,210,210),-1)
        positions=[]
        for y in (410,480,550,620):
            for x in range(280,850,70):
                cv2.circle(image,(x,y),10,(210,210,210),-1)
                cv2.circle(image,(x,y),10,(40,40,40),2)
                positions.append((x,y,10))
        return image,np.array([positions],np.float32)

    def test_solder_joints_do_not_hide_multiple_supported_package_bodies(self):
        image,circles=self.scene(3)
        result=self.analyze(image,circles)
        self.assertGreaterEqual(result['ic_like'],3)
        self.assertGreaterEqual(result['side_context']['raw_solder_pattern_score'],65)
        self.assertEqual(result['side_context']['status'],'populated_or_mixed_face')
        self.assertLess(result['solder_side_likelihood'],65)
        self.assertEqual(result['dominant_family'],'logic_ic')

    def test_solder_only_and_single_package_views_keep_solder_guard(self):
        for count in (0,1):
            image,circles=self.scene(count)
            result=self.analyze(image,circles)
            self.assertGreaterEqual(result['solder_side_likelihood'],65)
            self.assertEqual(result['capacitor_like'],0)
            self.assertEqual(result['magnetic_winding_like'],0)

    def test_unpinned_square_is_candidate_only_and_hole_is_not_package(self):
        image,_=self.scene()
        cv2.rectangle(image,(420,220),(530,330),(45,45,45),-1)
        cv2.circle(image,(780,260),45,(20,20,20),-1)
        result=self.analyze(image)
        candidates=[r for r in result['regions'] if r['type']=='Unverified package-like region']
        self.assertTrue(any(400<r['x']<540 for r in candidates))
        self.assertFalse(any(700<r['x']<830 for r in candidates))
        population=_supported_recovery_population({}, {'regions':candidates}, {'resolution':{'width':1100,'height':800}})
        self.assertEqual(population['count'],0)
        self.assertFalse(population['large_ic'])

    @unittest.skipUnless(os.getenv('BOARD_SENSE_ACER_FIXTURES'),'Optional private original-photo fixtures')
    def test_acer_front_keeps_component_candidates_back_keeps_solder_guard(self):
        root=Path(os.environ['BOARD_SENSE_ACER_FIXTURES'])
        for photo,front in [('IMG_5284.jpeg',True),('IMG_5285.jpeg',False)]:
            with tempfile.TemporaryDirectory() as directory:
                with Image.open(root/photo) as im:
                    im=ImageOps.exif_transpose(im).convert('RGB')
                    im.thumbnail((1600,1600),Image.Resampling.LANCZOS)
                    path=Path(directory)/'view.png';im.save(path)
                result=discriminate_components(str(path))
            self.assertEqual(result['side_context']['component_face_supported'],front)
            if front:
                self.assertGreater(result['capacitor_like'],0)
                self.assertEqual(result['dominant_family'],'logic_ic')
            else:
                self.assertGreaterEqual(result['solder_side_likelihood'],65)
                self.assertEqual(result['capacitor_like'],0)
