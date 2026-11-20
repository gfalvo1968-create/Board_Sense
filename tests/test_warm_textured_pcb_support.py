"""Regression controls for relay-heavy boards on warm textured surfaces.

Synthetic scenes only: do not check customer-uploaded photographs into GitHub.
"""
import unittest

import cv2
import numpy as np

from routes.board_region import board_region_mask


def warm_background():
    yy, xx = np.indices((1200, 900))
    value = np.clip(
        125 + 72 * np.sin(xx / 17) + 30 * np.cos(yy / 24), 35, 220
    ).astype(np.uint8)
    hsv = np.dstack([
        np.full((1200, 900), 22, np.uint8),
        np.full((1200, 900), 125, np.uint8),
        value,
    ])
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def fragmented_power_board():
    image = warm_background()
    cv2.rectangle(image, (180, 130), (730, 1050), (35, 110, 37), -1)
    # Multiple tall dark relay-style bodies obscure much of the green PCB;
    # exposed solder mask survives as several separated islands.
    for x, y, w, h in ((190, 155, 230, 250),
                       (450, 180, 250, 260),
                       (260, 480, 390, 280)):
        cv2.rectangle(image, (x, y), (x + w, y + h),
                      (28, 29, 33), -1)
    cv2.rectangle(image, (180, 430), (730, 680), (28, 29, 33), -1)
    for x1, y1, x2, y2 in ((210, 140, 400, 182),
                           (485, 140, 690, 182),
                           (210, 275, 360, 320)):
        cv2.rectangle(image, (x1, y1), (x2, y2),
                      (35, 110, 37), -1)
    for x, y in ((325, 810), (545, 820)):
        cv2.circle(image, (x, y), 65, (90, 90, 100), -1)
    for x, y in ((265, 670), (670, 675)):
        cv2.rectangle(image, (x, y), (x + 65, y + 75),
                      (21, 21, 25), -1)
    # Populated texture is required. A smooth green panel is not a PCB.
    for y in range(700, 1020, 12):
        for x in range(205, 700, 20):
            cv2.rectangle(image, (x, y), (x + 11, y + 7),
                          (0, 0, 0), -1)
    return image


class WarmTexturedPCBSupportTests(unittest.TestCase):
    def test_fragmented_relay_heavy_pcb_region_without_cloth(self):
        for image in (fragmented_power_board(),
                      cv2.resize(fragmented_power_board(), (750, 1000))):
            mask = board_region_mask(image)
            self.assertGreater(cv2.countNonZero(mask), mask.size * .12)
            self.assertEqual(int(mask[30, 30]), 0)
            self.assertEqual(int(mask[mask.shape[0] // 2, 30]), 0)
            self.assertNotEqual(int(mask[int(mask.shape[0] * .8),
                                         int(mask.shape[1] * .5)]), 0)

    def test_obscured_relay_board_against_plain_light_paper(self):
        image = fragmented_power_board()
        # Preserve the real synthetic populated board while replacing the
        # warm textile border with uniform off-white paper.
        paper = np.full_like(image, 214)
        paper[130:1051, 180:731] = image[130:1051, 180:731]
        for view in (paper, cv2.rotate(paper, cv2.ROTATE_90_CLOCKWISE)):
            mask = board_region_mask(view)
            self.assertGreater(cv2.countNonZero(mask), mask.size * .10)
            self.assertEqual(int(mask[20, 20]), 0)

    def test_single_populated_green_surface_on_neutral_paper(self):
        image = np.full((1000, 850, 3), 212, np.uint8)
        cv2.rectangle(image, (185, 115), (665, 905), (33, 118, 40), -1)
        for row in range(7):
            for col in range(5):
                x, y = 225 + col * 85, 170 + row * 98
                cv2.rectangle(image, (x, y), (x + 48, y + 55),
                              (28, 30, 31), -1)
                cv2.line(image, (x + 9, y + 62), (x + 42, y + 62),
                         (220, 225, 228), 2)
        mask = board_region_mask(image)
        self.assertGreater(cv2.countNonZero(mask), mask.size * .15)
        self.assertEqual(int(mask[35, 35]), 0)

    def test_plain_green_panel_has_no_population_support(self):
        image = warm_background()
        cv2.rectangle(image, (180, 130), (730, 1050),
                      (35, 110, 37), -1)
        self.assertEqual(cv2.countNonZero(board_region_mask(image)), 0)

    def test_two_separate_green_objects_do_not_get_unified(self):
        image = warm_background()
        cv2.rectangle(image, (140, 280), (390, 920), (35, 110, 37), -1)
        cv2.rectangle(image, (510, 280), (760, 920), (35, 110, 37), -1)
        for x in (140, 510):
            for y in range(300, 900, 24):
                cv2.rectangle(image, (x + 40, y), (x + 90, y + 9),
                              (0, 0, 0), -1)
        self.assertEqual(cv2.countNonZero(board_region_mask(image)), 0)


if __name__ == "__main__":
    unittest.main()
