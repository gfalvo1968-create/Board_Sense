import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from routes.analysis_image import board_analysis_image


class AnalysisImageTests(unittest.TestCase):
    def test_large_image_is_bounded_and_temporary_copy_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'large.jpg'
            Image.new('RGB', (3024, 4032), (30, 100, 40)).save(original)
            before = original.read_bytes()
            with board_analysis_image(original) as working:
                working = Path(working)
                self.assertNotEqual(working, original)
                with Image.open(working) as image:
                    self.assertEqual(image.size, (1200, 1600))
            self.assertFalse(working.exists())
            self.assertEqual(original.read_bytes(), before)

    def test_small_image_is_not_reencoded(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'small.png'
            Image.new('RGB', (800, 600)).save(original)
            with board_analysis_image(original) as working:
                self.assertEqual(working, original)

    def test_normalized_blueprints_are_distinct_and_inline_without_persistence(self):
        import base64
        import cv2
        import numpy as np
        from routes.board_analyzer import analyze_board

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            uploads = root / 'data' / 'Images'
            uploads.mkdir(parents=True)
            reports = root / 'data' / 'Blueprints'
            image_payloads = []
            for i in range(2):
                image = np.full((1600, 2200, 3), 180, np.uint8)
                cv2.rectangle(image, (400, 200), (1800, 1400), (28, 100, 36), -1)
                for row in range(4):
                    for col in range(5):
                        x, y = 500 + col*230 + i*10, 300 + row*250
                        cv2.rectangle(image, (x, y), (x+100, y+70), (24, 24, 24), -1)
                path = uploads / f'photo-{i}.png'
                cv2.imwrite(str(path), image)
                # This regression isolates image delivery from object classification.
                from unittest.mock import patch
                with patch('routes.board_analyzer.classify_object', return_value={'mode': 'board'}):
                    result = analyze_board(str(path))
                blueprint = result['board_blueprint']
                self.assertTrue(blueprint['available'], blueprint)
                self.assertEqual(blueprint['delivery_mode'], 'inline_no_store')
                self.assertNotIn('image_filename', blueprint)
                self.assertTrue(blueprint['image_url'].startswith('data:image/jpeg;base64,'))
                raw = base64.b64decode(blueprint['image_url'].split(',', 1)[1], validate=True)
                decoded = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
                self.assertIsNotNone(decoded)
                self.assertLessEqual(max(decoded.shape[:2]), 1200)
                image_payloads.append(raw)
            self.assertNotEqual(image_payloads[0], image_payloads[1])
            self.assertFalse(reports.exists() and any(reports.rglob('*')),
                             'Derived images must not persist on the server')

    def test_orientation_and_error_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'rotated.jpg'
            exif = Image.Exif()
            exif[274] = 6
            Image.new('RGB', (600, 800)).save(original, exif=exif)
            with self.assertRaisesRegex(RuntimeError, 'detector failed'):
                with board_analysis_image(original) as working:
                    with Image.open(working) as image:
                        self.assertEqual(image.size, (800, 600))
                        self.assertNotIn(274, image.getexif())
                    raise RuntimeError('detector failed')
            self.assertFalse(Path(working).exists())

    @unittest.skipUnless(os.getenv('BOARD_SENSE_ACER_FIXTURES'), 'Optional private original-photo fixtures')
    def test_large_and_small_uploads_keep_mainboard_case_identity(self):
        from routes.board_analyzer import analyze_board
        from routes.case_reasoner import reconcile_case
        root = Path(os.environ['BOARD_SENSE_ACER_FIXTURES'])
        back = analyze_board(str(root / 'IMG_5285.jpeg'))
        with Image.open(root / 'IMG_5284.jpeg') as original:
            with tempfile.TemporaryDirectory() as directory:
                for size in (2048, 4032):
                    path = Path(directory) / f'front-{size}.jpg'
                    original.resize((size*3//4, size)).save(path, quality=95)
                    front = analyze_board(str(path))
                    self.assertEqual(front['board_type'], 'Motherboard / Main Logic Board')
                    self.assertTrue(front['motherboard']['confirmed_slot_bank'])
                    self.assertTrue(front['motherboard']['edge_connector_bank'])
                    self.assertLessEqual(max(front['photo_quality']['resolution'].values()), 1600)
                    for views in ([front, back], [back, front]):
                        case = reconcile_case(views)
                        self.assertEqual(case['board_type'], 'Motherboard / Main Logic Board')
                        self.assertTrue(case['same_board_verification']['same_board'])
                        self.assertEqual(case['recovery_economics']['status'], 'needs_values')
