from routes.board_analyzer import analyze_board


class BoardAI:
    def predict_board(self, filename):
        result = analyze_board(filename)

        return {
            "grade": result.get("grade", "UNKNOWN"),
            "confidence": result.get("confidence", 0.50),
            "signals": result.get("signals", {}),
            "score": result.get("score", 0),
            "jackpot": result.get("jackpot", False),
            "recommendation": result.get("recommendation", "Basic scan completed."),
            "pay_dirt_ready": result.get("pay_dirt_ready", False),
            "features": result.get("features", {}),
            "model": result.get("model", "Autodidact Modular Core"),
        }


board_ai = BoardAI()
