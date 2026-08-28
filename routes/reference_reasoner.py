"""Board Sense reference knowledge reasoner.

SPIKE reasoning v2 uses conservative evidence weighting. Broad board geometry,
color ratios, or a single gold-like signal can support a hypothesis but cannot
by themselves prove RAM, a motherboard, or full gold fingers.
"""

from routes.reference_loader import get_knowledge


def _compact_match(item, reason):
    return {"category":item.get("category","Unknown"),"grade":item.get("grade","UNKNOWN"),
            "value_rank":item.get("value_rank",0),"reason":reason,
            "material_signals":item.get("material_signals",[]),
            "sorting_advice":item.get("sorting_advice",""),"notes":item.get("notes","")}


def _add(hypotheses,name,points,reason):
    item=hypotheses.setdefault(name,{"score":0,"evidence":[],"against":[]})
    item["score"]+=points
    (item["evidence"] if points>=0 else item["against"]).append(reason)


def _normalize_hypotheses(hypotheses):
    ranked=[]
    for name,data in hypotheses.items():
        raw=data["score"]
        # Evidence strength, not probability. Keep ordinary hypotheses out of
        # the 90-100% range unless they have unusually specific support.
        confidence=max(20,min(94,int(round(38+raw*4.5))))
        ranked.append({"type":name,"evidence_score":raw,"hypothesis_confidence":confidence,
                       "evidence":data["evidence"],"against":data["against"]})
    ranked.sort(key=lambda x:x["evidence_score"],reverse=True)
    if len(ranked)>1:
        margin=ranked[0]["evidence_score"]-ranked[1]["evidence_score"]
        if margin<=2:
            ranked[0]["hypothesis_confidence"]=min(ranked[0]["hypothesis_confidence"],72)
        elif margin<=4:
            ranked[0]["hypothesis_confidence"]=min(ranked[0]["hypothesis_confidence"],80)
    return ranked


def build_reference_matches(features, visual, motherboard, power, board_type):
    knowledge=get_knowledge(); matches=[]; hypotheses={}
    raw_gold=bool(features.get("gold_fingers") or visual.get("gold_finger_edge"))
    finger_geometry=bool(visual.get("gold_finger_geometry") or features.get("gold_finger_geometry") or visual.get("repeated_edge_contacts"))
    # Only specific edge geometry earns a true gold-finger witness.
    gold=bool(raw_gold and finger_geometry)
    ram=bool(features.get("ram") or features.get("memory_module") or visual.get("possible_ram"))
    dense=bool(features.get("dense_component_board")); large_ics=bool(features.get("large_ic_chips") or visual.get("possible_large_ic_chips"))
    processor=bool(features.get("processor")); mobo=bool(features.get("motherboard") or motherboard.get("possible_motherboard"))
    large_board=bool(motherboard.get("large_board")); power_like=bool(features.get("power_board") or power.get("possible_power_board"))
    component_count=int(features.get("component_count",0) or 0); aspect_ratio=float(visual.get("aspect_ratio",0) or 0)
    large_round=int(power.get("large_round_components",0) or 0); large_regions=int(power.get("large_component_regions",0) or 0)

    if ram: _add(hypotheses,"RAM / Memory Module",4,"Memory-module geometry detector fired")
    if aspect_ratio>=2.8: _add(hypotheses,"RAM / Memory Module",2,f"Long narrow aspect ratio ({aspect_ratio:.2f}:1)")
    if gold:
        _add(hypotheses,"RAM / Memory Module",2,"Repeated edge-aligned finger geometry supports memory-card interpretation")
        _add(hypotheses,"Expansion / Gold Finger Card",6,"Repeated rectangular contacts aligned along a physical board edge")
    elif raw_gold:
        _add(hypotheses,"Expansion / Gold Finger Card",1,"Unconfirmed gold-colored edge signal; geometry not yet proven")

    if dense:
        _add(hypotheses,"Telecom / Network Board",2,"Dense IC population")
        _add(hypotheses,"Motherboard / Logic Board",1,"Dense logic population")
        _add(hypotheses,"Mixed Consumer Control Board",2,"Dense mixed control circuitry")
    if large_ics:
        _add(hypotheses,"Telecom / Network Board",1,"Multiple large IC-like packages")
        _add(hypotheses,"Motherboard / Logic Board",1,"Large IC packages support logic-board interpretation")
        _add(hypotheses,"Mixed Consumer Control Board",2,"Large IC packages support control/logic functionality")
    if processor:
        _add(hypotheses,"Motherboard / Logic Board",4,"Large central processor-like package")
        _add(hypotheses,"Processor-Rich Logic Board",5,"Dominant central processing package")
    if mobo:
        _add(hypotheses,"Motherboard / Logic Board",3,"Motherboard-scale size/proportion detector fired")
    if large_board:
        _add(hypotheses,"Motherboard / Logic Board",1,"Large board geometry")
        _add(hypotheses,"Server / Enterprise Board",1,"Large board size")
        _add(hypotheses,"Mixed Consumer Control Board",2,"Large populated control-board footprint")
    if dense and mobo and large_board and processor:
        _add(hypotheses,"Server / Enterprise Board",3,"Large dense logic board with processor evidence")
    if power_like:
        _add(hypotheses,"Power / Supply Board",6,"Power-board detector found strong power-handling characteristics")
        _add(hypotheses,"Mixed Consumer Control Board",4,"Power handling plus control circuitry supports a mixed consumer board")
        _add(hypotheses,"Telecom / Network Board",-3,"Power-heavy layout argues against premium telecom logic")
        _add(hypotheses,"Motherboard / Logic Board",-2,"Power-heavy layout weakens PC-motherboard interpretation")
    if large_round>=2: _add(hypotheses,"Power / Supply Board",2,f"{large_round} large round power components detected")
    if large_regions>=2: _add(hypotheses,"Power / Supply Board",2,f"{large_regions} large power-component regions detected")
    if component_count>=8:
        _add(hypotheses,"Mixed Consumer Control Board",3,f"High populated-component count ({component_count})")
        _add(hypotheses,"Telecom / Network Board",1,f"High chip-like component count ({component_count})")
    elif component_count<=2 and power_like:
        _add(hypotheses,"Power / Supply Board",2,"Low logic-chip count with power characteristics")

    if gold:
        gold_rules=knowledge.get("gold_fingers",[])
        target="High Quality Gold Finger Card" if dense else "Full Gold Fingers"
        for item in gold_rules:
            if item.get("category")==target:
                reason="Repeated rectangular gold-colored contacts confirmed along an outer board edge"
                if dense: reason+=" with dense component population"
                matches.append(_compact_match(item,reason)); break

    if large_ics or processor:
        for item in knowledge.get("ic_chips",[]):
            target="BGA Chip" if processor else "Plastic IC Chip"
            if item.get("category")==target:
                matches.append(_compact_match(item,"Processor-like package detected" if processor else "Multiple large dark rectangular IC-like packages detected")); break

    # Motherboard reference grading now needs processor/socket-style specificity,
    # not simply a large board silhouette.
    motherboard_specific=bool(mobo and (processor or (dense and component_count>=8 and not power_like)))
    if motherboard_specific:
        target="High Grade Motherboard" if dense and gold else "Medium Grade Motherboard"
        for item in knowledge.get("motherboards",[]):
            if item.get("category")==target:
                reason="Motherboard-scale geometry plus specific logic evidence detected"
                if processor: reason+=" with processor-like package"
                if gold: reason+=" and confirmed edge fingers"
                matches.append(_compact_match(item,reason)); break

    telecom_like=bool(gold and dense and large_ics and not power_like)
    if telecom_like:
        for item in knowledge.get("Telecom_boards",[]):
            if item.get("category")=="High Grade Telecom Board":
                matches.append(_compact_match(item,"Dense IC layout plus confirmed edge-finger geometry resembles high-grade telecom architecture")); break

    ranked=_normalize_hypotheses(hypotheses)
    top=ranked[0] if ranked else None; runner=ranked[1] if len(ranked)>1 else None
    margin=(top["evidence_score"]-runner["evidence_score"]) if top and runner else (top["evidence_score"] if top else 0)
    return {"matches":matches,"match_count":len(matches),"hypotheses":ranked[:5],"top_hypothesis":top,
            "hypothesis_margin":margin,"telecom_pattern":telecom_like,
            "board_type_context":board_type.get("type","General PCB"),
            "gold_finger_geometry_confirmed":gold,
            "reasoning_version":"SPIKE-weighted-evidence-v2"}
