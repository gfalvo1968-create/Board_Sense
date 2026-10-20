import os
import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps
from routes.component_discriminator import discriminate_components
from routes.board_analyzer import _supported_recovery_population


class NestedPackageCandidateTests(unittest.TestCase):
    def analyze(self, image):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'view.png';cv2.imwrite(str(path),image)
            return discriminate_components(str(path))

    def scene(self):
        image=np.full((800,1100,3),175,np.uint8)
        cv2.rectangle(image,(200,100),(950,700),(28,140,36),-1)
        return image

    def test_nested_face_is_candidate_on_rotated_and_large_photos(self):
        image=self.scene()
        cv2.rectangle(image,(430,260),(550,380),(40,40,40),-1)
        cv2.rectangle(image,(467,297),(513,343),(160,160,160),-1)
        for photo in (image,cv2.rotate(image,cv2.ROTATE_90_CLOCKWISE),cv2.resize(image,(2200,1600))):
            result=self.analyze(photo)
            candidates=[r for r in result['regions'] if r['type']=='Exposed-die / package candidate']
            self.assertEqual(len(candidates),1)
            height,width=photo.shape[:2]
            population=_supported_recovery_population({}, {'regions':candidates}, {'resolution':{'width':width,'height':height}})
            self.assertEqual(population['count'],0)
            self.assertFalse(population['processor'])

    def test_holes_green_footprints_and_off_board_faces_do_not_qualify(self):
        image=self.scene()
        cv2.circle(image,(400,300),55,(30,30,30),-1)
        cv2.circle(image,(400,300),20,(160,160,160),-1)
        # Green solder-mask footprint with a light central printed rectangle.
        cv2.rectangle(image,(580,240),(700,360),(20,70,26),-1)
        cv2.rectangle(image,(617,277),(663,323),(160,160,160),-1)
        # A package-shaped object outside the supported board boundary.
        cv2.rectangle(image,(30,250),(150,370),(40,40,40),-1)
        cv2.rectangle(image,(67,287),(113,333),(160,160,160),-1)
        result=self.analyze(image)
        self.assertFalse(any(r['type']=='Exposed-die / package candidate' for r in result['regions']))

    @unittest.skipUnless(os.getenv('BOARD_SENSE_ACER_FIXTURES'),'Optional private original-photo fixtures')
    def test_acer_front_adds_candidate_back_does_not(self):
        root=Path(os.environ['BOARD_SENSE_ACER_FIXTURES'])
        for name,expected in [('IMG_5284.jpeg',True),('IMG_5285.jpeg',False)]:
            with Image.open(root/name) as source:
                for side in (2048,4032):
                    image=ImageOps.exif_transpose(source).convert('RGB')
                    image=image.resize((side*3//4,side))
                    with tempfile.TemporaryDirectory() as directory:
                        path=Path(directory)/'view.jpg';image.save(path,quality=95)
                        from routes.board_analyzer import analyze_board
                        result=analyze_board(str(path))
                    candidates=[r for r in result['component_intelligence']['regions'] if r['type']=='Exposed-die / package candidate']
                    # At 2048, the conservative PCB outline can exclude this
                    # package. Never bypass that guard to force a marker.
                    if not expected or side==4032:
                        self.assertEqual(bool(candidates),expected)
                    else:
                        self.assertFalse(candidates)
                    if expected:
                        self.assertEqual(result['board_type'],'Motherboard / Main Logic Board')
                        self.assertEqual(result['score'],3)
