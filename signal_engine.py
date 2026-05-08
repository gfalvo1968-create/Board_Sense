# signal_engine.py

def light_from_strength(strength: int):
    if strength >= 3:
        return "green"
    if strength >= 1:
        return "orange"
    return "red"


def evaluate_signals(board_data):
    score = 0
    signals = {}

    gold_strength = 0
    if board_data.get("gold_fingers"):
        gold_strength += 3
        score += 3

    chip_strength = 0
    if board_data.get("large_ic_chips"):
        chip_strength += 3
        score += 2

    server_strength = 0
    if board_data.get("server_grade"):
        server_strength += 3
        score += 2

    low_value = board_data.get("low_value_board", False)

    signals["gold_fingers"] = light_from_strength(gold_strength)
    signals["large_ic_chips"] = light_from_strength(chip_strength)
    signals["server_grade"] = light_from_strength(server_strength)
    signals["low_value_board"] = "red" if low_value else "green"

    jackpot = (
        signals["gold_fingers"] == "green"
        and signals["large_ic_chips"] == "green"
        and not low_value
    )

    if jackpot:
        recommendation = "JACKPOT — this board should be reviewed in Pay_Dirt."
    elif score >= 4:
        recommendation = "Strong board — likely worth sorting or selling as higher grade."
    elif score >= 2:
        recommendation = "Medium board — inspect before selling."
    else:
        recommendation = "Low signal board — likely scrap or training material."

    return {
        "score": score,
        "signals": signals,
        "jackpot": jackpot,
        "recommendation": recommendation,
    }
