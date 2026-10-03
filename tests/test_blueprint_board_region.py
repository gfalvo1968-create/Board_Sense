import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from routes.board_blueprint import generate_blueprint, _component_geometry_guard
from routes.board_motherboard import detect_motherboard
from routes.board_region import board_region_mask
from routes.component_discriminator import discriminate_components
from routes.frame_identity_gate import inspect_frame


def package(image, x, y, w=140, h=90):
    cv2.rectangle(image, (x, y), (x+w, y+h), (24, 24, 24), -1)
    for px in range(x+8, x+w-7, 8):
        cv2.rectangle(image, (px, y-6), (px+3, y+4), (210, 210, 210), -1)
        cv2.rectangle(image, (px, y+h-4), (px+3, y+h+6), (210, 210, 210), -1)


def scene():
    # Deliberately textured background with a fully chip-like decoy outside
    # the PCB and five aligned rectangles along the PHOTO edge.
    yy, xx = np.indices((800, 1100))
    gray = (115 + 45*np.sin(xx/13) + 24*np.cos(yy/19)).clip(0, 255).astype(np.uint8)
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for y in range(150, 651, 100):
        cv2.rectangle(image, (0, y), (35, y+45), (18, 18, 18), -1)
    package(image, 75, 300)
    cv2.rectangle(image, (300, 100), (900, 700), (28, 100, 36), -1)
    package(image, 530, 260)
    return image


class BoardRegionTests(unittest.TestCase):
    def analyze(self, image, operation):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'board.png'
            cv2.imwrite(str(path), image)
            return operation(path, Path(directory)/'maps')

    def test_background_decoy_does_not_become_a_chip_or_connector_bank(self):
        def check(path, maps):
            result = discriminate_components(str(path))
            self.assertTrue(result['regions'])
            for region in result['regions']:
                self.assertGreater(region['x'] + region['w']/2, 300)
                self.assertLess(region['x'] + region['w']/2, 900)
            self.assertTrue(any(r['type']=='IC-like package' and
                                500 < r['x']+r['w']/2 < 700 for r in result['regions']))
            self.assertFalse(detect_motherboard(str(path))['edge_connector_bank'])
            blueprint = generate_blueprint(path, result['regions'], maps)
            self.assertTrue(blueprint['available'])
            self.assertTrue(blueprint['component_index'])
            self.assertNotIn('Board Edge Connector Zone', [r['label'] for r in blueprint['component_index']])
        self.analyze(scene(), check)

    def test_blueprint_rejects_an_off_board_input_region(self):
        def check(path, maps):
            regions = [{'type':'IC-like package','x':65,'y':290,'w':170,'h':120,'confidence':99},
                       {'type':'IC-like package','x':530,'y':260,'w':140,'h':90,'confidence':85}]
            result = generate_blueprint(path, regions, maps)
            self.assertEqual(len(result['component_index']), 1)
            self.assertEqual(result['board_region_guard']['rejected_background_regions'], 1)
        self.analyze(scene(), check)

    def test_warm_shadowed_solder_mask_with_repeating_traces_is_not_a_chip(self):
        image = scene()
        # A shadowed PCB patch has aligned bright traces on opposing sides,
        # but its enclosed face remains colored solder mask under warm light.
        surface = cv2.cvtColor(np.uint8([[[17, 170, 50]]]), cv2.COLOR_HSV2BGR)[0, 0]
        package(image, 740, 460, 90, 140)
        cv2.rectangle(image, (740, 465), (830, 595), tuple(int(v) for v in surface), -1)
        def check(path, maps):
            result = discriminate_components(str(path))
            self.assertTrue(any(500 < r['x']+r['w']/2 < 700 for r in result['regions']))
            self.assertFalse(any(740 < r['x']+r['w']/2 < 830 and
                                 460 < r['y']+r['h']/2 < 600 for r in result['regions']))
        self.analyze(image, check)

    def test_rotation_and_large_image_scaling_keep_markers_on_the_package(self):
        for image in [cv2.rotate(scene(), cv2.ROTATE_90_CLOCKWISE),
                      cv2.resize(scene(), (2200, 1600))]:
            def check(path, maps):
                result = discriminate_components(str(path))
                self.assertTrue(any(r['type']=='IC-like package' for r in result['regions']))
                blueprint = generate_blueprint(path, result['regions'], maps)
                mask = board_region_mask(cv2.imread(str(path)))
                for marker in blueprint['component_index']:
                    box = marker['box']
                    self.assertNotEqual(mask[box['y']+box['h']//2, box['x']+box['w']//2], 0)
            self.analyze(image, check)

    def test_uncertain_background_does_not_admit_the_whole_frame(self):
        rng = np.random.default_rng(2)
        gray = rng.integers(15, 240, (500, 700), dtype=np.uint8)
        image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        self.assertEqual(cv2.countNonZero(board_region_mask(image)), 0)
        self.analyze(image, lambda path, maps: self.assertFalse(generate_blueprint(path, [], maps)['available']))

    def test_plain_background_still_supports_a_non_green_board(self):
        image = np.full((500, 700, 3), 175, dtype=np.uint8)
        cv2.rectangle(image, (150, 100), (550, 400), (100, 35, 25), -1)
        mask = board_region_mask(image)
        self.assertNotEqual(mask[250, 350], 0)
        self.assertEqual(mask[250, 50], 0)

    def test_single_board_outline_with_notches_completes_the_identity_check(self):
        image = np.full((800, 1100, 3), 115, dtype=np.uint8)
        cv2.rectangle(image, (250, 100), (900, 700), (28, 100, 36), -1)
        cv2.rectangle(image, (370, 100), (420, 150), (115, 115, 115), -1)
        cv2.rectangle(image, (640, 650), (710, 700), (115, 115, 115), -1)
        def check(path, maps):
            result = inspect_frame(str(path))
            self.assertNotIn('error', result)
            self.assertFalse(result['block_analysis'])
            self.assertGreater(result['metrics']['deep_concavity_count'], 0)
        self.analyze(image, check)

    def test_a_withheld_connector_label_does_not_become_an_ic_claim(self):
        region = {'type':'Board-edge connector bank','x':300,'y':100,'w':40,'h':300,'confidence':78}
        self.assertEqual(_component_geometry_guard(region, 1100, 800)['type'], 'Unconfirmed connector region')
        region.update({'geometry_proof':'repeated bodies','edge_side':'left',
                       'pcb_bounds':{'x':300,'y':100,'w':600,'h':600}})
        self.assertEqual(_component_geometry_guard(region, 1100, 800)['type'], 'Board-edge connector bank')


if __name__ == '__main__':
    unittest.main()
