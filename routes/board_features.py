def detect_board_features(image_path):

    lower_name = image_path.lower()

    return {
        "motherboard": "motherboard" in lower_name,
        "ram": "ram" in lower_name,
        "power_board": "power" in lower_name
    }
