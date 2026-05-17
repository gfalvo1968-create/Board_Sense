from routes.board_features import detect_board_features
from routes.board_scoring import calculate_score

def analyze_board(image_path):

    features = detect_board_features(image_path)

    score = calculate_score(features)

    if score <= 3:
        grade = "LOW"
    elif score <= 7:
        grade = "MEDIUM"
    else:
        grade = "HIGH"

    return {
        "score": score,
        "grade": grade
    }
