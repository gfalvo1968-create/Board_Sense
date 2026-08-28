"""SPIKE Glass visual recognition layer for Board Sense.

v0.5 adds solder-side context and requires deliberate plated-contact patterns.
It keeps confidence evidence-weighted and contradiction-aware.
"""


def _candidate(label, family, score, evidence, action="", caution=""):
    return {"label":label,"family":family,"score":max(0,min(95,int(score))),
            "evidence":evidence,"action":action,"caution":caution}


def recognize(features, visual, motherboard, power, components, reference_intelligence):
    candidates=[]
    ic_count=int(components.get("ic_like",0)); cap_count=int(components.get("capacitor_like",0))
    contact_count=int(components.get("contact_pad_like",0)); block_count=int(components.get("transformer_relay_like",0))
    solder_count=int(components.get("solder_joint_like",0)); solder_side=int(components.get("solder_side_likelihood",0))
    contact_pattern=float(components.get("contact_pattern_score",0.0))
    dominant=components.get("dominant_family","unknown")
    logic_ratio=float(components.get("logic_component_ratio",0.0)); power_ratio=float(components.get("power_component_ratio",0.0))

    if solder_side>=65:
        candidates.append(_candidate(
            "PCB Solder / Trace Side","board_feature",72+min(16,(solder_side-65)//2),
            [f"{solder_count} metallic solder/via candidates",f"solder-side structural likelihood {solder_side}%"],
            "Treat bright circular joints as solder/vias unless a deliberate plated-contact geometry is separately proven.",
            "This identifies board side/context, not the final board family."
        ))

    if features.get("ram") or visual.get("possible_ram"):
        evidence=[]; score=54
        if visual.get("possible_ram"): evidence.append("long narrow memory-module-like geometry"); score+=8
        if features.get("gold_fingers") or visual.get("gold_finger_edge"): evidence.append("edge-contact signal"); score+=8
        if ic_count>=4: evidence.append(f"{ic_count} IC-like packages"); score+=8
        if block_count>=2 or dominant=="power_components": score-=14; evidence.append("power-component evidence conflicts with RAM")
        candidates.append(_candidate("RAM / Memory Module","board",score,evidence,
            "Confirm DIMM/SODIMM geometry and repeated edge fingers before grading as memory.",
            "Long shape or gold color alone is insufficient."))

    if power.get("possible_power_board") or dominant=="power_components" or (cap_count+block_count)>=3:
        evidence=[]; score=48
        if power.get("possible_power_board"): score+=min(14,int(power.get("power_score",0))*2); evidence.append("independent power-board detector support")
        if cap_count: score+=min(12,cap_count*2); evidence.append(f"{cap_count} filtered capacitor-like components")
        if block_count: score+=min(18,block_count*6); evidence.append(f"{block_count} transformer/relay/power-block-like regions")
        if power_ratio>logic_ratio+.15: score+=8; evidence.append("power evidence exceeds logic evidence")
        if ic_count>=4 and logic_ratio>=power_ratio: score-=12; evidence.append("logic IC population conflicts with a pure power-board interpretation")
        candidates.append(_candidate("Power / Supply Board","board",score,evidence,
            "Favor copper, transformer and aluminum recovery; stay conservative on precious metals.",
            "A power-board call needs actual power parts."))

    if motherboard.get("possible_motherboard"):
        evidence=["motherboard-scale layout detector fired"]; score=56
        if motherboard.get("large_board"): evidence.append("large board footprint"); score+=6
        if features.get("processor"): evidence.append("processor-rich region"); score+=10
        if ic_count>=4: evidence.append(f"{ic_count} IC-like packages"); score+=min(8,ic_count)
        if dominant=="power_components" and power_ratio>logic_ratio: score-=12; evidence.append("power dominance conflicts with main-logic-board interpretation")
        candidates.append(_candidate("Motherboard / Main Logic Board","board",score,evidence,
            "Inspect sockets, processors, buses and removable memory before assigning motherboard grade."))

    # A loose gold-color signal may be surfaced cautiously, but it should not
    # become a high-confidence gold-finger result without stronger geometry from
    # upstream detectors/reference reasoning.
    gold_signal=bool(features.get("gold_fingers") or visual.get("gold_finger_edge"))
    if gold_signal:
        candidates.append(_candidate("Possible Edge Contact Area","component",58,
            ["gold-colored edge signal reported upstream"],
            "Confirm repeated rectangular contacts aligned along a physical board edge before calling gold fingers.",
            "Gold color, solder, copper traces and reflections can imitate a finger signal."))

    # Keypad/plated contact boards need a deliberate pattern and must lose to a
    # strong solder-side interpretation.
    if contact_count>=4 and contact_pattern>=0.60 and solder_side<65:
        score=58+min(16,contact_count)+int(contact_pattern*10)
        evidence=[f"{contact_count} plated/contact-pad candidates",f"deliberate pattern score {contact_pattern:.2f}"]
        candidates.append(_candidate("Keypad / Plated Contact Board","board_feature",score,evidence,
            "Inspect contact finish and surrounding electronics before grading.",
            "Contact color does not prove gold plating thickness."))

    if ic_count>=1:
        score=56+min(18,ic_count*3); evidence=[f"{ic_count} rectangular IC-like package candidates"]
        if dominant=="logic_ic": score+=7; evidence.append("logic ICs dominate major components")
        if power_ratio>logic_ratio+.25: score-=8; evidence.append("strong power evidence lowers logic-dominant confidence")
        candidates.append(_candidate("IC / Logic Package","component",score,evidence,
            "Use package style, markings and board context before estimating recovery value."))

    if cap_count>=1:
        score=52+min(18,cap_count*3); evidence=[f"{cap_count} filtered cylindrical/round component candidates"]
        if block_count: score+=min(8,block_count*2); evidence.append("power-component context also present")
        candidates.append(_candidate("Capacitor / Power Component Cluster","component",score,evidence,
            "Confirm component family before sorting.","Round pads and solder joints must not be counted as capacitors."))

    if block_count>=1:
        candidates.append(_candidate("Transformer / Relay / Power Block","component",60+min(20,block_count*5),
            [f"{block_count} large block-like power regions"],
            "Inspect for copper windings, steel cores, aluminum heat sinks and relay contacts."))

    if features.get("large_ic_chips") and ic_count>=2:
        candidates.append(_candidate("IC-Rich Logic Area","component_region",68+min(10,ic_count),
            [f"{ic_count} IC-like packages","visual and component evidence agree on a logic-style area"],
            "Use package type and board context before assigning precious-metal value."))

    if dominant=="mixed" and ic_count>=2 and (cap_count+block_count)>=2:
        candidates.append(_candidate("Mixed Logic / Power Board","board",74,
            [f"{ic_count} IC-like packages",f"{cap_count+block_count} filtered power-component candidates"],
            "Sort by board function and recoverable components rather than forcing a PC-motherboard family."))

    for match in reference_intelligence.get("matches",[]):
        label=match.get("category")
        if not label: continue
        rank=int(match.get("value_rank",0) or 0)
        candidates.append(_candidate(label,"reference_match",48+min(22,rank*2),
            [match.get("reason","reference-library evidence")],match.get("sorting_advice",""),
            "Reference knowledge supports recognition but does not replace visual confirmation."))

    merged={}
    for item in candidates:
        key=item["label"].lower()
        if key not in merged or item["score"]>merged[key]["score"]: merged[key]=item
        else:
            for e in item["evidence"]:
                if e not in merged[key]["evidence"]: merged[key]["evidence"].append(e)
    ranked=sorted(merged.values(),key=lambda i:i["score"],reverse=True)
    top=ranked[0] if ranked else None; second=ranked[1] if len(ranked)>1 else None
    if top:
        raw=min(95,max(25,top["score"])); margin=top["score"]-(second["score"] if second else top["score"]-25)
        if margin<=3: confidence=min(raw,66); status="ambiguous_match"
        elif margin<=7: confidence=min(raw,75); status="likely_match"
        elif margin<=12: confidence=min(raw,84); status="likely_match"
        else: confidence=raw; status="likely_match" if confidence>=70 else "possible_match"
        if confidence<60: status="possible_match"
    else:
        confidence=0; margin=0; status="no_strong_match"
    return {"status":status,"top_match":top,"candidates":ranked[:6],"confidence":confidence,
            "score_margin":int(margin),"mode":"Spike Glass v0.5",
            "evidence_summary":{"ic_like":ic_count,"capacitor_like":cap_count,"contact_pad_like":contact_count,
                                "solder_joint_like":solder_count,"solder_side_likelihood":solder_side,
                                "contact_pattern_score":contact_pattern,"power_block_like":block_count,
                                "dominant_family":dominant,"logic_component_ratio":logic_ratio,"power_component_ratio":power_ratio},
            "note":"SPIKE weighs evidence, contradictions and board-side context before naming a family."}
