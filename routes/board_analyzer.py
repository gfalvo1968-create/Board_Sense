from routes.board_features import detect_board_features
from routes.board_visual import detect_visual_features
from routes.board_scoring import calculate_score
from routes.board_motherboard import detect_motherboard
from routes.board_power import detect_power_board
from routes.board_type import classify_board_type
from routes.board_confidence import calculate_confidence
from routes.board_insight import BoardInsight
from routes.reference_loader import get_knowledge
from routes.reference_reasoner import build_reference_matches
from routes.component_discriminator import discriminate_components
from routes.spike_glass import recognize as spike_glass_recognize
from routes.photo_quality import assess_photo_quality
from recovery_lab.core.recovery_engine import build_recovery_plan


def _grade_from_reference(score):
    rules = get_knowledge().get("board_grade", [])
    for rule in rules:
        score_range = rule.get("score_range", [])
        if len(score_range) != 2:
            continue
        low, high = score_range
        if low <= score <= high:
            return {
                "grade": rule.get("grade", "UNKNOWN"),
                "recommendation": rule.get("recommended_action", "Manual review recommended."),
                "pay_dirt_ready": bool(rule.get("pay_dirt_ready", False)),
                "recovery_signals": rule.get("recovery_signals", []),
                "grade_notes": rule.get("notes", ""),
            }
    if score >= 22:
        return {"grade": "VERY HIGH", "recommendation": "Separate immediately and store securely.", "pay_dirt_ready": True, "recovery_signals": ["high precious metal potential"], "grade_notes": "Premium recovery candidate."}
    if score >= 16:
        return {"grade": "HIGH", "recommendation": "Separate from mixed board loads.", "pay_dirt_ready": True, "recovery_signals": ["moderate to high precious metal recovery"], "grade_notes": "Strong recovery potential."}
    if score >= 9:
        return {"grade": "MEDIUM", "recommendation": "Sort into medium-grade categories.", "pay_dirt_ready": False, "recovery_signals": ["moderate recovery value"], "grade_notes": "Average recovery category."}
    return {"grade": "LOW", "recommendation": "Recover copper, aluminum, transformers, or bulk shred value.", "pay_dirt_ready": False, "recovery_signals": ["limited precious metal recovery"], "grade_notes": "Low-value or mixed recovery material."}


def _agreement(simple_type, top_hypothesis):
    if not top_hypothesis:
        return {"status": "insufficient_evidence", "message": "Weighted reasoner did not produce a strong competing hypothesis."}
    weighted_type = top_hypothesis.get("type", "Unknown")
    simple_lower = simple_type.lower()
    weighted_lower = weighted_type.lower()
    keyword_groups = [("ram", "memory"), ("power", "supply"), ("motherboard", "logic"), ("telecom", "network"), ("expansion", "gold finger"), ("processor",), ("server", "enterprise")]
    agrees = any(any(word in simple_lower for word in group) and any(word in weighted_lower for word in group) for group in keyword_groups)
    return {
        "status": "agree" if agrees else "review",
        "simple_classifier": simple_type,
        "weighted_hypothesis": weighted_type,
        "weighted_confidence": top_hypothesis.get("hypothesis_confidence", 0),
        "message": "Independent classifiers agree on the same broad board family." if agrees else "Independent classifiers disagree; keep the result conservative and review the evidence.",
    }


def analyze_board(image_path):
    photo_quality = assess_photo_quality(image_path)
    features = detect_board_features(image_path)
    visual = detect_visual_features(image_path)
    motherboard = detect_motherboard(image_path)
    power = detect_power_board(image_path)
    components = discriminate_components(image_path)

    if visual.get("possible_ram", False):
        features["ram"] = True
        features["memory_module"] = True
    if visual.get("gold_finger_edge", False):
        features["gold_fingers"] = True
    if motherboard.get("possible_motherboard", False):
        features["motherboard"] = True
    if power.get("possible_power_board", False):
        features["power_board"] = True

    visual_ic_signal = visual.get("possible_large_ic_chips", False)
    component_ic_support = components.get("ic_like", 0) >= 2 and components.get("dominant_family") != "power_components"
    features["large_ic_chips"] = bool(visual_ic_signal and component_ic_support)

    if components.get("dominant_family") == "power_components":
        features["power_board"] = True

    board_type = classify_board_type(features, visual, motherboard, power)
    score = calculate_score(features)
    grade_result = _grade_from_reference(score)
    reference_intelligence = build_reference_matches(features, visual, motherboard, power, board_type)
    reasoning_crosscheck = _agreement(board_type["type"], reference_intelligence.get("top_hypothesis"))
    spike_glass = spike_glass_recognize(features, visual, motherboard, power, components, reference_intelligence)

    if not photo_quality.get("usable", False):
        spike_glass["status"] = "retake_recommended"
        spike_glass["confidence"] = min(int(spike_glass.get("confidence", 0)), 45)
        spike_glass["photo_warning"] = "Recognition confidence capped because the photo quality gate recommends a retake."

    confidence = calculate_confidence(score, features=features, visual=visual, motherboard=motherboard, power=power)
    if reasoning_crosscheck["status"] == "review":
        confidence = max(25, confidence - 10)
    if visual_ic_signal and not component_ic_support:
        confidence = max(25, confidence - 5)
    if not photo_quality.get("usable", False):
        confidence = max(20, min(confidence, 50))

    result = {
        "grade": grade_result["grade"],
        "confidence": confidence,
        "score": score,
        "board_type": board_type["type"],
        "board_type_reason": board_type["reason"],
        "reasoning_crosscheck": reasoning_crosscheck,
        "photo_quality": photo_quality,
        "spike_glass": spike_glass,
        "pay_dirt_ready": grade_result["pay_dirt_ready"],
        "recommendation": grade_result["recommendation"],
        "recovery_signals": grade_result["recovery_signals"],
        "grade_notes": grade_result["grade_notes"],
        "reference_intelligence": reference_intelligence,
        "component_intelligence": components,
        "features": features,
        "visual": visual,
        "power": power,
        "signals": {
            "motherboard": features.get("motherboard", False),
            "ram": features.get("ram", False),
            "power_board": features.get("power_board", False),
            "gold_fingers": features.get("gold_fingers", False),
            "large_ic_chips": features.get("large_ic_chips", False),
            "dense_component_board": features.get("dense_component_board", False),
            "processor": features.get("processor", False),
            "component_count": features.get("component_count", 0),
            "component_density": features.get("component_density", 0.0),
            "possible_ram": visual.get("possible_ram", False),
            "gold_finger_edge": visual.get("gold_finger_edge", False),
            "raw_large_ic_signal": visual_ic_signal,
            "ic_signal_confirmed": component_ic_support,
            "possible_motherboard": motherboard.get("possible_motherboard", False),
            "large_board": motherboard.get("large_board", False),
            "possible_power_board": power.get("possible_power_board", False),
            "large_round_components": power.get("large_round_components", 0),
            "large_component_regions": power.get("large_component_regions", 0),
            "power_score": power.get("power_score", 0),
        },
        "model": "Board Sense v1.7 + Spike Glass v0.2 + Recovery Lab v0.1",
    }

    result["recovery_lab"] = build_recovery_plan(spike_glass, result)
    insight_engine = BoardInsight()
    result["insight"] = insight_engine.generate(result)
    return result
