# routes/board_analyzer.py

from routes.board_features import detect_board_features
from routes.board_visual import detect_visual_features
from routes.board_scoring import calculate_score
from routes.board_motherboard import detect_motherboard_signals

def analyze_board(image_path):

    features = detect_board_features(image_path)
    visual = detect_visual_features(image_path)

    if visual.get("possible_ram"):
        features["ram"] = True
        features["memory_module"] = True
        features["gold_fingers"] = True

    if visual.get("gold_finger_edge"):
        features["gold_fingers"] = True
    
    score = calculate_score(features)

    grade = "LOW"
    confidence = 0.50
    recommendation = "Low value board."
    pay_dirt_ready = False

    if score >= 10:
        grade = "HIGH"
        confidence = 0.90
        pay_dirt_ready = True
        recommendation = "High value recovery candidate."

    elif score >= 5:
        grade = "MEDIUM"
        confidence = 0.75
        recommendation = "Worth separating for recovery."

        motherboard_signals, motherboard_score = detect_motherboard_signals(
        features,
        visual_data
)

        features["motherboard_signals"] = motherboard_signals

    if motherboard_score >= 3:
        features["motherboard"] = True
        score += 12

return {
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
        },
        "model": "Autodidact Modular Core"
    }
