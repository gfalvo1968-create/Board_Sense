# routes/board_knowledge.py

def signal_level(score: int):
    if score >= 3:
        return "green"
    if score >= 1:
        return "orange"
    return "red"


def detect_board_features(filename: str):
    name = filename.lower()

    features = {
        "gold_fingers": False,
        "large_ic_chips": False,
        "server_grade": False,
        "telecom_board": False,
        "power_board": False,
        "low_value_board": False,
        "heavy_components": False,
    }

    if "gold" in name or "finger" in name or "edge" in name:
        features["gold_fingers"] = True

    if "chip" in name or "ic" in name or "cpu" in name or "bga" in name:
        features["large_ic_chips"] = True

    if "server" in name or "telecom" in name or "network" in name:
        features["server_grade"] = True

    if "telecom" in name or "phone" in name:
        features["telecom_board"] = True

    if "power" in name or "supply" in name or "transformer" in name:
        features["power_board"] = True

    if "junk" in name or "low" in name or "brown" in name:
        features["low_value_board"] = True

    if "heavy" in name or "heat" in name or "sink" in name:
        features["heavy_components"] = True

    return features


def analyze_board_knowledge(filename: str):
    features = detect_board_features(filename)

    name = filename.lower()
    
    score = 0

    if features["gold_fingers"]:
        score += 3

    if features["large_ic_chips"]:
        score += 3

    if features["server_grade"]:
        score += 2

    if features["telecom_board"]:
        score += 2

    if features["heavy_components"]:
        score += 1

    if features["power_board"]:
        score -= 1

    if features["low_value_board"]:
        score -= 2

    signals = {
        "gold_fingers": signal_level(3 if features["gold_fingers"] else 0),
        "large_ic_chips": signal_level(3 if features["large_ic_chips"] else 0),
        "server_grade": signal_level(3 if features["server_grade"] else 0),
        "telecom_board": signal_level(3 if features["telecom_board"] else 0),
        "power_board": signal_level(1 if features["power_board"] else 0),
        "heavy_components": signal_level(1 if features["heavy_components"] else 0),
    }

    jackpot = (
        signals["gold_fingers"] == "green"
        and signals["large_ic_chips"] == "green"
        and not features["low_value_board"]
    )

    if jackpot:
        grade = "HIGH"
        recommendation = "JACKPOT — this board should be reviewed in Pay_Dirt for recovery."
    elif score >= 5:
        grade = "HIGH"
        recommendation = "Strong board. Sort as high grade or review for recovery."
    elif score >= 3:
        grade = "MEDIUM"
        recommendation = "Medium board. Inspect chips, fingers, and connectors before selling."
    elif score >= 1:
        grade = "LOW"
        recommendation = "Low signal board. Useful for training or low-grade scrap."
    else:
        grade = "JUNK"
        recommendation = "Weak signal board. Scrap only unless visual inspection says otherwise."

    return {
        "features": features,
        "signals": signals,
        "score": score,
        "grade": grade,
        "jackpot": jackpot,
        "recommendation": recommendation,
        "pay_dirt_ready": jackpot or grade == "HIGH",
    }
