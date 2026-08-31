"""SPIKE Same-Board Verification Gate v0.3.
Classification contradictions and physical-board fingerprints are evaluated before
multi-photo evidence is allowed to merge. Geometry is conservative around crops,
front/back views and perspective, but extreme contradictions cannot earn a clean pass.
"""
from routes.board_fingerprint import fingerprint_conflict

def _family(r):
 t=str(r.get("board_type","unknown")).lower()
 if "motherboard" in t or "main logic" in t:return "logic"
 if "power" in t or "supply" in t:return "power"
 if "expansion" in t or "gold finger" in t:return "expansion"
 if "control" in t:return "control"
 if "phone" in t or "mobile" in t:return "mobile"
 return "unknown"
def _anchors(r):
 s=r.get("signals") or {};return {"processor":bool(s.get("processor")),"ram":bool(s.get("ram") or s.get("possible_ram")),"large_ic":bool(s.get("large_ic_chips")),"power":bool(s.get("possible_power_board") or s.get("power_board")),"gold_edge":bool(s.get("gold_fingers") or s.get("gold_finger_edge")),"motherboard":bool(s.get("possible_motherboard"))}
def _severity(c):
 if not c or not c.get("conflict"):return 0
 # Current fingerprint engine reports aspect mismatch plus corroborating hole/landmark mismatch.
 # A large aspect ratio mismatch is useful as an escalation signal, never as sole identity proof.
 vals=[]
 for k in ("aspect_ratio_mismatch","aspect_mismatch_ratio","board_aspect_ratio_mismatch"):
  try:
   if c.get(k) is not None:vals.append(float(c[k]))
  except:pass
 return max(vals or [1.0])
def verify_same_board(results):
 n=len(results or [])
 if n<2:return {"version":"SPIKE Same-Board Verification Gate v0.3","status":"INSUFFICIENT_VIEWS","same_board":None,"confidence":0,"block_reconciliation":False,"reasons":["At least two views are needed for a multi-photo identity check."]}
 families=[_family(r) for r in results];known=[f for f in families if f!="unknown"];unique=set(known);anchors=[_anchors(r) for r in results];strong_conflict=False;uncertain_physical=False;reasons=[];physical=[];counts={f:known.count(f) for f in unique}
 if len(unique)>=2:
  ranked=sorted(counts.items(),key=lambda x:x[1],reverse=True);a,b=ranked[0],ranked[1];high={f:max([float(r.get("confidence",0) or 0) for r in results if _family(r)==f] or [0]) for f in unique}
  if (a[1]>=2 and b[1]>=2 and high[a[0]]>=75 and high[b[0]]>=75) or (high[a[0]]>=90 and high[b[0]]>=90):strong_conflict=True;reasons.append("Strong views support conflicting board families: "+a[0]+" versus "+b[0]+".")
 power_views=sum(1 for a in anchors if a["power"] and not a["motherboard"]);logic_views=sum(1 for a in anchors if a["motherboard"] or a["processor"] or a["ram"])
 if power_views>=2 and logic_views>=2:strong_conflict=True;reasons.append("Multiple views contain incompatible power-board and logic-board structural anchors.")
 for i in range(n):
  for j in range(i+1,n):
   c=fingerprint_conflict(results[i].get("physical_fingerprint") or {},results[j].get("physical_fingerprint") or {})
   if c:physical.append({"views":[i+1,j+1],**c})
 conflicts=[p for p in physical if p.get("conflict")];conflict_views={v for p in conflicts for v in p.get("views",[])}
 # Cluster rule: if a photo conflicts with multiple other large-board views, that is
 # corroborated evidence of a case split. This catches one foreign board mixed into a case.
 per_view={i:0 for i in range(1,n+1)}
 for p in conflicts:
  for v in p.get("views",[]):per_view[v]=per_view.get(v,0)+1
 cluster_conflict=any(v>=2 for v in per_view.values())
 if cluster_conflict or len(conflicts)>=2:
  strong_conflict=True;reasons.append("Physical fingerprints form incompatible large-view geometry across the case.")
 elif len(conflicts)==1:
  # With only one conflicting pair we do not claim multiple boards because front/back,
  # perspective or crop may explain it. But it can no longer receive PROBABLY SAME.
  uncertain_physical=True;reasons.append("One large-view physical fingerprint conflict needs another whole-board view before identity can be trusted.")
 if strong_conflict:return {"version":"SPIKE Same-Board Verification Gate v0.3","status":"MULTIPLE_BOARDS_SUSPECTED","same_board":False,"confidence":92,"block_reconciliation":True,"families":families,"physical_pair_checks":physical,"conflicting_views":sorted(conflict_views),"reasons":reasons,"rule":"Classification and physical geometry are checked before evidence can be merged."}
 if uncertain_physical or len(unique)>1:
  status="IDENTITY_UNCERTAIN";conf=55 if uncertain_physical else 60;reasons.append("SPIKE will not grant high combined confidence until board identity is better established.")
 else:
  status="PROBABLY_SAME_BOARD";conf=82;reasons.append("No strong cross-view family or physical-geometry contradiction was found.")
 return {"version":"SPIKE Same-Board Verification Gate v0.3","status":status,"same_board":True if status=="PROBABLY_SAME_BOARD" else None,"confidence":conf,"block_reconciliation":False,"families":families,"physical_pair_checks":physical,"conflicting_views":sorted(conflict_views),"reasons":reasons,"rule":"Absence of contradiction is not proof of identity; uncertain cases remain flagged."}
