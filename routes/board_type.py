def classify_board_type(features, visual, motherboard, power):
    """Return a human-readable board type from combined detector evidence.

    Broad identity follows structural topology. Pure-PSU penalties must not erase
    a physically supported power stage when control/logic evidence is also present.
    Recovery material observations remain separate from equipment identity.
    """
    features=features or {};visual=visual or {};motherboard=motherboard or {};power=power or {}
    power_score=int(power.get("power_score",0) or 0);raw_power_score=max(power_score,int(power.get("raw_power_score",0) or 0));power_blocks=int(power.get("large_component_regions",0) or 0);power_round=int(power.get("large_round_components",0) or 0);power_packages=int(power.get("large_power_package_like",0) or 0)
    logic_evidence=bool(features.get("processor") or features.get("dense_component_board") or features.get("large_ic_chips"))
    stage_present=bool(power.get("power_stage_present") or power.get("mixed_power_control_candidate"))
    substantial_power_topology=bool(stage_present or (power_blocks>=1 and(raw_power_score>=3 or power_round>=2 or power_blocks>=2)) or (power_packages>=1 and power_round>=2 and raw_power_score>=3))
    if features.get("ram") or visual.get("possible_ram"):return {"type":"RAM / Memory Module","reason":"Long narrow geometry and memory-module signals detected."}
    if substantial_power_topology and logic_evidence:return {"type":"Power-Control / Controller Board","reason":"Physically supported power-stage hardware and control/logic evidence are both present; pure-PSU logic penalties do not erase the observed mixed topology."}
    if power.get("possible_power_board"):return {"type":"Power / Supply Board","reason":"Power-stage topology is dominant without enough confirmed control logic to classify the board as a mixed power controller."}
    if features.get("motherboard") or motherboard.get("possible_motherboard"):return {"type":"Motherboard / Main Logic Board","reason":"Large board geometry with logic-board characteristics detected."}
    if features.get("processor") and features.get("dense_component_board"):return {"type":"Processor-Rich Logic Board","reason":"Dense IC population with a dominant processor-like package detected."}
    if features.get("dense_component_board") or features.get("large_ic_chips"):return {"type":"Dense Logic / Controller Board","reason":"Multiple IC-like packages and elevated component density detected."}
    if features.get("gold_fingers") or visual.get("gold_finger_edge"):return {"type":"Edge-Connector Expansion Board","reason":"A board-edge connector signal is present and no stronger structural topology has been confirmed."}
    return {"type":"General PCB","reason":"No stronger board-type pattern has been confirmed yet."}
