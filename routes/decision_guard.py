"""SPIKE structural + condition decision guard.

Defining architecture outranks generic component counts. Condition evidence is
kept separate from identity so SPIKE can recognize what a board started as while
pricing only the recoverable material that is still physically present.
"""


def family(label):
    text = str(label or "").lower()
    if any(x in text for x in ("motherboard", "main logic", "logic board")): return "motherboard"
    if any(x in text for x in ("power", "supply", "psu")): return "power"
    if any(x in text for x in ("expansion", "gold finger", "edge-connector", "edge card")): return "expansion"
    if any(x in text for x in ("ram", "memory module")): return "ram"
    if any(x in text for x in ("server", "enterprise")): return "server"
    return "unknown"


def motherboard_structure(result):
    ri = result.get("reference_intelligence") or {}
    score = 0.0
    anchors = []
    for hyp in ri.get("hypotheses") or []:
        if family(hyp.get("type")) == "motherboard":
            score = max(score, float(hyp.get("evidence_score", 0) or 0))
            anchors.extend(hyp.get("evidence") or [])
    signals = result.get("signals") or {}
    if signals.get("possible_motherboard") or signals.get("motherboard"):
        score = max(score, 6.0)
        anchors.append("motherboard structural detector")
    return {"score": score, "anchors": list(dict.fromkeys(str(x) for x in anchors))[:8]}


def strong_structural_family(result):
    mb = motherboard_structure(result)
    conf = float(result.get("confidence", 0) or 0)
    fam = family(result.get("board_type"))
    if fam == "motherboard" and conf >= 80 and mb["score"] >= 6:
        return {
            "family": "motherboard",
            "strength": "hard",
            "confidence": conf,
            "structural_score": mb["score"],
            "anchors": mb["anchors"],
            "vetoes": ["generic capacitor count cannot rename board as power supply"],
        }
    return None


def condition_harvest_check(result, observations=None):
    """Build a conservative buying-condition packet.

    Observations may later come from vision, blueprint, a web/reference match, or
    user-confirmed inspection. Missing value is never assumed from an unseen
    camera angle. Only explicit removed/cut evidence reduces the value factor.
    """
    observations = observations or {}
    fam = family(result.get("board_type"))
    items = []

    def add(name, status, impact="unknown", note=""):
        items.append({"feature": name, "status": status, "value_impact": impact, "note": note})

    for name, value in observations.items():
        if isinstance(value, dict):
            add(name, value.get("status", "unknown"), value.get("value_impact", "unknown"), value.get("note", ""))
        else:
            add(name, str(value), "unknown", "")

    confirmed_loss = [x for x in items if str(x["status"]).lower() in ("removed", "cut", "harvested", "missing_confirmed")]
    uncertain = [x for x in items if str(x["status"]).lower() in ("not_visible", "uncertain", "unknown", "expected_not_visible")]

    severe = sum(1 for x in confirmed_loss if str(x["value_impact"]).lower() in ("high", "major", "severe"))
    moderate = sum(1 for x in confirmed_loss if str(x["value_impact"]).lower() in ("medium", "moderate"))
    minor = max(0, len(confirmed_loss) - severe - moderate)

    factor = max(0.20, 1.0 - severe * 0.25 - moderate * 0.12 - minor * 0.05)
    if severe >= 2 or factor <= 0.55:
        condition = "HEAVILY HARVESTED"
    elif confirmed_loss:
        condition = "HARVESTED / MODIFIED"
    elif uncertain:
        condition = "INSPECTION NEEDED"
    else:
        condition = "NO CONFIRMED HARVESTING"

    return {
        "mode": "Condition & Harvest Check v0.1",
        "board_family": fam,
        "condition": condition,
        "confirmed_value_losses": confirmed_loss,
        "uncertain_or_not_visible": uncertain,
        "remaining_value_factor": round(factor, 2),
        "buying_guidance": (
            "Reduce the offer from intact-board value when confirmed valuable features were removed."
            if confirmed_loss else
            "Do not reduce the offer for a feature that is merely outside the photo or uncertain."
        ),
        "pricing_rule": "price what is physically present; web/reference identity is advisory",
        "final_authority": "SPIKE",
    }


def decision_trace(winner, hard=None, supporting=None, weak=None, contradictions=None, condition=None):
    hard = hard or []
    supporting = supporting or []
    weak = weak or []
    contradictions = contradictions or []
    if hard:
        reason = f"{winner} wins because defining structural anchors outweigh generic visual hints."
    else:
        reason = f"{winner} is the best supported family from the available evidence."
    trace = {
        "final_authority": "SPIKE",
        "winner": winner,
        "hard_evidence": hard,
        "supporting_evidence": supporting,
        "weak_hints": weak,
        "contradictions_or_vetoes": contradictions,
        "reason": reason,
        "web_evidence_policy": "advisory_only",
    }
    if condition is not None:
        trace["condition_and_harvest"] = condition
    return trace
