"""SPIKE Equipment Subtype Reasoner v0.1.

Adds a cautious equipment-family layer below the broad board family. It does not
replace board_type and it never invents product identity from generic geometry.
"""


def infer_equipment_subtype(result):
    board_type=str(result.get("board_type","Unknown Board"))
    signals=result.get("signals") or {}
    motherboard=(result.get("features") or {}).get("motherboard",False)
    ref=result.get("reference_intelligence") or {}
    hypotheses=ref.get("hypotheses") or []
    text=" ".join(str(x).lower() for x in [board_type, result.get("board_type_reason","")] + [h.get("type","") for h in hypotheses])

    candidates=[]
    def add(label,score,evidence):
        candidates.append({"subtype":label,"score":score,"evidence":evidence})

    # PC requires several independent PC-like structural cues. A large board plus
    # generic long connectors is not enough because telecom/console/industrial
    # logic boards commonly share that geometry.
    structure_score=int(signals.get("motherboard_structure_score",0) or 0)
    if not structure_score:
        structure_score=int((result.get("board_blueprint") or {}).get("context_guard",{}).get("motherboard_structure_score",0) or 0)
    pc_evidence=[]; pc_score=0
    if structure_score>=9: pc_score+=3; pc_evidence.append("very strong motherboard structural score")
    if signals.get("processor"): pc_score+=2; pc_evidence.append("processor evidence")
    if signals.get("large_ic_chips"): pc_score+=1; pc_evidence.append("dense logic/large IC evidence")
    if signals.get("ram") or signals.get("possible_ram"): pc_score+=2; pc_evidence.append("memory-module evidence")
    if pc_score>=5 and (signals.get("ram") or signals.get("possible_ram")): add("PC / Computer Mainboard",pc_score,pc_evidence)

    telecom=[]; telecom_score=0
    if any(k in text for k in ("telecom","network")): telecom_score+=4; telecom.append("telecom/network reasoning evidence")
    if signals.get("large_board") and signals.get("large_ic_chips"): telecom_score+=2; telecom.append("large dense logic board")
    if structure_score>=6 and not (signals.get("ram") or signals.get("possible_ram")): telecom_score+=2; telecom.append("backplane/connector-style structure without memory-module evidence")
    if telecom_score>=5: add("Telecommunications / Network Logic Board",telecom_score,telecom)

    server=[]; server_score=0
    if any(k in text for k in ("server","enterprise")): server_score+=4; server.append("server/enterprise hypothesis")
    if signals.get("processor") and (signals.get("ram") or signals.get("possible_ram")): server_score+=2; server.append("processor plus memory architecture")
    if server_score>=5: add("Server / Enterprise Logic Board",server_score,server)

    power=[]; power_score=0
    if signals.get("possible_power_board") or signals.get("power_board"): power_score+=3; power.append("power topology evidence")
    if int(signals.get("power_score",0) or 0)>=5: power_score+=2; power.append("strong power score")
    if power_score>=5 and not motherboard: add("Power / Conversion Equipment Board",power_score,power)

    # Broad fallback is intentionally useful rather than falsely precise.
    broad_logic=motherboard or "logic" in board_type.lower() or "motherboard" in board_type.lower()
    if broad_logic: add("Embedded / Proprietary Main Logic Board",3,["main-logic architecture confirmed; equipment family not independently proven"])

    candidates.sort(key=lambda x:x["score"],reverse=True)
    best=candidates[0] if candidates else {"subtype":"Unresolved Equipment Family","score":0,"evidence":["insufficient equipment-specific evidence"]}
    margin=best["score"]-(candidates[1]["score"] if len(candidates)>1 else 0)
    confidence="high" if best["score"]>=7 and margin>=2 else ("moderate" if best["score"]>=5 else "low")
    return {"subtype":best["subtype"],"confidence":confidence,"evidence":best["evidence"],"candidates":candidates[:4],"rule":"Broad board family may be confident while equipment subtype remains conservative.","model":"SPIKE Equipment Subtype Reasoner v0.1"}
