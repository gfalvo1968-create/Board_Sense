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
        "memory_module": False,
        "processor": False,
        "ceramic_cpu": False,
        "motherboard": False,
    }

    if "ram" in name or "memory" in name or "dimm" in name or "sodimm" in name:
        features["memory_module"] = True
        features["gold_fingers"] = True
        features["large_ic_chips"] = True

    if "cpu" in name or "processor" in name or "chip" in name or "bga" in name:
        features["processor"] = True
        features["large_ic_chips"] = True

    if "ceramic" in name or "goldcap" in name or "gold_cap" in name:
        features["ceramic_cpu"] = True
        features["processor"] = True
        features["large_ic_chips"] = True

    if "gold" in name or "finger" in name or "edge" in name:
        features["gold_fingers"] = True

    if "server" in name or "backplane" in name or "raid" in name:
        features["server_grade"] = True
        features["large_ic_chips"] = True

    if "telecom" in name or "network" in name or "router" in name or "switch" in name:
        features["telecom_board"] = True
        features["server_grade"] = True
        features["large_ic_chips"] = True

    if "motherboard" in name or "mainboard" in name or "pc_board" in name:
        features["motherboard"] = True
        features["large_ic_chips"] = True

    if "power" in name or "supply" in name or "psu" in name or "transformer" in name:
        features["power_board"] = True
        features["heavy_components"] = True

    if "heavy" in name or "heat" in name or "sink" in name or "heatsink" in name:
        features["heavy_components"] = True

    if "junk" in name or "low" in name or "brown" in name:
        features["low_value_board"] = True

    return features


def make_signals(features):
    return {
        "gold_fingers": "green" if features["gold_fingers"] else "red",
        "large_ic_chips": "green" if features["large_ic_chips"] else "red",
        "server_grade": "green" if features["server_grade"] else "red",
        "telecom_board": "green" if features["telecom_board"] else "red",
        "power_board": "orange" if features["power_board"] else "red",
        "heavy_components": "orange" if features["heavy_components"] else "red",
    }


def analyze_board_knowledge(filename: str):
    features = detect_board_features(filename)

    score = 0

    if features["gold_fingers"]:
        score += 3

    if features["large_ic_chips"]:
        score += 3

    if features["server_grade"]:
        score += 3

    if features["telecom_board"]:
        score += 3

    if features["motherboard"]:
        score += 2

    if features["power_board"]:
        score += 1

    if features["heavy_components"]:
        score += 1

    if features["memory_module"]:
        score += 4

    if features["processor"]:
        score += 5

    if features["ceramic_cpu"]:
        score += 5

    if features["low_value_board"]:
        score -= 4

    jackpot = False
    pay_dirt_ready = False

    if features["ceramic_cpu"]:
        grade = "HIGH"
        recommendation = "Ceramic or gold-cap CPU signal detected. High-priority manual review for precious metal recovery."
        pay_dirt_ready = True

    elif features["processor"]:
        grade = "HIGH"
        recommendation = "Processor or specialty chip detected. Manual review recommended before scrapping."
        pay_dirt_ready = True

    elif features["telecom_board"]:
        grade = "HIGH"
        recommendation = "Telecom/network board signal detected. Strong IC and recovery potential."
        pay_dirt_ready = True

    elif features["server_grade"]:
        grade = "HIGH"
        recommendation = "Server-grade board signal detected. Separate from mixed boards."
        pay_dirt_ready = True

    elif features["memory_module"]:
        grade = "MEDIUM"
        recommendation = "Memory module detected. Gold fingers and recoverable IC chips present."
        pay_dirt_ready = True

    elif score >= 8:
        grade = "HIGH"
        recommendation = "High-value board signals detected. Separate for better recovery value."
        pay_dirt_ready = True

    elif score >= 5:
        grade = "MEDIUM"
        recommendation = "Mid-grade board. Worth separating from low-grade scrap."

    elif score >= 2:
        grade = "LOW"
        recommendation = "Low-grade board. Some recoverable components may be present."

    else:
        grade = "JUNK"
        recommendation = "Weak signal board. Scrap only unless visual inspection says otherwise."

    if score >= 10:
        jackpot = True
        pay_dirt_ready = True

    return {
        "grade": grade,
        "score": score,
        "jackpot": jackpot,
        "recommendation": recommendation,
        "pay_dirt_ready": pay_dirt_ready,
        "features": features,
        "signals": make_signals(features),
    }
