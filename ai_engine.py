from routes.board_analyzer import analyze_board


class BoardAI:
    def __init__(self):
        self.model_name = "BoardSense Hybrid AI v1"

    def load_model(self):
        return {
            "status": "loaded",
            "model": self.model_name
        }

    def predict_board(self, filename: str):
        knowledge = analyze_board_knowledge(filename)

        confidence = 0.50

        if knowledge["grade"] == "HIGH":
            confidence = 0.92
        elif knowledge["grade"] == "MEDIUM":
            confidence = 0.78
        elif knowledge["grade"] == "LOW":
            confidence = 0.62
        elif knowledge["grade"] == "JUNK":
            confidence = 0.40

        grade = knowledge["grade"]
        recommendation = knowledge["recommendation"]

        if confidence < 0.60 or grade == "JUNK":
            grade = "UNKNOWN"
            recommendation = "Manual review required. Possible processor, chip, or specialty recovery item."

        return {
            "model": self.model_name,
            "grade": grade,
            "confidence": confidence,
            "signals": knowledge["signals"],
            "score": knowledge["score"],
            "jackpot": knowledge["jackpot"],
            "recommendation": recommendation,
            "pay_dirt_ready": knowledge["pay_dirt_ready"],
            "features": knowledge["features"]
        }


board_ai = BoardAI()
