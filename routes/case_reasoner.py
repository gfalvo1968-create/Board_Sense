"""SPIKE Multi-Photo Case Reasoner v0.2.

Combines several photographs of one physical board. Strong structural evidence
outranks repeated weak hints, and repeated near-equivalent views do not gain full
voting authority merely because the camera moved a little.
"""
from copy import deepcopy
from routes.decision_guard import strong_structural_family, condition_harvest_check
from routes.equipment_subtype import infer_equipment_subtype


def _evidence_signature(r):
    s=r.get("signals") or {}
    return (
        str(r.get("board_type","Unknown Board")),
        bool(s.get("ram") or s.get("possible_ram")),
        bool(s.get("processor")), bool(s.get("large_ic_chips")),
        bool(s.get("possible_power_board") or s.get("power_board")),
        bool(s.get("gold_fingers") or s.get("gold_finger_edge")),
        bool(s.get("possible_motherboard")),
    )


def _view_role(r):
    sg=r.get("spike_glass") or {}; top=sg.get("top_match") or {}
    label=str(top.get("label","")).lower()
    comps=r.get("component_intelligence") or {}
    if "solder" in label or "trace side" in label: return "solder_or_trace_side"
    if "connector" in label or "gold finger" in label: return "connector_or_edge_detail"
    if "ic" in label or "logic" in label: return "logic_component_view"
    if "power" in label or comps.get("dominant_family")=="power_components": return "power_component_view"
    return "whole_board_or_general_view"


def reconcile_case(results):
    if not results:
        return {"board_type":"Unknown Board","confidence":0,"model":"SPIKE Multi-Photo Case Reasoner v0.2"}

    hard=[]
    for i,r in enumerate(results):
        s=strong_structural_family(r)
        if s: hard.append((i,r,s))
    if hard:
        _,winner,_=max(hard,key=lambda x: float(x[1].get("confidence",0) or 0))
    else:
        scores={}; seen={}
        for r in results:
            label=r.get("board_type","Unknown Board"); sig=_evidence_signature(r)
            base=max(0.15,float(r.get("confidence",0) or 0)/100.0)
            repeat=seen.get(sig,0)
            # First equivalent view has full weight. Repeats are corroboration,
            # not independent witnesses, and therefore receive diminishing weight.
            weight=base if repeat==0 else base*(0.35 if repeat==1 else 0.18)
            scores[label]=scores.get(label,0)+weight; seen[sig]=repeat+1
        label=max(scores,key=scores.get)
        winner=max((r for r in results if r.get("board_type")==label),key=lambda r:float(r.get("confidence",0) or 0))

    combined=deepcopy(winner)
    observations={}; view_summaries=[]; signatures={}
    for i,r in enumerate(results,1):
        mod=r.get("modification_intelligence") or {}
        for name,obs in (mod.get("observations") or {}).items():
            old=observations.get(name)
            if old is None or str(obs.get("status","")).lower() in ("removed","cut","harvested","missing_confirmed"):
                observations[name]=obs
        sig=_evidence_signature(r); repeat=signatures.get(sig,0); signatures[sig]=repeat+1
        view_summaries.append({"view":i,"role":_view_role(r),"board_type":r.get("board_type"),"confidence":r.get("confidence"),"grade":r.get("grade"),"modification_status":mod.get("status","not_evaluated"),"evidence_independence":"primary" if repeat==0 else "corroborating_repeat"})

    combined["condition_and_harvest"]=condition_harvest_check(combined,observations)
    combined["equipment_subtype"]=infer_equipment_subtype(combined)
    unique=len(signatures)
    combined["case_analysis"]={
        "mode":"same_board_multi_photo","views_analyzed":len(results),"independent_evidence_patterns":unique,
        "view_summaries":view_summaries,
        "duplicate_evidence_guard":{"active":True,"rule":"Repeated equivalent views corroborate but do not multiply authority at full weight."},
        "message":"Multiple photographs were treated as one physical board case. Structural evidence outranks repeated weak hints; view diversity outranks photo count.",
    }
    best=max(float(r.get("confidence",0) or 0) for r in results)
    combined["confidence"]=min(98,max(float(combined.get("confidence",0) or 0),best))
    combined["model"]="Board Sense v2.5 + SPIKE Multi-Photo Case Reasoner v0.2 + Equipment Subtype v0.1 + Verification v0.1"
    return combined
