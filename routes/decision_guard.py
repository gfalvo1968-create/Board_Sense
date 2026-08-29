"""SPIKE structural decision guard.

Defining architecture outranks generic component counts. This helper is kept
small so both single-image and paired reasoning can use the same rules.
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


def decision_trace(winner, hard=None, supporting=None, weak=None, contradictions=None):
    hard = hard or []
    supporting = supporting or []
    weak = weak or []
    contradictions = contradictions or []
    if hard:
        reason = f"{winner} wins because defining structural anchors outweigh generic visual hints."
    else:
        reason = f"{winner} is the best supported family from the available evidence."
    return {
        "final_authority": "SPIKE",
        "winner": winner,
        "hard_evidence": hard,
        "supporting_evidence": supporting,
        "weak_hints": weak,
        "contradictions_or_vetoes": contradictions,
        "reason": reason,
        "web_evidence_policy": "advisory_only",
    }
