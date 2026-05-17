# routes/board_visual.py

from PIL import Image


def detect_visual_features(image_path):
    visual = {
        "wide_skinny_board": False,
        "possible_ram": False,
    }

    try:
        img = Image.open(image_path)
        width, height = img.size

        long_side = max(width, height)
        short_side = min(width, height)

        if short_side > 0:
            ratio = long_side / short_side
        else:
            ratio = 0

        # RAM sticks are usually long and skinny
        if ratio >= 2.4:
            visual["wide_skinny_board"] = True
            visual["possible_ram"] = True

    except Exception as e:
        print(f"[Board Visual Error] {e}")

    return visual
