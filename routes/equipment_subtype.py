"""SPIKE Equipment Subtype Reasoner v0.2.
Equipment subtype sits below broad board identity. PC/server labels require confirmed
physical architecture, while telecom and embedded families remain conservative.
"""
def infer_equipment_subtype(result):
    board_type=str(result.get("board_type","Unknown Board"));signals=result.get("signals") or {};mb=result.get("motherboard") or {};features=result.get("features") or {};ref=result.get("reference_intelligence") or {};hypotheses=ref.get("hypotheses") or []
    text=" ".join(str(x).lower() for x in [board_type,result.get("board_type_reason","")]+[h.get("type","") for h in hypotheses]);candidates=[]
    def add(label,score,evidence):candidates.append({"subtype":label,"score":score,"evidence":evidence})
    structure_score=int(signals.get("motherboard_score",signals.get("motherboard_structure_score",mb.get("motherboard_score",mb.get("score",0)))) or 0);confirmed_slot=bool(signals.get("confirmed_slot_bank") or mb.get("confirmed_slot_bank"));edge_bank=bool(mb.get("edge_connector_bank"));geometry_confirmed=confirmed_slot and edge_bank and structure_score>=9
    ram=bool(signals.get("ram") or signals.get("possible_ram"));processor=bool(signals.get("processor"));large_ic=bool(signals.get("large_ic_chips"))
    pc_evidence=[];pc_score=0
    if geometry_confirmed:pc_score+=4;pc_evidence.append("confirmed slot bank + edge connector bank + strong motherboard geometry")
    if processor:pc_score+=2;pc_evidence.append("processor evidence")
    if large_ic:pc_score+=1;pc_evidence.append("large/dense logic-package evidence")
    if ram:pc_score+=2;pc_evidence.append("memory-module evidence")
    if geometry_confirmed and ram and pc_score>=7:add("PC / Computer Mainboard",pc_score,pc_evidence)
    telecom=[];telecom_score=0
    if any(k in text for k in ("telecom","network")):telecom_score+=4;telecom.append("telecom/network reasoning evidence")
    if signals.get("large_board") and large_ic:telecom_score+=2;telecom.append("large dense logic board")
    if structure_score>=6 and not ram and not geometry_confirmed:telecom_score+=2;telecom.append("connector/backplane-like structure without confirmed PC memory architecture")
    if telecom_score>=5:add("Telecommunications / Network Logic Board",telecom_score,telecom)
    server=[];server_score=0
    if any(k in text for k in ("server","enterprise")):server_score+=4;server.append("server/enterprise hypothesis")
    if processor and ram:server_score+=2;server.append("processor plus memory architecture")
    if geometry_confirmed:server_score+=2;server.append("confirmed motherboard slot/edge geometry")
    if server_score>=7 and geometry_confirmed:add("Server / Enterprise Logic Board",server_score,server)
    power=[];power_score=0
    if signals.get("possible_power_board") or signals.get("power_board"):power_score+=3;power.append("power topology evidence")
    if int(signals.get("power_score",0) or 0)>=5:power_score+=2;power.append("strong power score")
    if power_score>=5 and not geometry_confirmed:add("Power / Conversion Equipment Board",power_score,power)
    broad_logic=bool(features.get("motherboard")) or "logic" in board_type.lower() or "motherboard" in board_type.lower()
    if broad_logic:add("Embedded / Proprietary Main Logic Board",3,["main-logic architecture indicated; equipment family not independently proven"])
    candidates.sort(key=lambda x:x["score"],reverse=True);best=candidates[0] if candidates else {"subtype":"Unresolved Equipment Family","score":0,"evidence":["insufficient equipment-specific evidence"]};margin=best["score"]-(candidates[1]["score"] if len(candidates)>1 else 0);confidence="high" if best["score"]>=7 and margin>=2 else ("moderate" if best["score"]>=5 else "low")
    return {"subtype":best["subtype"],"confidence":confidence,"evidence":best["evidence"],"candidates":candidates[:4],"geometry":{"confirmed_pc_architecture":geometry_confirmed,"confirmed_slot_bank":confirmed_slot,"edge_connector_bank":edge_bank,"motherboard_score":structure_score},"rule":"Broad board identity does not prove equipment subtype. PC/server labels require corroborated physical architecture.","model":"SPIKE Equipment Subtype Reasoner v0.2"}
