"""SPIKE Multi-Photo Case Reasoner v0.1.

Combines several photographs of one physical board without treating each image as
a separate purchase item. Strong structural evidence outranks repeated weak visual
hints. Condition observations are accumulated conservatively across views.
"""
from collections import Counter
from copy import deepcopy
from routes.decision_guard import strong_structural_family, condition_harvest_check


def reconcile_case(results):
    if not results:
        return {"board_type":"Unknown Board","confidence":0,"model":"SPIKE Multi-Photo Case Reasoner v0.1"}

    # A hard structural anchor in any clear view has first authority.
    hard=[]
    for i,r in enumerate(results):
        s=strong_structural_family(r)
        if s: hard.append((i,r,s))
    if hard:
        _,winner,_=max(hard,key=lambda x: float(x[1].get("confidence",0) or 0))
    else:
        # Otherwise use confidence-weighted family voting, so six mediocre hints
        # cannot automatically beat one much clearer photograph.
        scores={}
        for r in results:
            label=r.get("board_type","Unknown Board")
            scores[label]=scores.get(label,0)+max(0.15,float(r.get("confidence",0) or 0)/100.0)
        label=max(scores,key=scores.get)
        winner=max((r for r in results if r.get("board_type")==label),key=lambda r:float(r.get("confidence",0) or 0))

    combined=deepcopy(winner)
    observations={}
    view_summaries=[]
    for i,r in enumerate(results,1):
        mod=r.get("modification_intelligence") or {}
        for name,obs in (mod.get("observations") or {}).items():
            old=observations.get(name)
            # Never upgrade uncertainty to confirmed loss merely by repetition.
            # Confirmed status must already come from a detector/inspection source.
            if old is None or str(obs.get("status","")).lower() in ("removed","cut","harvested","missing_confirmed"):
                observations[name]=obs
        view_summaries.append({"view":i,"board_type":r.get("board_type"),"confidence":r.get("confidence"),"grade":r.get("grade"),"modification_status":mod.get("status","not_evaluated")})

    combined["condition_and_harvest"]=condition_harvest_check(combined,observations)
    combined["case_analysis"]={
        "mode":"same_board_multi_photo",
        "views_analyzed":len(results),
        "view_summaries":view_summaries,
        "message":"Multiple photographs were treated as one physical board case. Structural evidence outranks repeated weak visual hints.",
    }
    combined["confidence"]=min(98,max(float(combined.get("confidence",0) or 0), max(float(r.get("confidence",0) or 0) for r in results)))
    combined["model"]="Board Sense v2.4 + SPIKE Multi-Photo Case Reasoner v0.1 + Verification v0.1"
    return combined
