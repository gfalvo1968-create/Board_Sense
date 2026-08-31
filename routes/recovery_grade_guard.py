"""SPIKE Recovery Grade Guard v0.2.
A recovery floor must be supported by corroborated physical evidence. A broad
classification label alone can never promote a board's economic grade.
"""
def apply_recovery_grade_guard(result):
    out=dict(result);signals=out.get("signals") or {};board=str(out.get("board_type","")).lower();grade=str(out.get("grade","LOW")).upper();evidence=[]
    logic_family=any(x in board for x in ("logic","motherboard","processor"));processor=bool(signals.get("processor"));large_ic=bool(signals.get("large_ic_chips") or signals.get("ic_signal_confirmed"));dense=bool(signals.get("dense_component_board")) or float(signals.get("component_density",0) or 0)>=.18;motherboard=bool(signals.get("possible_motherboard"));gold_edge=bool(signals.get("gold_fingers") or signals.get("gold_finger_edge"))
    if logic_family:evidence.append("broad logic-board classification")
    if processor:evidence.append("processor evidence")
    if large_ic:evidence.append("large/multiple logic-package evidence")
    if dense:evidence.append("dense component population")
    if motherboard:evidence.append("corroborated motherboard structure")
    if gold_edge:evidence.append("edge-contact evidence")
    # Classification is only context. Require at least two independent physical
    # anchors, one of which must be processor/IC evidence, before raising grade.
    anchors=sum([processor,large_ic,dense,motherboard,gold_edge]);logic_anchor=processor or large_ic;floor="MEDIUM" if logic_family and logic_anchor and anchors>=2 else None
    order={"N/A":-1,"LOW":0,"MEDIUM":1,"HIGH":2,"VERY HIGH":3};raised=bool(floor and order.get(grade,0)<order[floor])
    if raised:
        out["grade"]=floor;out["recommendation"]="Sort as a logic-rich recovery board; compare sell-whole, selective strip, and full-recovery economics before processing.";out["recovery_signals"]=list(dict.fromkeys((out.get("recovery_signals") or [])+["corroborated logic-rich recovery floor"]));out["grade_notes"]="Recovery Grade Guard raised LOW to MEDIUM only after multiple independent physical logic anchors corroborated the broad classification."
    out["recovery_grade_guard"]={"active":True,"raised_grade":raised,"original_grade":grade,"final_grade":out.get("grade",grade),"floor":floor,"evidence":evidence,"physical_anchor_count":anchors,"rule":"Classification labels never raise economic grade by themselves. A floor requires corroborated physical evidence.","pay_dirt_policy":"Grade floor does not automatically set Pay Dirt Ready. Pay Dirt remains evidence-driven.","model":"SPIKE Recovery Grade Guard v0.2"};return out
