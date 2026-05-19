# routes/board_motherboard.py

from PIL import Image


def detect_motherboard(image_path):
    signals = {
        "large_board": False,
        "possible_motherboard": False
    }

    try:
        img = Image.open(image_path)
        width, height = img.size

        long_side = max(width, height)
        short_side = min(width, height)

        ratio = long_side / short_side if short_side else 0

        # Motherboards are usually larger and not super skinny like RAM
        if ratio < 2.2 and long_side > 700:
            signals["large_board"] = True
            signals["possible_motherboard"] = True

    except Exception as e:
        print(f"[Motherboard Detector Error] {e}")

    return signals
