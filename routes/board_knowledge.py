def analyze_board_knowledge(image_path: str):
    features = detect_board_features(image_path)
    visual = detect_visual_features(image_path)

    lower_name = image_path.lower()

    if "motherboard" in lower_name or "board" in lower_name:
        features["motherboard"] = True

    if visual["dense_components"]:
        features["large_ic_chips"] = True

    if visual["dark_board"]:
        features["server_grade"] = True

    score = 0

    if features["gold_fingers"]:
        score += 3
    if features["large_ic_chips"]:
        score += 3
    if features["server_grade"]:
        score += 4
    if features["telecom_board"]:
        score += 5
    if features["power_board"]:
        score += 1
    if features["heavy_components"]:
        score += 1
    if features["memory_module"]:
        score += 5
    if features["processor"]:
        score += 7
    if features["ceramic_cpu"]:
        score += 10
    if features["gold_cap_cpu"]:
        score += 12
    if features["motherboard"]:
        score += 4
    if features["pci_card"]:
        score += 5
    if features["gpu_card"]:
        score += 7
    if features["fiber_card"]:
        score += 6
    if features["military_grade"]:
        score += 10
    if features["daughterboard"]:
        score += 4
    if features["inverter_board"]:
        score += 5
    if features["low_value_board"]:
        score -= 5

    if visual["gold_like"]:
        score += 5
    if visual["dense_components"]:
        score += 3
    if visual["large_chip"]:
        score += 4
    if visual["dark_board"]:
        score += 2

    jackpot = False
    pay_dirt_ready = False
    confidence = 0.50

    if visual["gold_like"]:
        confidence += 0.10
    if visual["dense_components"]:
        confidence += 0.10
    if visual["large_chip"]:
        confidence += 0.10
    if visual["dark_board"]:
        confidence += 0.05
    if features["telecom_board"]:
        confidence += 0.10
    if features["server_grade"]:
        confidence += 0.10
    if features["processor"]:
        confidence += 0.15
    if features["ceramic_cpu"]:
        confidence += 0.20
    if features["gold_cap_cpu"]:
        confidence += 0.20

    confidence = min(confidence, 0.99)

    grade = "UNKNOWN"
    recommendation = "Manual review required. Possible processor, chip, or specialty recovery item."

    if features["gold_cap_cpu"]:
        grade = "HIGH"
        recommendation = "Gold-cap CPU signal detected. High-priority precious metal recovery review."
        pay_dirt_ready = True
    elif features["ceramic_cpu"]:
        grade = "HIGH"
        recommendation = "Ceramic CPU signal detected. High-priority manual review for precious metal recovery."
        pay_dirt_ready = True
    elif features["military_grade"]:
        grade = "HIGH"
        recommendation = "Military/aerospace board signal detected. Separate immediately for specialty recovery review."
        pay_dirt_ready = True
    elif features["processor"]:
        grade = "HIGH"
        recommendation = "Processor or specialty chip detected. Manual review recommended before scrapping."
        pay_dirt_ready = True
    elif features["gpu_card"]:
        grade = "HIGH"
        recommendation = "GPU or graphics card signal detected. Gold fingers and IC recovery potential."
        pay_dirt_ready = True
    elif features["fiber_card"]:
        grade = "HIGH"
        recommendation = "Fiber/network card signal detected. Strong telecom recovery potential."
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
    elif features["pci_card"]:
        grade = "MEDIUM"
        recommendation = "PCI/expansion card detected. Gold fingers and IC chips may add recovery value."
    elif features["motherboard"]:
        grade = "MEDIUM"
        recommendation = "Motherboard detected. Mid-grade recovery item. Sort separately from low-grade scrap."
    elif features["inverter_board"]:
        grade = "MEDIUM"
        recommendation = "Inverter or power electronics board detected. Check for copper, aluminum heat sinks, and heavy components."
    elif features["power_board"]:
        grade = "LOW"
        recommendation = "Power board detected. Recover copper, aluminum heat sinks, and transformers if labor is worth it."
    elif score >= 10:
        grade = "HIGH"
        recommendation = "High-value board signals detected. Separate for better recovery value."
        pay_dirt_ready = True
    elif score >= 5:
        grade = "MEDIUM"
        recommendation = "Mid-grade board. Worth separating from low-grade scrap."
    elif score >= 2:
        grade = "LOW"
        recommendation = "Low-grade board. Some recoverable components may be present."

    if score >= 12:
        jackpot = True
        pay_dirt_ready = True

    return {
        "grade": grade,
        "score": score,
        "confidence": round(confidence, 2),
        "jackpot": jackpot,
        "recommendation": recommendation,
        "pay_dirt_ready": pay_dirt_ready,
        "features": features,
        "visual": visual,
        "signals": make_signals(features, visual),
    }
