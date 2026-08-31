"""SPIKE Equipment Subtype Reasoner v0.3.
Separates pure power conversion from boards that combine substantial power handling
with digital/control logic. PC/server labels still require confirmed architecture.
"""
def infer_equipment_subtype(result):
    board_type=str(result.get("board_type","Unknown Board"));signals=result.get("signals") or {};mb=result.get("motherboard") or {};features=result.get("features") or {};ref=result.get("reference_intelligence") or {};hypotheses=ref.get("hypotheses") or []
    text=" ".join(str(x).lower() for x in [board_type,result.get("board_type_reason","")]+[h.get("type","") for h in hypotheses]);candidates=[]
    def add(label,score,evidence):candidates.append({"subtype":label,"score":score,"evidence":evidence})
    structure_score=int(signals.get("motherboard_score",signals.get("motherboard_structure_score",mb.get("motherboard_score",mb.get("score",0)))) or 0);confirmed_slot=bool(signals.get("confirmed_slot_bank") or mb.get("confirmed_slot_bank"));edge_bank=bool(mb.get("edge_connector_bank"));geometry_confirmed=confirmed_slot and edge_bank and structure_score>=9
    ram=bool(signals.get("ram") or signals.get("possible_ram"));processor=bool(signals.get("processor"));large_ic=bool(signals.get("large_ic_chips"));dense=bool(signals.get("dense_component_board"));power_present=bool(signals.get("possible_power_board") or signals.get("power_board"));power_score=int(signals.get("power_score",0) or 0);logic_present=processor or large_ic or dense or "logic" in board_type.lower() or "control" in board_type.lower()
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
    # Mixed power-control is deliberately distinct from a simple PSU. A controller,
    # drive, appliance, industrial or proprietary board can contain both muscle and brains.
    mixed=[];mixed_score=0
    if power_present or power_score>=4:mixed_score+=3;mixed.append("substantial power-handling topology")
    if power_score>=6:mixed_score+=2;mixed.append("strong power topology score")
    if large_ic:mixed_score+=2;mixed.append("large logic/control IC evidence")
    if processor:mixed_score+=2;mixed.append("processor/controller evidence")
    if dense:mixed_score+=1;mixed.append("dense control-component population")
    if ("control" in text or "controller" in text):mixed_score+=2;mixed.append("control-family reasoning evidence")
    if mixed_score>=7 and logic_present and not geometry_confirmed:add("Power-Control / Controller Equipment Board",mixed_score,mixed)
    power=[];pure_power_score=0
    if power_present:pure_power_score+=3;power.append("power topology evidence")
    if power_score>=5:pure_power_score+=2;power.append("strong power score")
    if logic_present:pure_power_score-=2;power.append("logic/control population reduces pure-supply confidence")
    if pure_power_score>=5 and not geometry_confirmed:add("Power / Conversion Equipment Board",pure_power_score,power)
    broad_logic=bool(features.get("motherboard")) or "logic" in board_type.lower() or "motherboard" in board_type.lower() or "control" in board_type.lower()
    if broad_logic:add("Embedded / Proprietary Main Logic Board",3,["main-logic/control architecture indicated; equipment family not independently proven"])
    candidates.sort(key=lambda x:x["score"],reverse=True);best=candidates[0] if candidates else {"subtype":"Unresolved Equipment Family","score":0,"evidence":["insufficient equipment-specific evidence"]};margin=best["score"]-(candidates[1]["score"] if len(candidates)>1 else 0);confidence="high" if best["score"]>=7 and margin>=2 else ("moderate" if best["score"]>=5 else "low")
    return {"subtype":best["subtype"],"confidence":confidence,"evidence":best["evidence"],"candidates":candidates[:5],"geometry":{"confirmed_pc_architecture":geometry_confirmed,"confirmed_slot_bank":confirmed_slot,"edge_connector_bank":edge_bank,"motherboard_score":structure_score},"topology":{"power_present":power_present,"power_score":power_score,"logic_present":logic_present},"rule":"Broad identity does not prove equipment subtype. Mixed power plus control logic is evaluated separately from a pure supply; PC/server labels require corroborated architecture.","model":"SPIKE Equipment Subtype Reasoner v0.3"}
