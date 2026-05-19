# routes/board_visual.py

from PIL import Image


def detect_visual_features(image_path):

    visual = {
        "wide_skinny_board": False,
        "possible_ram": False,
        "gold_finger_edge": False,
    
    # RAM shape detection
if width > height * 2:
    features["possible_ram"] = True

# Gold finger edge detection
if gold_pixels > 100:
    features["gold_finger_edge"] = True
    
    }

    try:
        img = Image.open(image_path).convert("RGB")

        width, height = img.size
    
    }

        # ADD NEW DETECTION LOGIC HERE

    except Exception as e:
        print(f"[Board Visual Error] {e}")

    return visual
        
        long_side = max(width, height)
        short_side = min(width, height)

        ratio = long_side / short_side if short_side else 0

        # RAM / expansion card shape
        if ratio >= 2.4:
            visual["wide_skinny_board"] = True
            visual["possible_ram"] = True

        # Scan lower edge for gold-colored pixels
        gold_pixels = 0
        total_pixels = 0

        scan_y_start = int(height * 0.80)

        for y in range(scan_y_start, height):
            for x in range(width):

                r, g, b = img.getpixel((x, y))

                total_pixels += 1

                # simple gold-ish color detection
                if (
                    r > 140
                    and g > 100
                    and b < 120
                ):
                    gold_pixels += 1

        if total_pixels > 0:
            gold_ratio = gold_pixels / total_pixels

            if gold_ratio > 0.08:
                visual["gold_finger_edge"] = True

    except Exception as e:
        print(f"[Board Visual Error] {e}")

    return visual
