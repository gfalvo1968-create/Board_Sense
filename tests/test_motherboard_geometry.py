import os
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from routes.board_motherboard import detect_motherboard
from routes.board_region import board_region_mask
from routes.board_type import classify_board_type
from routes.equipment_subtype import infer_equipment_subtype


def scene(ports=True):
    image = np.full((1100, 1100, 3), 190, np.uint8)
    cv2.rectangle(image, (100, 100), (1000, 1000), (55, 110, 45), -1)
    for x in (350, 410):
        cv2.rectangle(image, (x, 250), (x+35, 900), (180, 70, 20), -1)
    cv2.rectangle(image, (250, 150), (800, 180), (20, 20, 20), -1)
    if ports:
        for y in (300, 550, 800):
            cv2.rectangle(image, (930, y), (995, y+45), (170, 170, 170), -1)
    else:
        for x in range(200, 850, 120):
            cv2.circle(image, (x, 975), 22, (190, 190, 190), -1)
    return image


class MotherboardGeometryTests(unittest.TestCase):
    def detect(self, image):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'board.png')
            cv2.imwrite(path, image)
            return detect_motherboard(path)

    def test_parallel_slots_and_distinct_ports_support_mainboard(self):
        result = self.detect(scene())
        self.assertTrue(result['possible_motherboard'])
        self.assertEqual(result['motherboard_score'], result['motherboard_structure_score'])

    def test_capacitor_row_cannot_replace_io_ports(self):
        result = self.detect(scene(False))
        self.assertTrue(result['confirmed_slot_bank'])
        self.assertFalse(result['edge_connector_bank'])
        self.assertFalse(result['possible_motherboard'])

    def test_architecture_outranks_generic_power_components(self):
        mb = self.detect(scene())
        result = classify_board_type({'large_ic_chips': True}, {}, mb,
                                     {'possible_power_board': True, 'power_stage_present': True})
        self.assertEqual(result['type'], 'Motherboard / Main Logic Board')
        subtype = infer_equipment_subtype({'board_type': result['type'], 'motherboard': mb})
        self.assertIn('Computer Mainboard', subtype['subtype'])

    @unittest.skipUnless(os.getenv('BOARD_SENSE_ACER_FIXTURES'), 'Optional private original-photo fixtures')
    def test_original_acer_front_back_rotation_and_resize(self):
        root = Path(os.environ['BOARD_SENSE_ACER_FIXTURES'])
        front = cv2.imread(str(root / 'IMG_5284.jpeg'))
        self.assertIsNotNone(front)
        # The original lower blue clothing must not become the PCB surface.
        self.assertEqual(int(board_region_mask(front)[1900, 900]), 0)
        for image in (front, cv2.rotate(front, cv2.ROTATE_90_CLOCKWISE),
                      cv2.resize(front, None, fx=.5, fy=.5)):
            result = self.detect(image)
            self.assertTrue(result['possible_motherboard'])
            self.assertTrue(result['confirmed_slot_bank'])
        back = detect_motherboard(str(root / 'IMG_5285.jpeg'))
        self.assertFalse(back['possible_motherboard'])
