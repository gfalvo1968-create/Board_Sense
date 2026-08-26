from routes.board_features import detect_board_features
from routes.board_visual import detect_visual_features
from routes.board_scoring import calculate_score
from routes.board_motherboard import detect_motherboard
from routes.board_confidence import calculate_confidence
from routes.board_insight import BoardInsight


def analyze_board(image_path):
    # Detect board characteristics
    features = detect_board_features(image_path)
    visual = detect_visual_features(image_path)
    motherboard = detect_motherboard(image_path)

    # Improve feature detection
    if visual.get("possible_ram", False):
        features["ram"] = True
        features["memory_module"] = True
        features["gold_fingers"] = True

    if visual.get("gold_finger_edge", False):
        features["gold_fingers"] = True

    if motherboard.get("possible_motherboard", False):
        features["motherboard"] = True

    # Calculate score
    score = calculate_score(features)

    # Calculate confidence from the score plus corroborating detector evidence
    confidence = calculate_confidence(
        score,
        features=features,
        visual=visual,
        motherboard=motherboard,
    )

    # Grade and recommendation
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

    # Build final result
    result = {
        "grade": grade,
        "confidence": confidence,
        "score": score,
        "pay_dirt_ready": pay_dirt_ready,
        "recommendation": recommendation,
        "features": features,
        "visual": visual,
        "signals": {
            "motherboard": features.get("motherboard", False),
            "ram": features.get("ram", False),
            "power_board": features.get("power_board", False),
            "possible_ram": visual.get("possible_ram", False),
            "gold_finger_edge": visual.get("gold_finger_edge", False),
            "possible_motherboard": motherboard.get(
                "possible_motherboard", False
            ),
            "large_board": motherboard.get("large_board", False),
        },
        "model": "Board Sense v0.7",
    }

    # Generate insight
    insight_engine = BoardInsight()
    result["insight"] = insight_engine.generate(result)

    return result

