# routes/board_visual.py

from PIL import Image


def detect_visual_features(image_path):
    visual = {
        "wide_skinny_board": False,
        "possible_ram": False,
        "gold_finger_edge": False,
    }

    try:
        img = Image.open(image_path).convert("RGB")
        width, height = img.size

        long_side = max(width, height)
        short_side = min(width, height)

        ratio = long_side / short_side if short_side else 0

        if ratio >= 2.4:
            visual["wide_skinny_board"] = True
            visual["possible_ram"] = True

        gold_pixels = 0
        total_pixels = 0

        scan_y_start = int(height * 0.75)

        for y in range(scan_y_start, height):
            for x in range(width):
                r, g, b = img.getpixel((x, y))
                total_pixels += 1

                if r > 140 and g > 95 and b < 130:
                    gold_pixels += 1

        if total_pixels > 0:
            gold_ratio = gold_pixels / total_pixels

            if gold_ratio > 0.06:
                visual["gold_finger_edge"] = True

    except Exception as e:
        print(f"[Board Visual Error] {e}")

    return visual
