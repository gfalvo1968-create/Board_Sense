"""SPIKE Lot Risk v0.1.

Turns a per-board condition loss into purchase exposure across a bulk lot. This
module deliberately reports ranges when the sample is incomplete instead of
pretending one inspected board represents an entire pallet.
"""


def lot_risk(quantity, intact_value_per_board, sampled_conditions=None):
    quantity = max(0, int(quantity or 0))
    intact = max(0.0, float(intact_value_per_board or 0))
    samples = sampled_conditions or []
    factors = []
    for sample in samples:
        try:
            factor = float(sample.get("remaining_value_factor", 1.0))
            factors.append(max(0.0, min(1.0, factor)))
        except (TypeError, ValueError, AttributeError):
            continue

    intact_lot_value = round(quantity * intact, 2)
    if not factors:
        return {
            "mode": "SPIKE Lot Risk v0.1",
            "quantity": quantity,
            "sample_size": 0,
            "intact_reference_lot_value": intact_lot_value,
            "status": "INSPECTION REQUIRED",
            "message": "No verified board-condition samples are available. Do not price the lot as intact by assumption.",
            "final_authority": "SPIKE",
        }

    avg_factor = sum(factors) / len(factors)
    worst_factor = min(factors)
    best_factor = max(factors)
    estimated_remaining = round(intact_lot_value * avg_factor, 2)
    estimated_loss = round(intact_lot_value - estimated_remaining, 2)
    conservative_remaining = round(intact_lot_value * worst_factor, 2)

    sample_ratio = (len(factors) / quantity) if quantity else 0
    if sample_ratio >= 0.20 or len(factors) >= 20:
        sample_confidence = "STRONG"
    elif len(factors) >= 5:
        sample_confidence = "MODERATE"
    else:
        sample_confidence = "WEAK"

    if estimated_loss >= 5000:
        warning = "CRITICAL EXPOSURE"
    elif estimated_loss >= 1000:
        warning = "MAJOR EXPOSURE"
    elif estimated_loss >= 200:
        warning = "CAUTION"
    else:
        warning = "LOW EXPOSURE"

    return {
        "mode": "SPIKE Lot Risk v0.1",
        "quantity": quantity,
        "sample_size": len(factors),
        "sample_confidence": sample_confidence,
        "average_remaining_value_factor": round(avg_factor, 3),
        "observed_factor_range": [round(worst_factor, 3), round(best_factor, 3)],
        "intact_reference_lot_value": intact_lot_value,
        "estimated_current_lot_value": estimated_remaining,
        "conservative_lot_value_using_worst_sample": conservative_remaining,
        "estimated_value_loss": estimated_loss,
        "warning": warning,
        "buying_rule": "Scale verified condition loss across quantity; increase sampling before committing large money.",
        "final_authority": "SPIKE",
    }
