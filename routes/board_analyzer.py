from routes.board_features import detect_board_features
from routes.board_visual import detect_visual_features
from routes.board_scoring import calculate_score
from routes.board_motherboard import detect_motherboard
from routes.board_power import detect_power_board
from routes.board_type import classify_board_type
from routes.board_confidence import calculate_confidence
from routes.board_insight import BoardInsight


def analyze_board(image_path):
    features = detect_board_features(image_path)
    visual = detect_visual_features(image_path)
    motherboard = detect_motherboard(image_path)
    power = detect_power_board(image_path)

    if visual.get("possible_ram", False):
        features["ram"] = True
        features["memory_module"] = True

    if visual.get("gold_finger_edge", False):
        features["gold_fingers"] = True

    if visual.get("possible_large_ic_chips", False):
        features["large_ic_chips"] = True

    if motherboard.get("possible_motherboard", False):
        features["motherboard"] = True

    if power.get("possible_power_board", False):
        features["power_board"] = True

    board_type = classify_board_type(
        features,
        visual,
        motherboard,
        power,
    )

    score = calculate_score(features)

    confidence = calculate_confidence(
        score,
        features=features,
        visual=visual,
        motherboard=motherboard,
        power=power,
    )

    if score >= 10:
        grade = "HIGH"
        recommendation = "High value recovery candidate."
        pay_dirt_ready = True
    elif score >= 5:
        grade = "MEDIUM"
        recommendation = "Worth separating for recovery."
        pay_dirt_ready = False
    else:
        grade = "LOW"
        recommendation = "Low value board."
        pay_dirt_ready = False

    result = {
        "grade": grade,
        "confidence": confidence,
        "score": score,
        "board_type": board_type["type"],
        "board_type_reason": board_type["reason"],
        "pay_dirt_ready": pay_dirt_ready,
        "recommendation": recommendation,
        "features": features,
        "visual": visual,
        "power": power,
        "signals": {
            "motherboard": features.get("motherboard", False),
            "ram": features.get("ram", False),
            "power_board": features.get("power_board", False),
            "gold_fingers": features.get("gold_fingers", False),
            "large_ic_chips": features.get("large_ic_chips", False),
            "dense_component_board": features.get("dense_component_board", False),
            "processor": features.get("processor", False),
            "component_count": features.get("component_count", 0),
            "component_density": features.get("component_density", 0.0),
            "possible_ram": visual.get("possible_ram", False),
            "gold_finger_edge": visual.get("gold_finger_edge", False),
            "possible_large_ic_chips": visual.get(
                "possible_large_ic_chips", False
            ),
            "possible_motherboard": motherboard.get(
                "possible_motherboard", False
            ),
            "large_board": motherboard.get("large_board", False),
            "possible_power_board": power.get("possible_power_board", False),
            "large_round_components": power.get("large_round_components", 0),
            "large_component_regions": power.get("large_component_regions", 0),
            "power_score": power.get("power_score", 0),
        },
        "model": "Board Sense v1.0",
    }

    insight_engine = BoardInsight()
    result["insight"] = insight_engine.generate(result)

    return result
