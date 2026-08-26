"""Time-versus-value helper for Recovery Lab decisions."""


def compare_recovery_to_sale(sell_value=None, recovered_value=None, minutes=None):
    try:
        sell_value = float(sell_value) if sell_value is not None else None
        recovered_value = float(recovered_value) if recovered_value is not None else None
        minutes = float(minutes) if minutes is not None else None
    except (TypeError, ValueError):
        return {"status": "invalid_input"}

    if sell_value is None or recovered_value is None or not minutes or minutes <= 0:
        return {
            "status": "needs_values",
            "message": "Add whole-item sale value, expected recovered value, and labor minutes to compare options.",
        }

    extra_value = recovered_value - sell_value
    per_minute = extra_value / minutes
    per_hour = per_minute * 60

    if extra_value <= 0:
        decision = "SELL WHOLE"
    elif per_hour >= 60:
        decision = "RECOVERY LOOKS STRONG"
    elif per_hour >= 25:
        decision = "RECOVERY MAY BE WORTHWHILE"
    else:
        decision = "SELL WHOLE / REVIEW LABOR"

    return {
        "status": "ready",
        "sell_value": round(sell_value, 2),
        "recovered_value": round(recovered_value, 2),
        "extra_value": round(extra_value, 2),
        "minutes": round(minutes, 1),
        "extra_value_per_minute": round(per_minute, 2),
        "extra_value_per_hour": round(per_hour, 2),
        "decision": decision,
    }
