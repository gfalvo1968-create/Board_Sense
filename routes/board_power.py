import cv2
from routes.component_discriminator import discriminate_components

def detect_power_board(image_path):
    """Estimate power-stage topology separately from pure-PSU classification.

    A controller board can contain a substantial transformer/relay/power-device
    stage while also carrying many ICs. Logic evidence should stop a *pure PSU*
    call, but it must not erase physically corroborated power-stage evidence.
    """
    signals={"possible_power_board":False,"power_stage_present":False,"mixed_power_control_candidate":False,"large_round_components":0,"large_component_regions":0,"large_power_package_like":0,"magnetic_winding_like":0,"sparse_component_layout":False,"power_score":0,"raw_power_score":0,"logic_penalty":0,"solder_side_suppressed":False}
    try:
        image=cv2.imread(image_path)
        if image is None:return signals
        components=discriminate_components(image_path);round_count=int(components.get("capacitor_like",0));block_count=int(components.get("transformer_relay_like",0));package_count=int(components.get("large_power_package_like",0));winding_count=int(components.get("magnetic_winding_like",0));ic_count=int(components.get("ic_like",0));solder_side=int(components.get("solder_side_likelihood",0));logic_ratio=float(components.get("logic_component_ratio",0.0));power_ratio=float(components.get("power_component_ratio",0.0));effective_round=round_count;effective_block=block_count;effective_package=package_count;effective_winding=winding_count
        if solder_side>=65:effective_round=0;effective_block=0;effective_package=0;effective_winding=0;signals["solder_side_suppressed"]=True
        signals["large_round_components"]=effective_round;signals["large_component_regions"]=effective_block;signals["large_power_package_like"]=effective_package;signals["magnetic_winding_like"]=effective_winding;signals["sparse_component_layout"]=(effective_block>=1 and(effective_block>=2 or effective_round>=3) and ic_count<=6 and solder_side<65)
        raw=0
        if effective_round>=2:raw+=1
        if effective_round>=4:raw+=1
        if effective_round>=6:raw+=1
        if effective_block>=1:raw+=3
        if effective_block>=2:raw+=2
        if effective_package>=1 and(effective_round>=2 or effective_block>=1 or effective_winding>=1):raw+=2
        # A visible copper-wound magnetic component is strong topology evidence
        # only when another power-family feature independently corroborates it.
        if effective_winding>=1 and(effective_round>=2 or effective_block>=1 or effective_package>=1):raw+=3
        if effective_winding>=2 and effective_round>=2:raw+=1
        if power_ratio>=.55 and solder_side<65:raw+=1
        if signals["sparse_component_layout"]:raw+=2
        penalty=0
        if ic_count>=4 or logic_ratio>=.40:penalty+=2
        if ic_count>=8 or logic_ratio>=.55:penalty+=2
        if solder_side>=65:raw=0;penalty=0
        score=max(0,raw-penalty);signals["raw_power_score"]=raw;signals["logic_penalty"]=penalty;signals["power_score"]=score
        corroborated_stage=bool(
            (effective_block>=1 and raw>=3)
            or(effective_package>=1 and effective_round>=2 and raw>=3)
            or(effective_winding>=1 and effective_round>=2 and raw>=4)
            or(effective_winding>=1 and effective_package>=1 and raw>=4)
        )
        signals["power_stage_present"]=bool(corroborated_stage and solder_side<65)
        signals["mixed_power_control_candidate"]=bool(signals["power_stage_present"] and(ic_count>=3 or logic_ratio>=.30))
        signals["possible_power_board"]=bool(score>=6 and effective_block>=1 and(effective_round>=2 or effective_block>=2) and solder_side<65)
    except Exception as exc:print(f"[Power Board Detector Error] {exc}")
    return signals
