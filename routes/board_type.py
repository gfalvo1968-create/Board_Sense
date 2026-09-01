def classify_board_type(features, visual, motherboard, power):
    """Return a human-readable board type from combined detector evidence.

    Broad identity follows structural topology. A weak gold-coloured edge signal
    must not outrank substantial power hardware plus control/logic evidence.
    Recovery material observations remain separate from equipment identity.
    """
    features = features or {}
    visual = visual or {}
    motherboard = motherboard or {}
    power = power or {}

    power_score = int(power.get("power_score", 0) or 0)
    power_blocks = int(power.get("large_component_regions", 0) or 0)
    power_round = int(power.get("large_round_components", 0) or 0)
    logic_evidence = bool(
        features.get("processor")
        or features.get("dense_component_board")
        or features.get("large_ic_chips")
    )
    substantial_power_topology = bool(
        power_blocks >= 1
        and (power_score >= 3 or power_round >= 2 or power_blocks >= 2)
    )

    if features.get("ram") or visual.get("possible_ram"):
        return {
            "type": "RAM / Memory Module",
            "reason": "Long narrow geometry and memory-module signals detected.",
        }

    # Mixed power + logic is a controller family, not a pure PSU and not an
    # expansion card merely because a bright/plated-looking edge was observed.
    if substantial_power_topology and logic_evidence:
        return {
            "type": "Power-Control / Controller Board",
            "reason": "Substantial power-stage hardware and control/logic evidence are both present; this mixed topology outranks a weak edge-connector signal.",
        }

    if power.get("possible_power_board"):
        return {
            "type": "Power / Supply Board",
            "reason": "Power-stage topology is dominant without enough confirmed control logic to classify the board as a mixed power controller.",
        }

    if features.get("motherboard") or motherboard.get("possible_motherboard"):
        return {
            "type": "Motherboard / Main Logic Board",
            "reason": "Large board geometry with logic-board characteristics detected.",
        }

    if features.get("processor") and features.get("dense_component_board"):
        return {
            "type": "Processor-Rich Logic Board",
            "reason": "Dense IC population with a dominant processor-like package detected.",
        }

    if features.get("dense_component_board") or features.get("large_ic_chips"):
        return {
            "type": "Dense Logic / Controller Board",
            "reason": "Multiple IC-like packages and elevated component density detected.",
        }

    if features.get("gold_fingers") or visual.get("gold_finger_edge"):
        return {
            "type": "Edge-Connector Expansion Board",
            "reason": "A board-edge connector signal is present and no stronger structural topology has been confirmed.",
        }

    return {
        "type": "General PCB",
        "reason": "No stronger board-type pattern has been confirmed yet.",
    }
