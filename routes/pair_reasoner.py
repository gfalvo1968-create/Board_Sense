from copy import deepcopy


def _family(label):
    text = str(label or "").lower()
    groups = [
        ("power", ("power", "supply", "psu")),
        ("motherboard", ("motherboard", "main logic", "logic board")),
        ("ram", ("ram", "memory module")),
        ("expansion", ("expansion", "gold finger card", "edge card")),
        ("server", ("server", "enterprise")),
        ("telecom", ("telecom", "network")),
        ("processor", ("processor", "cpu")),
    ]
    for key, words in groups:
        if any(word in text for word in words):
            return key
    return "unknown"


def _display_name(family):
    return {
        "power": "Power / Supply Board",
        "motherboard": "Motherboard / Main Logic Board",
        "ram": "RAM / Memory Module",
        "expansion": "Expansion / Gold Finger Card",
        "server": "Server / Enterprise Board",
        "telecom": "Telecom / Network Board",
        "processor": "Processor / CPU Board",
    }.get(family, "Unknown Board")


def _side_scores(result):
    scores = {k: 0.0 for k in ("power", "motherboard", "ram", "expansion", "server", "telecom", "processor")}
    confidence = max(0.0, min(100.0, float(result.get("confidence", 0) or 0)))
    primary = _family(result.get("board_type"))
    if primary in scores:
        scores[primary] += 4.0 + confidence / 20.0

    # Weighted Jury evidence helps, but cannot overpower hard physical evidence.
    ri = result.get("reference_intelligence") or {}
    for hypothesis in (ri.get("hypotheses") or [])[:5]:
        fam = _family(hypothesis.get("type"))
        if fam in scores:
            scores[fam] += min(4.0, float(hypothesis.get("evidence_score", 0) or 0) * 0.35)

    sig = result.get("signals") or {}
    features = result.get("features") or {}
    power = result.get("power") or {}

    power_score = float(sig.get("power_score", power.get("power_score", 0)) or 0)
    round_parts = float(sig.get("large_round_components", power.get("large_round_components", 0)) or 0)
    if sig.get("possible_power_board") or sig.get("power_board") or features.get("power_board"):
        scores["power"] += 5.0
    scores["power"] += min(6.0, power_score * 0.9)
    scores["power"] += min(3.0, round_parts * 0.55)

    if sig.get("possible_motherboard") or sig.get("motherboard") or features.get("motherboard"):
        scores["motherboard"] += 3.0
    if sig.get("ic_signal_confirmed") or sig.get("large_ic_chips") or features.get("large_ic_chips"):
        scores["motherboard"] += 2.5
    if sig.get("dense_component_board") or features.get("dense_component_board"):
        scores["motherboard"] += 1.5

    if sig.get("possible_ram") or sig.get("ram") or features.get("ram"):
        scores["ram"] += 5.0
    if sig.get("gold_finger_edge") or sig.get("gold_fingers") or features.get("gold_fingers"):
        scores["expansion"] += 3.5
        scores["ram"] += 1.5

    return scores


def _grade(score):
    if score >= 22:
        return "VERY HIGH"
    if score >= 16:
        return "HIGH"
    if score >= 9:
        return "MEDIUM"
    return "LOW"


def reconcile_pair(side_a, side_b):
    """Treat two photos as evidence from one physical board, not two independent boards."""
    a_scores = _side_scores(side_a)
    b_scores = _side_scores(side_b)
    totals = {key: a_scores[key] + b_scores[key] for key in a_scores}

    # A strong component-side power signature should not be erased by generic
    # motherboard-like geometry on the reverse side of the same PCB.
    strong_power = max(a_scores["power"], b_scores["power"]) >= 10.0
    if strong_power:
        totals["power"] += 4.0
        totals["motherboard"] = max(0.0, totals["motherboard"] - 3.0)
        totals["server"] = max(0.0, totals["server"] - 2.0)

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    winner, win_score = ranked[0]
    runner, runner_score = ranked[1]
    margin = win_score - runner_score

    fam_a = _family(side_a.get("board_type"))
    fam_b = _family(side_b.get("board_type"))
    direct_agreement = fam_a == fam_b and fam_a != "unknown"

    base_conf = (float(side_a.get("confidence", 0) or 0) + float(side_b.get("confidence", 0) or 0)) / 2.0
    if direct_agreement:
        pair_conf = min(98, round(base_conf + 4))
        agreement_text = "Both sides independently point to the same board family."
    else:
        # Disagreement is resolved from shared physical evidence, not by simply
        # choosing whichever side reported the larger confidence number.
        margin_bonus = min(12.0, margin * 1.5)
        pair_conf = max(45, min(94, round(58 + margin_bonus)))
        agreement_text = "The two sides initially disagreed, so Board Sense reconciled them as one physical board using evidence from both faces."

    combined_score = round((float(side_a.get("score", 0) or 0) + float(side_b.get("score", 0) or 0)) / 2.0)
    if strong_power and winner == "power":
        combined_score = min(combined_score, 15)

    # Use the side whose own evidence best supports the paired winner as the
    # base for rich detail cards, then override the final verdict.
    support_a = a_scores.get(winner, 0)
    support_b = b_scores.get(winner, 0)
    representative = side_a if support_a >= support_b else side_b
    paired = deepcopy(representative)
    paired["board_type"] = _display_name(winner)
    paired["board_type_reason"] = agreement_text
    paired["confidence"] = pair_conf
    paired["score"] = combined_score
    paired["grade"] = _grade(combined_score)
    paired["pay_dirt_ready"] = combined_score >= 16
    paired["paired_analysis"] = {
        "mode": "same_physical_board",
        "winner_family": winner,
        "runner_up_family": runner,
        "winner_score": round(win_score, 2),
        "runner_up_score": round(runner_score, 2),
        "evidence_margin": round(margin, 2),
        "direct_side_agreement": direct_agreement,
        "side_a_family": fam_a,
        "side_b_family": fam_b,
        "side_a_support": {k: round(v, 2) for k, v in a_scores.items() if v > 0},
        "side_b_support": {k: round(v, 2) for k, v in b_scores.items() if v > 0},
        "message": agreement_text,
    }
    paired["reasoning_crosscheck"] = {
        "status": "paired_agree" if direct_agreement else "paired_reconciled",
        "simple_classifier": paired["board_type"],
        "weighted_hypothesis": _display_name(winner),
        "weighted_confidence": pair_conf,
        "message": agreement_text,
    }
    paired["model"] = "Board Sense v2.0 + Two-Sided Pair Reasoner v1.0"

    # Filter reference cards to the winning family when possible so the final
    # screen does not announce mutually exclusive board identities.
    ri = deepcopy(paired.get("reference_intelligence") or {})
    matches = ri.get("matches") or []
    filtered_matches = [m for m in matches if _family(m.get("category")) in (winner, "unknown")]
    if filtered_matches:
        ri["matches"] = filtered_matches
    hypotheses = ri.get("hypotheses") or []
    ri["hypotheses"] = sorted(hypotheses, key=lambda h: (_family(h.get("type")) != winner, -float(h.get("evidence_score", 0) or 0)))
    paired["reference_intelligence"] = ri

    return paired
