import cv2
import numpy as np


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
        "gold_cap_cpu": False,
        "motherboard": False,
        "pci_card": False,
        "gpu_card": False,
        "fiber_card": False,
        "military_grade": False,
        "daughterboard": False,
        "inverter_board": False,
    }

    if any(word in name for word in ["ram", "memory", "dimm", "sodimm"]):
        features["memory_module"] = True
        features["gold_fingers"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["cpu", "processor", "procesor", "proccessor", "bga", "chip"]):
        features["processor"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["ceramic", "ceramic_cpu"]):
        features["ceramic_cpu"] = True
        features["processor"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["goldcap", "gold_cap", "gold cpu", "gold_cpu"]):
        features["gold_cap_cpu"] = True
        features["ceramic_cpu"] = True
        features["processor"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["gold", "finger", "fingers", "edge", "connector"]):
        features["gold_fingers"] = True

    if any(word in name for word in ["server", "backplane", "raid", "sas", "scsi"]):
        features["server_grade"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["telecom", "network", "router", "switch", "marconi", "cisco", "juniper"]):
        features["telecom_board"] = True
        features["server_grade"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["fiber", "optical", "sfp", "gbic"]):
        features["fiber_card"] = True
        features["telecom_board"] = True
        features["server_grade"] = True

    if any(word in name for word in ["motherboard", "mainboard", "pc_board"]):
        features["motherboard"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["pci", "pcie", "expansion", "soundcard", "nic"]):
        features["pci_card"] = True
        features["gold_fingers"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["gpu", "graphics", "video_card"]):
        features["gpu_card"] = True
        features["pci_card"] = True
        features["gold_fingers"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["power", "supply", "psu", "transformer"]):
        features["power_board"] = True
        features["heavy_components"] = True

    if any(word in name for word in ["heavy", "heat", "sink", "heatsink"]):
        features["heavy_components"] = True

    if any(word in name for word in ["military", "aerospace", "avionics", "defense"]):
        features["military_grade"] = True
        features["gold_fingers"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["daughter", "daughterboard", "module"]):
        features["daughterboard"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["inverter", "solar", "ev", "drive_board"]):
        features["inverter_board"] = True
        features["power_board"] = True
        features["heavy_components"] = True

    if any(word in name for word in ["junk", "low", "brown", "tv_board"]):
        features["low_value_board"] = True

    return features


def detect_visual_features(image_path: str):
    visual = {
        "gold_like": False,
        "dark_board": False,
        "dense_components": False,
        "large_chip": False,
        "green_board": False,
        "gold_edge": False,
    
    }

    try:
        image = cv2.imread(image_path)

        if image is None:
            return visual

        height, width = image.shape[:2]
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # GREEN PCB RANGE
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([90, 255, 255])

        green_mask = cv2.inRange(hsv, lower_green, upper_green)
        green_pixels = cv2.countNonZero(green_mask)

        if green_pixels > 5000:
           visual["green_board"] = True
        
        lower_gold = np.array([15, 70, 70])
        upper_gold = np.array([45, 255, 255])
        gold_mask = cv2.inRange(hsv, lower_gold, upper_gold)
        gold_pixels = cv2.countNonZero(gold_mask)

        if gold_pixels > 500:
            visual["gold_like"] = True

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        avg_brightness = np.mean(gray)

        if avg_brightness < 95:
            visual["dark_board"] = True

        edges = cv2.Canny(gray, 80, 180)
        edge_pixels = cv2.countNonZero(edges)

        if edge_pixels > 12000:
            visual["dense_components"] = True

        center = gray[
            height // 3 : 2 * height // 3,
            width // 3 : 2 * width // 3
        ]

        if np.mean(center) < 105:
            visual["large_chip"] = True

    except Exception as e:
        print("Visual detection error:", e)

    return visual


def make_signals(features, visual):
    return {
        "gold_fingers": (
            "green"
            if features["gold_fingers"] or visual["gold_like"]
            else "red"
        ),
        "large_ic_chips": (
            "green"
            if features["large_ic_chips"] or visual["dense_components"] or visual["large_chip"]
            else "red"
        ),
        "green_board": (
            "green"
            if visual["green_board"]
            else "red"
        ),
        "server_grade": (
            "green"
            if features["server_grade"] and (visual["dense_components"] or visual["dark_board"])
            else "orange"
            if features["server_grade"]
            else "red"
        ),
        "telecom_board": (
            "green"
            if features["telecom_board"] and (visual["dense_components"] or visual["dark_board"])
            else "orange"
            if features["telecom_board"]
            else "red"
        ),
        "power_board": (
            "orange"
            if features["power_board"] or features["inverter_board"]
            else "red"
        ),
        "heavy_components": (
            "orange"
            if features["heavy_components"]
            else "red"
        ),
    }


def analyze_board_knowledge(image_path: str):
    features = detect_board_features(image_path)
    visual = detect_visual_features(image_path)

    lower_name = image_path.lower()

    if "motherboard" in lower_name or "board" in lower_name:
        features["motherboard"] = True

    if visual["dense_components"]:
        features["large_ic_chips"] = True

    if visual["dark_board"] and visual["dense_components"] and features["large_ic_chips"]:
       features["server_grade"] = True

    score = 0

    if features["gold_fingers"]:
        score += 3
    if features["large_ic_chips"]:
        score += 3
    if visual["green_board"] and features["gold_fingers"]:
        score += 4
    if visual["green_board"] and features["large_ic_chips"]:
        score += 2
    if features["server_grade"]:
        score += 4
    if features["telecom_board"]:
        score += 5
    if features["power_board"]:
        score -= 4

    if features["heavy_components"]:
        score -= 2
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

    if visual["gold_like"] and features["gold_fingers"]:
        score += 2
    if visual["dense_components"]:
        score += 2
    if visual["large_chip"] and not features["power_board"]:
        score += 1
    if visual["dark_board"]:
        score += 1
    if visual["green_board"]:
        score += 2
    if visual["green_board"]:
        score += 1

    if visual["green_board"]:
        score += 1

    if visual["dense_components"]:
        score += 2

    if visual["large_chip"]:
        score += 2

    if visual["dark_board"]:
        score += 1   
        
         # Junk board penalty logic
    if features["power_board"] and not features["gold_fingers"]:
        score -= 4

    if features["heavy_components"] and not features["large_ic_chips"]:
        score -= 3

    if visual["green_board"] and not features["gold_fingers"] and not features["large_ic_chips"]:
        score -= 3

    if features["power_board"] and features["heavy_components"]:
        score -= 2

    score = max(score, 0)

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

    if features["power_board"] or features["heavy_components"]:
    if not features["gold_fingers"] and not features["large_ic_chips"]:
        score = min(score, 3)
        grade = "LOW"
        recommendation = "Low-value power/control board. Recover only basic copper, aluminum, or transformer value."
        pay_dirt_ready = False
    
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
    elif score >= 14:
        grade = "HIGH"
        recommendation = "High-value board signals detected. Separate for better recovery value."
        pay_dirt_ready = True
    elif score >= 5:
        grade = "MEDIUM"
        recommendation = "Mid-grade board. Worth separating from low-grade scrap."
    elif score >= 2:
        grade = "LOW"
        recommendation = "Low-grade board. Some recoverable components may be present."

    if score >= 18:
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
