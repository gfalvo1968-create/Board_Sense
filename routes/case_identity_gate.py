"""SPIKE Same-Board Verification Gate v0.1.

Checks whether a multi-photo case is internally coherent before SPIKE merges
its evidence. This is deliberately conservative: different sides/details of
one board are allowed, but conflicting strong board-family fingerprints can
block reconciliation. Visual similarity alone never proves identity.
"""

def _family(r):
    t=str(r.get("board_type","unknown")).lower()
    if "motherboard" in t or "main logic" in t:return "logic"
    if "power" in t or "supply" in t:return "power"
    if "expansion" in t or "gold finger" in t:return "expansion"
    if "control" in t:return "control"
    if "phone" in t or "mobile" in t:return "mobile"
    return "unknown"

def _anchors(r):
    s=r.get("signals") or {}
    return {
      "processor":bool(s.get("processor")),
      "ram":bool(s.get("ram") or s.get("possible_ram")),
      "large_ic":bool(s.get("large_ic_chips")),
      "power":bool(s.get("possible_power_board") or s.get("power_board")),
      "gold_edge":bool(s.get("gold_fingers") or s.get("gold_finger_edge")),
      "motherboard":bool(s.get("possible_motherboard")),
    }

def verify_same_board(results):
    n=len(results or [])
    if n<2:
        return {"version":"SPIKE Same-Board Verification Gate v0.1","status":"INSUFFICIENT_VIEWS","same_board":None,"confidence":0,"block_reconciliation":False,"reasons":["At least two views are needed for a multi-photo identity check."]}
    families=[_family(r) for r in results]
    known=[f for f in families if f!="unknown"]
    unique=set(known)
    anchors=[_anchors(r) for r in results]
    strong_conflict=False;reasons=[]
    # A repeated, high-confidence family opposed by another repeated/high-confidence
    # family is evidence that the case may contain multiple physical boards.
    counts={f:known.count(f) for f in unique}
    if len(unique)>=2:
        ranked=sorted(counts.items(),key=lambda x:x[1],reverse=True)
        a,b=ranked[0],ranked[1]
        high_by_family={f:max([float(r.get("confidence",0) or 0) for r in results if _family(r)==f] or [0]) for f in unique}
        if (a[1]>=2 and b[1]>=2 and high_by_family[a[0]]>=75 and high_by_family[b[0]]>=75) or (high_by_family[a[0]]>=90 and high_by_family[b[0]]>=90):
            strong_conflict=True
            reasons.append("Strong views support conflicting board families: "+a[0]+" versus "+b[0]+".")
    # Strong mutually exclusive topology conflict. One isolated detail view is not enough.
    power_views=sum(1 for a in anchors if a["power"] and not a["motherboard"])
    logic_views=sum(1 for a in anchors if a["motherboard"] or a["processor"] or a["ram"])
    if power_views>=2 and logic_views>=2:
        strong_conflict=True;reasons.append("Multiple views contain incompatible power-board and logic-board structural anchors.")
    if strong_conflict:
        return {"version":"SPIKE Same-Board Verification Gate v0.1","status":"MULTIPLE_BOARDS_SUSPECTED","same_board":False,"confidence":90,"block_reconciliation":True,"families":families,"reasons":reasons,"rule":"Do not merge conflicting physical-board evidence into a Frankenstein classification."}
    if len(unique)<=1:
        status="PROBABLY_SAME_BOARD";conf=78
        reasons.append("No strong cross-view board-family contradiction was found.")
    else:
        status="IDENTITY_UNCERTAIN";conf=58
        reasons.append("Views vary in board-family interpretation, but evidence is not strong enough to prove multiple boards.")
    return {"version":"SPIKE Same-Board Verification Gate v0.1","status":status,"same_board":True if status=="PROBABLY_SAME_BOARD" else None,"confidence":conf,"block_reconciliation":False,"families":families,"reasons":reasons,"rule":"Absence of contradiction is not proof of identity; uncertain cases remain flagged."}
