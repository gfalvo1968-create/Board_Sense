"""SPIKE Recovery Grade Guard v0.5.

Economic grade promotion is anchored to directly observed recovery evidence.
Derived identity/classifier signals may explain a board, but cannot promote its
grade by themselves. Density-aware population evidence is now a valid recovery
anchor when it is supported by the image.

Pay Dirt is an inspection gate, not a claim of precious-metal chemistry or cash
value. MEDIUM logic boards can qualify only when dense population and large/
multiple IC evidence corroborate one another.
"""

def apply_recovery_grade_guard(result):
    out=dict(result)
    signals=out.get("signals") or {}
    board=str(out.get("board_type","")).lower()
    grade=str(out.get("grade","LOW")).upper()
    evidence=[]

    logic_family=any(x in board for x in ("logic","motherboard","processor","controller"))
    processor=bool(signals.get("processor"))
    large_ic=bool(signals.get("large_ic_chips") or signals.get("ic_signal_confirmed"))
    component_count=int(signals.get("component_count",0) or 0)
    component_density=float(signals.get("component_density",0) or 0)
    dense=bool(signals.get("dense_component_board")) or component_count>=8 or component_density>=.035
    gold_edge=bool(signals.get("gold_fingers") or signals.get("gold_finger_edge"))
    motherboard_context=bool(signals.get("possible_motherboard"))
    confirmed_slot_context=bool(signals.get("confirmed_slot_bank"))

    if logic_family:evidence.append("broad logic-board classification (context only)")
    if processor:evidence.append("processor evidence")
    if large_ic:evidence.append("large/multiple logic-package evidence")
    if dense:evidence.append(f"dense component population ({component_count} candidates)")
    if gold_edge:evidence.append("edge-contact evidence")
    if motherboard_context:evidence.append("motherboard detector candidate (identity context only)")
    if confirmed_slot_context:evidence.append("confirmed slot-bank geometry (identity context only)")

    recovery_anchors=sum([processor,large_ic,dense,gold_edge])
    logic_anchor=processor or large_ic or dense

    # MEDIUM is a floor, not a high-value claim. It simply prevents a visibly
    # dense logic board from being flattened to LOW when multiple recovery-
    # bearing observations agree.
    floor="MEDIUM" if logic_family and logic_anchor and recovery_anchors>=2 else None

    order={"N/A":-1,"LOW":0,"MEDIUM":1,"HIGH":2,"VERY HIGH":3}
    raised=bool(floor and order.get(grade,0)<order[floor])

    if raised:
        out["grade"]=floor
        out["recommendation"]="Sort as a logic-rich recovery board; compare sell-whole, selective strip, and full-recovery economics before processing."
        out["recovery_signals"]=list(dict.fromkeys((out.get("recovery_signals") or [])+[
            "corroborated recovery-bearing logic evidence",
            "dense IC population" if dense else "logic-package evidence",
        ]))
        out["grade_notes"]="Recovery Grade Guard raised LOW to MEDIUM only after multiple recovery-bearing observations corroborated the broad logic context."

    final_grade=str(out.get("grade",grade)).upper()
    existing_pay_dirt=bool(out.get("pay_dirt_ready",False))

    # Evidence-driven MEDIUM exception. A logic-rich board that has both a
    # dense component population and corroborated large/multiple IC evidence
    # deserves the Pay Dirt inspection route even though MEDIUM by itself does
    # not. This opens investigation only; it does not claim gold, bond-wire
    # chemistry, recoverable mass, or dollar value from the photo.
    medium_logic_pay_dirt=bool(
        not existing_pay_dirt
        and final_grade=="MEDIUM"
        and logic_family
        and dense
        and large_ic
        and recovery_anchors>=2
    )

    if medium_logic_pay_dirt:
        out["pay_dirt_ready"]=True
        out["pay_dirt_reason"]="Dense logic-board population plus corroborated large/multiple IC evidence qualifies this board for Pay Dirt inspection. Precious-metal chemistry, recoverable mass, and cash value remain unverified."
        out["recovery_signals"]=list(dict.fromkeys((out.get("recovery_signals") or [])+[
            "dense IC population warrants Pay Dirt inspection"
        ]))
    elif existing_pay_dirt:
        out["pay_dirt_ready"]=True
        out.setdefault("pay_dirt_reason","Reference grade already qualifies this board for Pay Dirt inspection; material chemistry and value still require separate evidence.")
    else:
        out["pay_dirt_ready"]=False

    out["recovery_grade_guard"]={
        "active":True,
        "raised_grade":raised,
        "original_grade":grade,
        "final_grade":out.get("grade",grade),
        "floor":floor,
        "evidence":evidence,
        "recovery_anchor_count":recovery_anchors,
        "component_population":{"count":component_count,"density":component_density,"dense":dense},
        "identity_context":{"possible_motherboard":motherboard_context,"confirmed_slot_bank":confirmed_slot_context},
        "rule":"Identity and structural labels never raise economic grade. A floor requires corroborated recovery-bearing evidence.",
        "pay_dirt_policy":"HIGH/VERY HIGH retain their reference Pay Dirt status. MEDIUM qualifies only when logic context is backed by both dense population and large/multiple IC recovery evidence. Pay Dirt opens an inspection route; it does not prove precious-metal chemistry or value.",
        "pay_dirt_promoted":medium_logic_pay_dirt,
        "pay_dirt_ready":bool(out.get("pay_dirt_ready",False)),
        "model":"SPIKE Recovery Grade Guard v0.5",
    }
    return out
