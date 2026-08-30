"""SPIKE Recovery Economics v0.2.

Compare sell-whole, partial-strip, and full-recovery paths without inventing
prices. Values enter only when supplied by a buyer, market bridge, verified
recovery estimate, or the operator. Labor and processing costs stay visible.
"""


def _num(value):
    if value is None or value == "": return None
    try: return float(value)
    except (TypeError, ValueError): return None


def _path(name, gross_value, minutes=0, costs=0, residual_value=0):
    gross=_num(gross_value); mins=_num(minutes) or 0.0; cost=_num(costs) or 0.0; residual=_num(residual_value) or 0.0
    if gross is None: return {"path":name,"status":"needs_value"}
    net=gross+residual-cost
    return {"path":name,"status":"ready","gross_value":round(gross,2),"residual_value":round(residual,2),"processing_costs":round(cost,2),"labor_minutes":round(mins,1),"net_value":round(net,2),"net_value_per_minute":round(net/mins,2) if mins>0 else None,"net_value_per_hour":round(net/mins*60,2) if mins>0 else None}


def compare_paths(sell_whole_value=None, partial_recovered_value=None, partial_residual_value=None,
                  partial_minutes=None, partial_costs=None, full_recovery_value=None,
                  full_minutes=None, full_costs=None, condition_factor=1.0):
    """Return a transparent three-path decision packet.

    condition_factor may reduce only the whole-board baseline when confirmed
    harvesting has already removed value. It is not used to fabricate recovery
    yields. Partial/full values must still be supplied or independently derived.
    """
    sell=_num(sell_whole_value); factor=_num(condition_factor)
    factor=1.0 if factor is None else max(0.0,min(1.0,factor))
    adjusted_sell=(sell*factor) if sell is not None else None
    paths=[
        _path("SELL WHOLE",adjusted_sell,0,0,0),
        _path("PARTIAL STRIP",partial_recovered_value,partial_minutes,partial_costs,partial_residual_value),
        _path("FULL RECOVERY",full_recovery_value,full_minutes,full_costs,0),
    ]
    ready=[p for p in paths if p.get("status")=="ready"]
    if not ready:
        return {"mode":"SPIKE Recovery Economics v0.2","status":"needs_values","paths":paths,"message":"Add verified values before SPIKE chooses an economic path. No dollar value is invented from the image."}
    winner=max(ready,key=lambda p:p["net_value"])
    sell_path=paths[0] if paths[0].get("status")=="ready" else None
    for p in ready:
        if sell_path:
            p["gain_over_sell_whole"]=round(p["net_value"]-sell_path["net_value"],2)
            if p["labor_minutes"]>0:p["incremental_value_per_minute"]=round((p["net_value"]-sell_path["net_value"])/p["labor_minutes"],2)
    return {"mode":"SPIKE Recovery Economics v0.2","status":"ready","condition_factor_applied_to_whole_board":factor,"paths":paths,"recommended_path":winner["path"],"recommended_net_value":winner["net_value"],"rule":"Choose from verified economics; keep labor, processing cost, residual board value, and condition deductions visible.","pricing_integrity":"No assay yield or dollar value is inferred from image color alone."}


def compare_recovery_to_sale(sell_value=None, recovered_value=None, minutes=None):
    """Backward-compatible two-path helper used by the existing Recovery Lab UI."""
    result=compare_paths(sell_whole_value=sell_value,full_recovery_value=recovered_value,full_minutes=minutes)
    if result.get("status")!="ready" or not all(_num(x) is not None for x in (sell_value,recovered_value,minutes)) or (_num(minutes) or 0)<=0:
        return {"status":"needs_values","message":"Add whole-item sale value, expected recovered value, and labor minutes to compare options."}
    sellp=result["paths"][0]; recp=result["paths"][2]; extra=recp["net_value"]-sellp["net_value"]; per_min=extra/float(minutes); per_hour=per_min*60
    if extra<=0: decision="SELL WHOLE"
    elif per_hour>=60: decision="RECOVERY LOOKS STRONG"
    elif per_hour>=25: decision="RECOVERY MAY BE WORTHWHILE"
    else: decision="SELL WHOLE / REVIEW LABOR"
    return {"status":"ready","sell_value":sellp["net_value"],"recovered_value":recp["net_value"],"extra_value":round(extra,2),"minutes":round(float(minutes),1),"extra_value_per_minute":round(per_min,2),"extra_value_per_hour":round(per_hour,2),"decision":decision,"economics":result}
