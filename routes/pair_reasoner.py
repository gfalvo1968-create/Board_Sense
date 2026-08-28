from copy import deepcopy


def _family(label):
    text = str(label or "").lower()
    groups = [
        ("power", ("power", "supply", "psu")),
        ("motherboard", ("motherboard", "main logic", "logic board")),
        ("ram", ("ram", "memory module")),
        ("expansion", ("expansion", "gold finger card", "edge card", "edge-connector")),
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


def _solder_side_likelihood(result):
    spike = result.get("spike_glass") or {}
    summary = spike.get("evidence_summary") or {}
    likelihood = float(summary.get("solder_side_likelihood", 0) or 0)
    label = str((spike.get("top_match") or {}).get("label", "")).lower()
    if "solder" in label and "trace" in label:
        likelihood = max(likelihood, 70.0)
    return likelihood


def _motherboard_structure(result):
    ri = result.get("reference_intelligence") or {}
    best = 0.0
    for hypothesis in ri.get("hypotheses") or []:
        if _family(hypothesis.get("type")) == "motherboard":
            best = max(best, float(hypothesis.get("evidence_score", 0) or 0))
    signals = result.get("signals") or {}
    if signals.get("possible_motherboard") or signals.get("motherboard"):
        best = max(best, 6.0)
    return best


def _side_scores(result):
    scores = {k: 0.0 for k in ("power", "motherboard", "ram", "expansion", "server", "telecom", "processor")}
    confidence = max(0.0, min(100.0, float(result.get("confidence", 0) or 0)))
    primary = _family(result.get("board_type"))
    if primary in scores:
        scores[primary] += 4.0 + confidence / 20.0

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
    """Treat two photos as evidence from one physical board, including face role."""
    a_scores = _side_scores(side_a)
    b_scores = _side_scores(side_b)
    totals = {key: a_scores[key] + b_scores[key] for key in a_scores}

    fam_a = _family(side_a.get("board_type"))
    fam_b = _family(side_b.get("board_type"))
    conf_a = float(side_a.get("confidence", 0) or 0)
    conf_b = float(side_b.get("confidence", 0) or 0)
    solder_a = _solder_side_likelihood(side_a)
    solder_b = _solder_side_likelihood(side_b)
    mb_a = _motherboard_structure(side_a)
    mb_b = _motherboard_structure(side_b)

    # A clearly identified solder/trace face is supporting evidence, not a new
    # opportunity to rename the physical board from vias/contact geometry.
    inherited_family = None
    component_side = None
    solder_side = None
    if solder_b >= 65 and solder_a < 65 and fam_a != "unknown" and conf_a >= 80:
        if conf_b <= 70 or fam_b != fam_a:
            inherited_family, component_side, solder_side = fam_a, "A", "B"
    elif solder_a >= 65 and solder_b < 65 and fam_b != "unknown" and conf_b >= 80:
        if conf_a <= 70 or fam_a != fam_b:
            inherited_family, component_side, solder_side = fam_b, "B", "A"

    # Strong motherboard architecture gets an additional safeguard. A reverse
    # face full of slot footprints and plated through-holes must not become an
    # expansion card merely because the components themselves are hidden.
    if solder_b >= 65 and fam_a == "motherboard" and conf_a >= 80 and mb_a >= 6:
        inherited_family, component_side, solder_side = "motherboard", "A", "B"
    elif solder_a >= 65 and fam_b == "motherboard" and conf_b >= 80 and mb_b >= 6:
        inherited_family, component_side, solder_side = "motherboard", "B", "A"

    if inherited_family:
        totals[inherited_family] += 8.0
        # The solder face still contributes evidence, but weak competing family
        # labels are demoted because face role explains the apparent conflict.
        for family in totals:
            if family != inherited_family:
                totals[family] = max(0.0, totals[family] - 2.5)

    strong_power = max(a_scores["power"], b_scores["power"]) >= 10.0
    if strong_power and inherited_family != "motherboard":
        totals["power"] += 4.0
        totals["motherboard"] = max(0.0, totals["motherboard"] - 3.0)
        totals["server"] = max(0.0, totals["server"] - 2.0)

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    winner, win_score = ranked[0]
    runner, runner_score = ranked[1]
    margin = win_score - runner_score

    direct_agreement = fam_a == fam_b and fam_a != "unknown"
    face_role_agreement = inherited_family is not None and winner == inherited_family
    base_conf = (conf_a + conf_b) / 2.0

    if direct_agreement:
        pair_conf = min(98, round(base_conf + 4))
        agreement_text = "Both sides independently point to the same board family."
    elif face_role_agreement:
        strong_conf = conf_a if component_side == "A" else conf_b
        pair_conf = min(96, max(82, round(strong_conf + min(4.0, margin * 0.35))))
        agreement_text = (
            f"Side {solder_side} is a solder/trace face of the same physical board. "
            f"Family identity is preserved from strong Side {component_side} structural evidence while the reverse face supplies supporting evidence."
        )
    else:
        margin_bonus = min(12.0, margin * 1.5)
        pair_conf = max(45, min(94, round(58 + margin_bonus)))
        agreement_text = "The two sides initially disagreed, so Board Sense reconciled them as one physical board using evidence from both faces."

    combined_score = round((float(side_a.get("score", 0) or 0) + float(side_b.get("score", 0) or 0)) / 2.0)
    if face_role_agreement:
        component_result = side_a if component_side == "A" else side_b
        component_score = float(component_result.get("score", 0) or 0)
        # Do not let a low-information solder face halve a valid component-side
        # recovery grade. Preserve the stronger score conservatively.
        combined_score = max(combined_score, round(component_score * 0.85))
    if strong_power and winner == "power":
        combined_score = min(combined_score, 15)

    support_a = a_scores.get(winner, 0)
    support_b = b_scores.get(winner, 0)
    if face_role_agreement:
        representative = side_a if component_side == "A" else side_b
    else:
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
        "face_role_agreement": face_role_agreement,
        "component_side": component_side,
        "solder_trace_side": solder_side,
        "side_a_solder_likelihood": round(solder_a, 1),
        "side_b_solder_likelihood": round(solder_b, 1),
        "side_a_family": fam_a,
        "side_b_family_raw": fam_b,
        "side_b_family": inherited_family if solder_side == "B" and face_role_agreement else fam_b,
        "side_a_support": {k: round(v, 2) for k, v in a_scores.items() if v > 0},
        "side_b_support": {k: round(v, 2) for k, v in b_scores.items() if v > 0},
        "message": agreement_text,
    }
    paired["reasoning_crosscheck"] = {
        "status": "paired_agree" if (direct_agreement or face_role_agreement) else "paired_reconciled",
        "simple_classifier": paired["board_type"],
        "weighted_hypothesis": _display_name(winner),
        "weighted_confidence": pair_conf,
        "message": agreement_text,
    }
    paired["model"] = "Board Sense v2.1 + Two-Sided Pair Reasoner v1.1"

    ri = deepcopy(paired.get("reference_intelligence") or {})
    matches = ri.get("matches") or []
    filtered_matches = [m for m in matches if _family(m.get("category")) in (winner, "unknown")]
    if filtered_matches:
        ri["matches"] = filtered_matches
    hypotheses = ri.get("hypotheses") or []
    ri["hypotheses"] = sorted(hypotheses, key=lambda h: (_family(h.get("type")) != winner, -float(h.get("evidence_score", 0) or 0)))
    paired["reference_intelligence"] = ri

    return paired
