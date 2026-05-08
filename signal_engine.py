# signal_engine.py

def evaluate_signals(board_data):

    score = 0
    signals = []

    if board_data.get("gold_fingers"):
        score += 1
        signals.append(("gold_fingers", "green"))

    if board_data.get("large_ic_chips"):
        score += 1
        signals.append(("large_ic_chips", "green"))

    if board_data.get("server_grade"):
        score += 1
        signals.append(("server_grade", "green"))

    if board_data.get("low_value_board"):
        signals.append(("low_value_board", "red"))

    jackpot = score >= 3

    return {
        "score": score,
        "signals": signals,
        "jackpot": jackpot
    }
