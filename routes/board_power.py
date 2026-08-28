import cv2

from routes.component_discriminator import discriminate_components


def detect_power_board(image_path):
    """Estimate true supply-board characteristics without capacitor-count bias."""
    signals = {
        "possible_power_board": False,
        "large_round_components": 0,
        "large_component_regions": 0,
        "sparse_component_layout": False,
        "power_score": 0,
        "solder_side_suppressed": False,
    }
    try:
        image = cv2.imread(image_path)
        if image is None:
            return signals
        components = discriminate_components(image_path)
        round_count = int(components.get("capacitor_like", 0))
        block_count = int(components.get("transformer_relay_like", 0))
        ic_count = int(components.get("ic_like", 0))
        solder_side = int(components.get("solder_side_likelihood", 0))
        logic_ratio = float(components.get("logic_component_ratio", 0.0))
        power_ratio = float(components.get("power_component_ratio", 0.0))

        # A solder/trace side cannot independently prove physical capacitors or
        # transformers. Preserve counts for diagnostics but remove their vote.
        effective_round = round_count
        effective_block = block_count
        if solder_side >= 65:
            effective_round = 0
            effective_block = 0
            signals["solder_side_suppressed"] = True

        signals["large_round_components"] = effective_round
        signals["large_component_regions"] = effective_block
        signals["sparse_component_layout"] = (
            effective_block >= 1 and (effective_block >= 2 or effective_round >= 3)
            and ic_count <= 6 and solder_side < 65
        )

        # Capacitor count saturates quickly. A PSU needs topology evidence such
        # as a substantial block/transformer region, not merely many small caps.
        power_score = 0
        if effective_round >= 2: power_score += 1
        if effective_round >= 6: power_score += 1
        if effective_block >= 1: power_score += 3
        if effective_block >= 2: power_score += 2
        if power_ratio >= 0.65 and solder_side < 65: power_score += 1
        if signals["sparse_component_layout"]: power_score += 2
        if ic_count >= 4 or logic_ratio >= 0.40: power_score -= 2
        if ic_count >= 8 or logic_ratio >= 0.55: power_score -= 2
        if solder_side >= 65: power_score = 0

        power_score = max(0, power_score)
        signals["power_score"] = power_score
        signals["possible_power_board"] = bool(
            power_score >= 6 and effective_block >= 1
            and (effective_round >= 2 or effective_block >= 2)
            and solder_side < 65
        )
    except Exception as exc:
        print(f"[Power Board Detector Error] {exc}")
    return signals
