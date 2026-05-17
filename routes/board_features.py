# routes/board_features.py

def detect_board_features(image_path: str):
    lower_name = str(image_path).lower()

    features = {
        "motherboard": False,
        "memory_module": False,
        "ram": False,
        "power_board": False,
        "gold_fingers": False,
        "large_ic_chips": False,
        "processor": False,
    }

    if "motherboard" in lower_name or "mainboard" in lower_name:
        features["motherboard"] = True

    if "ram" in lower_name or "memory" in lower_name:
        features["ram"] = True
        features["memory_module"] = True
        features["gold_fingers"] = True
        features["large_ic_chips"] = True

    if "power" in lower_name or "psu" in lower_name:
        features["power_board"] = True

    if "cpu" in lower_name or "processor" in lower_name:
        features["processor"] = True

    return features
