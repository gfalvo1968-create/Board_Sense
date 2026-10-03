import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from routes.board_analyzer import _supported_recovery_population
from routes.board_features import detect_board_features
from routes.board_scoring import calculate_score
from routes.component_discriminator import discriminate_components
from routes.photo_quality import assess_photo_quality


def package(image, x, y, w=90, h=55):
    cv2.rectangle(image, (x, y), (x+w, y+h), (24, 24, 24), -1)
    for px in range(x+8, x+w-7, 8):
        cv2.rectangle(image, (px, y-6), (px+3, y+4), (210, 210, 210), -1)
        cv2.rectangle(image, (px, y+h-4), (px+3, y+h+6), (210, 210, 210), -1)


def board_scene():
    yy, xx = np.indices((800, 1100))
    gray = (115+35*np.sin(xx/13)+20*np.cos(yy/19)).clip(0, 255).astype(np.uint8)
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(image, (300, 100), (900, 700), (28, 140, 36), -1)
    return image


def add_background_packages(image):
    for x in (20, 150):
        for y in range(40, 740, 95):
            package(image, x, y)


def add_printed_shadow_patches(image):
    # Bright traces and lettering on shadowed green solder mask resemble
    # package contours, but they have no physical package face.
    for x in (340, 450, 560, 670, 780):
        for y in (140, 440, 590):
            package(image, x, y, 70, 40)
            cv2.rectangle(image, (x, y+4), (x+70, y+36), (20, 70, 26), -1)
            cv2.putText(image, "J3", (x+15, y+26), cv2.FONT_HERSHEY_SIMPLEX,
                        .5, (220, 220, 220), 1)


class RecoveryPopulationTests(unittest.TestCase):
    def recovery(self, image):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"board.png"
            cv2.imwrite(str(path), image)
            raw = detect_board_features(str(path))
            population = _supported_recovery_population(
                raw, discriminate_components(str(path)), assess_photo_quality(str(path))
            )
        features = dict(raw)
        features.update(component_count=population["count"],
                        component_density=population["density"],
                        large_ic_chips=population["large_ic"],
                        dense_component_board=population["dense"],
                        processor=population["processor"])
        return raw, population, calculate_score(features)

    def test_off_board_packages_cannot_raise_recovery_population_or_score(self):
        image = board_scene()
        package(image, 530, 270, 140, 90)
        raw, baseline, score = self.recovery(image)
        add_background_packages(image)
        changed_raw, changed, changed_score = self.recovery(image)
        self.assertNotEqual(changed_raw["component_count"], raw["component_count"])
        self.assertEqual(changed, baseline)
        self.assertEqual(changed_score, score)
        self.assertEqual(changed["count"], 1)
        self.assertEqual(score, 3)

    def test_printed_board_patches_cannot_raise_recovery_population_or_score(self):
        image = board_scene()
        package(image, 530, 270, 140, 90)
        _, baseline, score = self.recovery(image)
        add_printed_shadow_patches(image)
        _, changed, changed_score = self.recovery(image)
        self.assertEqual(changed, baseline)
        self.assertEqual(changed_score, score)

    def test_an_empty_pcb_with_dark_decoys_does_not_earn_logic_points(self):
        image = board_scene()
        add_background_packages(image)
        add_printed_shadow_patches(image)
        raw, population, score = self.recovery(image)
        self.assertGreaterEqual(raw["component_count"], 8)
        self.assertEqual(population["count"], 0)
        self.assertEqual(score, 0)

    def test_real_dense_package_population_still_earns_recovery_points(self):
        image = board_scene()
        for x in (350, 520, 690):
            for y in (170, 290, 410, 530):
                package(image, x, y)
        _, population, score = self.recovery(image)
        self.assertGreaterEqual(population["count"], 8)
        self.assertTrue(population["large_ic"])
        self.assertTrue(population["dense"])
        self.assertGreaterEqual(score, 7)


if __name__ == "__main__":
    unittest.main()
