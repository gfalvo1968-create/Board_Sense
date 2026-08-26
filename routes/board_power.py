import cv2

from routes.component_discriminator import discriminate_components


def detect_power_board(image_path):
    """Estimate whether a board has power-supply-style visual characteristics.

    v0.2 deliberately reuses the filtered component discriminator instead of
    running an independent permissive Hough-circle detector. This prevents
    solder pads, holes, printed circles, and background texture from inflating
    the power-board score.
    """
    signals = {
        "possible_power_board": False,
        "large_round_components": 0,
        "large_component_regions": 0,
        "sparse_component_layout": False,
        "power_score": 0,
    }

    try:
        image = cv2.imread(image_path)
        if image is None:
            return signals

        components = discriminate_components(image_path)
        round_count = int(components.get("capacitor_like", 0))
        block_count = int(components.get("transformer_relay_like", 0))
        ic_count = int(components.get("ic_like", 0))
        logic_ratio = float(components.get("logic_component_ratio", 0.0))
        power_ratio = float(components.get("power_component_ratio", 0.0))

        signals["large_round_components"] = round_count
        signals["large_component_regions"] = block_count

        # True supply boards tend to have multiple substantial power parts and
        # fewer logic packages. Do not call a dense logic board a power board
        # merely because several circular features were visible.
        signals["sparse_component_layout"] = (
            (block_count >= 2 or round_count >= 4)
            and ic_count <= max(8, round_count + block_count)
        )

        power_score = 0
        if round_count >= 2:
            power_score += 1
        if round_count >= 5:
            power_score += 1
        if block_count >= 1:
            power_score += 2
        if block_count >= 2:
            power_score += 2
        if power_ratio >= 0.60:
            power_score += 2
        if signals["sparse_component_layout"]:
            power_score += 2

        # Logic-heavy evidence actively pushes against a power-board verdict.
        if ic_count >= 5 or logic_ratio >= 0.45:
            power_score -= 2
        if ic_count >= 10 or logic_ratio >= 0.60:
            power_score -= 2

        power_score = max(0, power_score)
        signals["power_score"] = power_score
        signals["possible_power_board"] = (
            power_score >= 6
            and (block_count >= 1 or round_count >= 4)
            and power_ratio > logic_ratio
        )

    except Exception as exc:
        print(f"[Power Board Detector Error] {exc}")

    return signals
