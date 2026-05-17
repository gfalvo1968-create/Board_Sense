# routes/board_features.py

import os


def detect_board_features(image_path):

    filename = os.path.basename(image_path).lower()

    features = {
        "motherboard": False,
        "ram": False,
        "power_board": False,
    }

    # RAM detection
    if (
        "ram" in filename
        or "memory" in filename
        or "dimm" in filename
    ):
        features["ram"] = True

    # Motherboard detection
    if (
        "motherboard" in filename
        or "mainboard" in filename
        or "logic" in filename
        or "laptop" in filename
    ):
        features["motherboard"] = True

    # Power supply board detection
    if (
        "psu" in filename
        or "power" in filename
        or "supply" in filename
    ):
        features["power_board"] = True

    return features
