# routes/board_analyzer.py

from routes.board_features import detect_board_features
from routes.board_scoring import calculate_score


def analyze_board(image_path):

    features = detect_board_features(image_path)

    score = calculate_score(features)

    grade = "LOW"
    confidence = 0.50
    recommendation = "Basic scan completed."
    pay_dirt_ready = False

    if score >= 10:
        grade = "HIGH"
        confidence = 0.95
        pay_dirt_ready = True
        recommendation = "High value recovery candidate."

    elif score >= 5:
        grade = "MEDIUM"
        confidence = 0.75
        recommendation = "Worth separating for recovery."

    elif score <= 1:
        grade = "LOW"
        confidence = 0.50
        recommendation = "Low value board."

    return {
        "grade": grade,
        "confidence": confidence,
        "score": score,
        "pay_dirt_ready": pay_dirt_ready,
        "recommendation": recommendation,
        "features": features,
        "signals": {
            "motherboard": features.get("motherboard"),
            "ram": features.get("ram"),
            "power_board": features.get("power_board"),
        },
        "model": "Autodidact Modular Core"
    }
