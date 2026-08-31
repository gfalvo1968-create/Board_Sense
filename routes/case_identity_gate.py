"""SPIKE Same-Board Verification Gate v0.6.
Checks contradiction first, then allows multiple usable whole-board views with
compatible geometry to become positive same-board evidence. Color alone never proves identity.
"""
from routes.board_fingerprint import fingerprint_conflict

def _family(r):
 t=str(r.get("board_type","unknown")).lower()
 if "motherboard" in t or "main logic" in t or "dense logic" in t:return "logic"
 if "power" in t or "supply" in t:return "power"
 if "expansion" in t or "gold finger" in t:return "expansion"
 if "control" in t:return "control"
 if "phone" in t or "mobile" in t:return "mobile"
 return "unknown"
def _anchors(r):
 s=r.get("signals") or {};return {"processor":bool(s.get("processor")),"ram":bool(s.get("ram") or s.get("possible_ram")),"large_ic":bool(s.get("large_ic_chips")),"power":bool(s.get("possible_power_board") or s.get("power_board")),"gold_edge":bool(s.get("gold_fingers") or s.get("gold_finger_edge")),"motherboard":bool(s.get("possible_motherboard"))}
def _usable_whole(f):return f.get("coverage")=="whole_or_large_view" and f.get("geometry_quality") in ("good","medium")
def verify_same_board(results):
 n=len(results or [])
 if n<2:return {"version":"SPIKE Same-Board Verification Gate v0.6","status":"INSUFFICIENT_VIEWS","same_board":None,"confidence":0,"block_reconciliation":False,"whole_view_count":0,"conflict_graph":[],"identity_next_step":"Add at least one more photo of the same physical board.","reasons":["At least two views are needed for a multi-photo identity check."]}
 families=[_family(r) for r in results];known=[f for f in families if f!="unknown"];unique=set(known);anchors=[_anchors(r) for r in results];strong_conflict=False;uncertain_physical=False;reasons=[];physical=[];counts={f:known.count(f) for f in unique};fps=[r.get("physical_fingerprint") or {} for r in results];whole_views=[i+1 for i,f in enumerate(fps) if _usable_whole(f)]
 if len(unique)>=2:
  ranked=sorted(counts.items(),key=lambda x:x[1],reverse=True);a,b=ranked[0],ranked[1];high={f:max([float(r.get("confidence",0) or 0) for r in results if _family(r)==f] or [0]) for f in unique}
  if (a[1]>=2 and b[1]>=2 and high[a[0]]>=75 and high[b[0]]>=75) or (high[a[0]]>=90 and high[b[0]]>=90):strong_conflict=True;reasons.append("Strong views support conflicting board families: "+a[0]+" versus "+b[0]+".")
 power_views=sum(1 for a in anchors if a["power"] and not a["motherboard"]);logic_views=sum(1 for a in anchors if a["motherboard"] or a["processor"] or a["ram"])
 # Power and logic can legitimately coexist on controller/inverter boards. Only use
 # this as a contradiction when both sides are independently strong and families disagree.
 if power_views>=2 and logic_views>=2 and len(unique)>=2 and "power" in unique and "logic" in unique:reasons.append("Power and logic structures coexist; treating topology as mixed until physical identity is checked rather than automatically splitting the case.")
 for i in range(n):
  for j in range(i+1,n):
   c=fingerprint_conflict(fps[i],fps[j])
   if c:physical.append({"views":[i+1,j+1],**c})
 conflicts=[p for p in physical if p.get("conflict")];conflict_views={v for p in conflicts for v in p.get("views",[])};per_view={i:0 for i in range(1,n+1)}
 for p in conflicts:
  for v in p.get("views",[]):per_view[v]=per_view.get(v,0)+1
 conflict_graph=[{"view":i,"conflict_degree":per_view.get(i,0)} for i in range(1,n+1) if per_view.get(i,0)>0];outliers=[i for i,d in per_view.items() if d>=2]
 if outliers:strong_conflict=True;reasons.append("A whole-board view conflicts with at least two other usable board geometries, forming a coherent physical outlier.")
 elif conflicts:uncertain_physical=True;reasons.append("Physical fingerprint disagreement exists, but it does not yet form a corroborated multiple-board cluster.")
 if strong_conflict:return {"version":"SPIKE Same-Board Verification Gate v0.6","status":"MULTIPLE_BOARDS_SUSPECTED","same_board":False,"confidence":92,"block_reconciliation":True,"families":families,"whole_view_count":len(whole_views),"whole_view_indices":whole_views,"physical_pair_checks":physical,"conflict_graph":conflict_graph,"conflicting_views":sorted(conflict_views),"identity_next_step":"Split the photos by physical board and start a separate case for each board.","reasons":reasons,"rule":"Semantic contradiction or a corroborated physical outlier is required before reconciliation is hard-blocked."}
 compatible_pairs=sum(1 for p in physical if not p.get("conflict"))
 positive_geometry=len(whole_views)>=2 and compatible_pairs>=1 and not uncertain_physical
 # Mixed classifier labels from closeups are not enough to keep identity uncertain
 # once multiple whole-board views physically agree and there is no hard contradiction.
 if positive_geometry:
  status="PROBABLY_SAME_BOARD";conf=min(94,84+min(10,(len(whole_views)-2)*3+compatible_pairs));reasons.append("Multiple usable whole-board views have compatible rotation-safe physical geometry with no corroborated outlier.");next_step="No extra identity photo required unless a later view introduces a physical contradiction."
 elif uncertain_physical or len(unique)>1:
  status="IDENTITY_UNCERTAIN";conf=50 if uncertain_physical and len(whole_views)<=2 else (55 if uncertain_physical else 60);reasons.append("SPIKE will not grant high combined confidence until board identity is better established.");next_step="Add one clear full-board photo that shows the complete board outline, mounting holes, and major connector positions."
 else:
  status="PROBABLY_SAME_BOARD";conf=82;reasons.append("No strong cross-view family or corroborated physical-geometry contradiction was found.");next_step="No extra identity photo required unless the case result remains otherwise uncertain."
 return {"version":"SPIKE Same-Board Verification Gate v0.6","status":status,"same_board":True if status=="PROBABLY_SAME_BOARD" else None,"confidence":conf,"block_reconciliation":False,"families":families,"whole_view_count":len(whole_views),"whole_view_indices":whole_views,"physical_pair_checks":physical,"conflict_graph":conflict_graph,"conflicting_views":sorted(conflict_views),"identity_next_step":next_step,"reasons":reasons,"positive_geometry_evidence":positive_geometry,"rule":"Compatible geometry from multiple usable whole-board views is positive identity evidence; color alone and absence of contradiction are not proof."}
