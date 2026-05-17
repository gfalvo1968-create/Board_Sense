# routes/board_features.py

def detect_board_features(image_path):

    lower_name = image_path.lower()

    features = {
        "motherboard": False,
        "memory_module": False,
        "ram": False,
        "gold_fingers": False,
        "large_ic_chips": False,
        "processor": False,
        "power_board": False,
    }

    if "ram" in lower_name or "memory" in lower_name:
        features["memory_module"] = True
        features["ram"] = True
        features["gold_fingers"] = True

    if "motherboard" in lower_name or "mainboard" in lower_name:
        features["motherboard"] = True
        features["large_ic_chips"] = True
        features["processor"] = True

    if "power" in lower_name or "psu" in lower_name:
        features["power_board"] = True

    return features
