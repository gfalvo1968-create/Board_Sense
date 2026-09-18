"""Regression guards for SPIKE multi-board split-and-analyze mode."""
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from routes.multi_board_split import save_isolated_board_crops, split_board_regions


def _textured_board(image, p1, p2, color, seed):
    rng = np.random.default_rng(seed)
    x1, y1 = p1
    x2, y2 = p2
    cv2.rectangle(image, p1, p2, color, -1)
    cv2.rectangle(image, p1, p2, (20, 65, 25), 4)
    for _ in range(90):
        x = int(rng.integers(x1 + 8, x2 - 8))
        y = int(rng.integers(y1 + 8, y2 - 8))
        cv2.circle(image, (x, y), int(rng.integers(2, 6)), (205, 205, 205), -1)
    for _ in range(10):
        x = int(rng.integers(x1 + 12, x2 - 70))
        y = int(rng.integers(y1 + 12, y2 - 35))
        cv2.rectangle(image, (x, y), (x + 50, y + 22), (25, 25, 25), -1)


def test_three_separated_small_boards_are_split_for_independent_reports():
    image = np.full((900, 1200, 3), 34, dtype=np.uint8)
    _textured_board(image, (80, 240), (330, 720), (50, 145, 70), 1)
    _textured_board(image, (440, 260), (720, 700), (70, 110, 135), 2)
    _textured_board(image, (820, 110), (1110, 760), (45, 150, 65), 3)

    with TemporaryDirectory() as td:
        path = Path(td) / "three_boards.jpg"
        cv2.imwrite(str(path), image)
        split = save_isolated_board_crops(str(path), Path(td) / "crops")

        assert split["status"] == "SEPARATE_BOARD_REGIONS_FOUND", split
        assert split["board_count"] == 3, split
        assert len(split["crops"]) == 3, split
        assert all(Path(x["crop_path"]).exists() for x in split["crops"])


def test_one_board_does_not_become_fake_batch():
    image = np.full((800, 900, 3), 32, dtype=np.uint8)
    _textured_board(image, (160, 120), (740, 690), (48, 150, 70), 7)

    with TemporaryDirectory() as td:
        path = Path(td) / "one_board.jpg"
        cv2.imwrite(str(path), image)
        split = split_board_regions(str(path))

    assert split["status"] == "SEPARATION_NOT_PROVEN", split
    assert split["board_count"] == 0, split
