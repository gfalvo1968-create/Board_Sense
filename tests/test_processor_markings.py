import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont
from routes.processor_markings import candidates_from_text, read_processor_markings, _trusted_text
from routes.processor_case import processor_case, inspect_processor


class ProcessorMarkingsTests(unittest.TestCase):
    def test_requires_brand_and_family_not_color_or_a_number(self):
        for text in ('gold yellow pins 6700', 'INTEL', 'CORE 2 DUO', 'SL9ZF', ''):
            self.assertEqual(candidates_from_text(text), [])
        self.assertEqual(candidates_from_text('INTEL(R) CORE 2 DUO\n6700 SL9ZF'), ['Intel Core 2 Duo'])
        self.assertEqual(candidates_from_text('AMD RYZEN 5'), ['AMD Ryzen'])

    def test_low_confidence_words_are_not_used(self):
        header = 'page_num\tblock_num\tpar_num\tline_num\tconf\ttext\n'
        text = _trusted_text(header + '1\t1\t1\t1\t20\tINTEL\n1\t1\t1\t1\t99\tCORE 2 DUO\n')
        self.assertEqual(candidates_from_text(text), [])

    def test_missing_ocr_fails_closed(self):
        with patch('routes.processor_markings.shutil.which', return_value=None):
            result = read_processor_markings('unused')
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['candidates'], [])

    def test_timeout_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'blank.png'
            Image.new('RGB', (400, 400), 'white').save(path)
            with patch('routes.processor_markings.shutil.which', return_value='/usr/bin/tesseract'), patch('routes.processor_markings.subprocess.run', side_effect=subprocess.TimeoutExpired('tesseract', 3)):
                result = read_processor_markings(path)
            self.assertEqual(result['status'], 'unavailable')
            self.assertEqual(result['candidates'], [])

    def test_candidate_on_later_view_does_not_confirm_other_view(self):
        base = {'board_type': 'Loose processor / CPU (user identified)', 'grade': 'WITHHELD', 'score': None, 'object_gate': {'confirmed_pcb': False}, 'processor_markings': {'candidates': []}}
        other = {**base, 'processor_markings': {'candidates': ['Intel Core 2 Duo']}}
        result = processor_case([base, other])
        self.assertEqual(result['processor_markings']['status'], 'candidate')
        self.assertIn('Intel Core 2 Duo', result['three_answers']['identity']['subtype'])
        self.assertEqual(result['grade'], 'WITHHELD')
        self.assertIsNone(result['score'])
        self.assertFalse(result['object_gate']['confirmed_pcb'])
        self.assertNotIn('recovery_economics', result)
        self.assertIn('not been independently verified', result['case_analysis']['message'])

    def test_conflicting_families_are_not_merged(self):
        result = processor_case([{'processor_markings': {'candidates': ['Intel Core 2 Duo']}, 'board_type': 'CPU'}, {'processor_markings': {'candidates': ['AMD Ryzen']}}])
        self.assertEqual(result['processor_markings']['status'], 'conflict')
        self.assertIn('Conflicting', result['three_answers']['identity']['subtype'])

    def test_real_ocr_on_control_image_and_blank(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'control.png'
            image = Image.new('RGB', (1000, 600), 'white')
            draw = ImageDraw.Draw(image)
            font_path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
            if not font_path.exists():
                self.skipTest('Control image requires DejaVu Sans')
            font = ImageFont.truetype(str(font_path), 48)
            draw.text((210, 230), 'INTEL CORE 2 DUO', fill='black', font=font)
            image.save(path)
            result = inspect_processor(path)
            self.assertEqual(result['processor_markings']['candidates'], ['Intel Core 2 Duo'])
            self.assertEqual(result['grade'], 'WITHHELD')
            Image.new('RGB', (500, 500), 'white').save(path)
            self.assertEqual(read_processor_markings(path)['candidates'], [])


if __name__ == '__main__':
    unittest.main()
