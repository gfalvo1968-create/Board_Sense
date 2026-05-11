import cv2
import numpy as np
from PIL import Image

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

    if any(word in name for word in ["cpu", "processor", "bga", "chip"]):
        features["processor"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["ceramic", "ceramic_cpu"]):
        features["ceramic_cpu"] = True
        features["processor"] = True
        features["large_ic_chips"] = True

    if any(word in name for word in ["goldcap", "gold_cap", "gold cpu", "gold_cpu"]):
        features["gold_cap_cpu"] = True
        features["processor"] = True
        features["ceramic_cpu"] = True
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
        "large_chip": False
    }

    try:
        image = cv2.imread(image_path)

        if image is None:
            return visual

        height, width = image.shape[:2]

        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # GOLD COLOR RANGE
        lower_gold = np.array([15, 80, 80])
        upper_gold = np.array([40, 255, 255])

        gold_mask = cv2.inRange(hsv, lower_gold, upper_gold)
        gold_pixels = cv2.countNonZero(gold_mask)

        if gold_pixels > 500:
            visual["gold_like"] = True

        # DARK BOARD CHECK
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        avg_brightness = np.mean(gray)

        if avg_brightness < 90:
            visual["dark_board"] = True

        # EDGE DENSITY
        edges = cv2.Canny(gray, 100, 200)
        edge_pixels = cv2.countNonZero(edges)

        if edge_pixels > 15000:
            visual["dense_components"] = True

        # LARGE CENTER CHIP DETECTION
        center = gray[
            height//3:2*height//3,
            width//3:2*width//3
        ]

        if np.mean(center) < 100:
            visual["large_chip"] = True

    except Exception as e:
        print("Visual detection error:", e)

    return visual


def make_signals(features):
    return {
       
        "gold_fingers": (
    "green"
    if features["gold_fingers"] and visual["gold_like"]
    else "orange"
    if features["gold_fingers"]
    else "red"
),
        "large_ic_chips": (
    "green"
    if features["large_ic_chips"] and visual["dense_components"]
    else "orange"
    if features["large_ic_chips"]
    else "red"
),
         "server_grade": (
    "green"
    if features["server_grade"] and visual["dense_components"]
    else "orange"
    if features["server_grade"]
    else "red"
),
         "telecom_board": (
    "green"
    if features["telecom_geade"] and visual["dense_components"]
    else "orange"
    if features["telecom_grade"]
    else "red"
),
         "power_board": (
    "green"
    if features["power_board"] and visual["dence_components"]
    else "orange"
    if features["power_board"]
    else "red"
 ),
        "heavy_components": (
    "green"
    if features["heavy_components"]and visual["dence_cmponents"]
    else "orange"
    if features["heavy_components"]
    else "red"
 ),
    
    }


def analyze_board_knowledge(filename: str):
    features = detect_board_features(filename)
    visual = detect_visual_features(filename)
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

    jackpot = False
    pay_dirt_ready = False

    if features["gold_cap_cpu"]:
        grade = "HIGH"
        recommendation = "Gold-cap CPU signal detected. High-priority precious metal recovery review."
        pay_dirt_ready = True

        # VISUAL AI SCORING
    confidence = 0.50
    if visual["gold_like"]:
       score += 10

    if visual["dense_components"]:
       score += 10

    if visual["large_chip"]:
       score += 15

    if visual["dark_board"]:
       score += 20
    
    confidence = min(confidence, 0.99)

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

    else:
        grade = "JUNK"
        recommendation = "Weak signal board. Scrap only unless visual inspection says otherwise."

    if score >= 12:
        jackpot = True
        pay_dirt_ready = True

      return {
        "grade": grade,
        "score": score,
        return {
    "grade": grade,
    "score": score,
    "confidence": round(confidence, 2),
    "jackpot": jackpot,
    "recommendation": recommendation,
    "pay_dirt_ready": pay_dirt_ready,
    "features": features,
    "signals": make_signals(features),
}
        "jackpot": jackpot,
        "recommendation": recommendation,
        "pay_dirt_ready": pay_dirt_ready,
        "features": features,
        "signals": make_signals(features),
    }
