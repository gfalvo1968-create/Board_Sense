"""SPIKE structural + condition decision guard v0.4.
Defining architecture outranks generic component counts. Hard motherboard authority
requires corroborated geometry, while dense processor-led main-logic boards may earn
a separate structural veto against weak false power-board promotion.
"""
def family(label):
    text=str(label or "").lower()
    if any(x in text for x in ("motherboard","main logic","logic board")):return "motherboard"
    if any(x in text for x in ("power","supply","psu")):return "power"
    if any(x in text for x in ("expansion","gold finger","edge-connector","edge card")):return "expansion"
    if any(x in text for x in ("ram","memory module")):return "ram"
    if any(x in text for x in ("server","enterprise")):return "server"
    return "unknown"
def motherboard_structure(result):
    ri=result.get("reference_intelligence") or {};signals=result.get("signals") or {};mb=result.get("motherboard") or {};score=0.0;anchors=[]
    for hyp in ri.get("hypotheses") or []:
        if family(hyp.get("type"))=="motherboard":score=max(score,float(hyp.get("evidence_score",0) or 0));anchors.extend(hyp.get("evidence") or [])
    confirmed_slot=bool(signals.get("confirmed_slot_bank") or mb.get("confirmed_slot_bank"));edge_bank=bool(mb.get("edge_connector_bank"));detector_score=float(signals.get("motherboard_score",mb.get("motherboard_score",mb.get("score",0))) or 0);possible=bool(signals.get("possible_motherboard") or signals.get("motherboard"))
    if confirmed_slot:anchors.append("confirmed parallel slot-bank geometry")
    if edge_bank:anchors.append("board-edge connector bank")
    if possible:anchors.append("motherboard detector candidate")
    geometry_confirmed=bool(confirmed_slot and edge_bank and detector_score>=9)
    if geometry_confirmed:score=max(score,9.0)
    return {"score":score,"anchors":list(dict.fromkeys(str(x) for x in anchors))[:8],"geometry_confirmed":geometry_confirmed,"confirmed_slot_bank":confirmed_slot,"edge_connector_bank":edge_bank,"detector_score":detector_score}
def strong_structural_family(result):
    mb=motherboard_structure(result);conf=float(result.get("confidence",0) or 0);fam=family(result.get("board_type"));signals=result.get("signals") or {};power=result.get("power") or {}
    if fam=="motherboard" and conf>=80 and mb["geometry_confirmed"]:
        return {"family":"motherboard","strength":"hard","confidence":conf,"structural_score":mb["score"],"anchors":mb["anchors"],"vetoes":["generic capacitor count cannot rename board as power supply","generic long contours cannot establish a PC motherboard without corroborated slot and edge geometry"]}
    processor=bool(signals.get("processor"));large_ic=bool(signals.get("large_ic_chips"));dense=bool(signals.get("dense_component_board"));logic_count=sum((processor,large_ic,dense));raw_power=max(int(signals.get("raw_power_score",0) or 0),int(signals.get("power_score",0) or 0),int(power.get("raw_power_score",0) or 0),int(power.get("power_score",0) or 0));power_blocks=max(int(signals.get("large_component_regions",0) or 0),int(power.get("large_component_regions",0) or 0));rounds=max(int(signals.get("large_round_components",0) or 0),int(power.get("large_round_components",0) or 0));packages=max(int(signals.get("large_power_package_like",0) or 0),int(power.get("large_power_package_like",0) or 0));strong_power=bool(raw_power>=5 and (power_blocks>=2 or rounds>=2 or packages>=2))
    if fam=="motherboard" and conf>=80 and logic_count>=2 and not strong_power:
        anchors=list(mb["anchors"])
        if processor:anchors.append("processor/controller package evidence")
        if large_ic:anchors.append("large logic IC population")
        if dense:anchors.append("dense logic-component population")
        return {"family":"main_logic","strength":"hard_logic","confidence":conf,"structural_score":max(mb["score"],float(logic_count+5)),"anchors":list(dict.fromkeys(anchors))[:8],"vetoes":["weak or generic power-component cues cannot rename a processor-led main logic board","mixed power-control identity requires corroborated strong power topology, not one ambiguous component cluster"]}
    return None
def condition_harvest_check(result,observations=None):
    observations=observations or {};fam=family(result.get("board_type"));items=[]
    def add(name,status,impact="unknown",note="",source="vision_or_case"):items.append({"feature":name,"status":status,"value_impact":impact,"note":note,"source":source})
    for name,value in observations.items():
        if isinstance(value,dict):add(name,value.get("status","unknown"),value.get("value_impact","unknown"),value.get("note",""),value.get("source","vision_or_case"))
        else:add(name,str(value),"unknown","")
    loss_states=("removed","cut","harvested","missing_confirmed","clearly_cut","clearly_harvested");uncertain_states=("not_visible","uncertain","unknown","expected_not_visible","probably_removed");present_states=("present","confirmed_present","visible","retained");confirmed_loss=[x for x in items if str(x["status"]).lower() in loss_states];uncertain=[x for x in items if str(x["status"]).lower() in uncertain_states];present=[x for x in items if str(x["status"]).lower() in present_states];severe=sum(1 for x in confirmed_loss if str(x["value_impact"]).lower() in ("high","major","severe"));moderate=sum(1 for x in confirmed_loss if str(x["value_impact"]).lower() in ("medium","moderate"));minor=max(0,len(confirmed_loss)-severe-moderate);factor=max(.20,1.0-severe*.25-moderate*.12-minor*.05)
    if severe>=3 or factor<=.40:condition="STRIPPED / SPENT"
    elif severe>=2 or factor<=.55:condition="HEAVILY HARVESTED"
    elif confirmed_loss:condition="PARTIALLY HARVESTED"
    elif uncertain:condition="INSPECTION NEEDED"
    else:condition="INTACT / NO CONFIRMED HARVESTING"
    signals=result.get("signals") or {};remaining_targets=[];target_map={"gold_fingers":"edge fingers / plated contacts","gold_finger_edge":"edge fingers / plated contacts","large_ic_chips":"large IC / logic packages","processor":"processor / high-value logic package","dense_component_board":"dense component population"}
    for key,label in target_map.items():
        if signals.get(key) and label not in remaining_targets:remaining_targets.append(label)
    for x in present:
        if x["feature"] not in remaining_targets:remaining_targets.append(x["feature"])
    if condition=="STRIPPED / SPENT" and not remaining_targets:opportunity="LOW / VERIFY RESIDUAL MATERIAL"
    elif confirmed_loss and remaining_targets:opportunity="REMAINING VALUE PRESENT AFTER HARVEST"
    elif remaining_targets:opportunity="VALUE-BEARING FEATURES STILL PRESENT"
    else:opportunity="INSPECTION REQUIRED"
    return {"mode":"Condition & Harvest Check v0.2","board_family":fam,"condition":condition,"confirmed_value_losses":confirmed_loss,"confirmed_present_features":present,"uncertain_or_not_visible":uncertain,"remaining_recovery_opportunity":opportunity,"remaining_recovery_targets":remaining_targets[:12],"remaining_value_factor":round(factor,2),"deduction_ready":bool(confirmed_loss),"buying_guidance":"Deduct only confirmed removed value, then price the useful material that remains. Harvested does not mean worthless." if confirmed_loss else "Do not reduce the offer for a feature that is merely outside the photo or uncertain.","pricing_rule":"price what is physically present; identity/reference evidence is advisory","verification_rule":"image color or apparent plating is an inspection cue, not a metal assay","final_authority":"SPIKE"}
def decision_trace(winner,hard=None,supporting=None,weak=None,contradictions=None,condition=None):
    hard=hard or [];supporting=supporting or [];weak=weak or [];contradictions=contradictions or [];reason=f"{winner} wins because defining structural anchors outweigh generic visual hints." if hard else f"{winner} is the best supported family from the available evidence.";trace={"final_authority":"SPIKE","winner":winner,"hard_evidence":hard,"supporting_evidence":supporting,"weak_hints":weak,"contradictions_or_vetoes":contradictions,"reason":reason,"web_evidence_policy":"advisory_only"}
    if condition is not None:trace["condition_and_harvest"]=condition
    return trace
