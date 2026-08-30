"""SPIKE Multi-Photo Case Reasoner v0.6.

Reconciles several photographs only after the Same-Board Verification Gate
checks the case for strong contradictory physical-board evidence.
"""
from copy import deepcopy
from routes.decision_guard import strong_structural_family, condition_harvest_check
from routes.equipment_subtype import infer_equipment_subtype
from routes.recovery_grade_guard import apply_recovery_grade_guard
from routes.case_identity_gate import verify_same_board
from recovery_lab.core.time_value import compare_paths
LOSS={"removed","cut","harvested","missing_confirmed","clearly_cut","clearly_harvested"};PRESENT={"present","confirmed_present","visible","retained"};UNCERTAIN={"not_visible","uncertain","unknown","expected_not_visible","probably_removed"}
def _evidence_signature(r):
 s=r.get("signals") or {};return (str(r.get("board_type","Unknown Board")),bool(s.get("ram") or s.get("possible_ram")),bool(s.get("processor")),bool(s.get("large_ic_chips")),bool(s.get("possible_power_board") or s.get("power_board")),bool(s.get("gold_fingers") or s.get("gold_finger_edge")),bool(s.get("possible_motherboard")))
def _view_role(r):
 sg=r.get("spike_glass") or {};top=sg.get("top_match") or {};label=str(top.get("label","")).lower();comps=r.get("component_intelligence") or {}
 if "solder" in label or "trace side" in label:return "solder_or_trace_side"
 if "connector" in label or "gold finger" in label:return "connector_or_edge_detail"
 if "ic" in label or "logic" in label:return "logic_component_view"
 if "power" in label or comps.get("dominant_family")=="power_components":return "power_component_view"
 return "whole_board_or_general_view"
def _merge_observation(store,name,obs,view):
 if not isinstance(obs,dict):obs={"status":str(obs)}
 incoming=dict(obs);incoming["source"]=f"view_{view}";state=str(incoming.get("status","unknown")).lower();old=store.get(name)
 if old is None:store[name]=incoming;return
 oldstate=str(old.get("status","unknown")).lower()
 if state in LOSS:store[name]=incoming
 elif state in PRESENT and oldstate not in LOSS:store[name]=incoming
 elif oldstate in PRESENT or oldstate in LOSS:return
 elif state in UNCERTAIN:old["note"]=(old.get("note","")+" Seen as uncertain/not visible in another view.").strip()
def _economics_inputs(result):
 raw=result.get("economics_inputs") or result.get("recovery_economics_inputs") or {};return {"sell_whole_value":raw.get("sell_whole_value"),"partial_recovered_value":raw.get("partial_recovered_value"),"partial_residual_value":raw.get("partial_residual_value"),"partial_minutes":raw.get("partial_minutes"),"partial_costs":raw.get("partial_costs"),"full_recovery_value":raw.get("full_recovery_value"),"full_minutes":raw.get("full_minutes"),"full_costs":raw.get("full_costs")}
def reconcile_case(results):
 if not results:return {"board_type":"Unknown Board","confidence":0,"model":"SPIKE Multi-Photo Case Reasoner v0.6"}
 identity=verify_same_board(results)
 if identity.get("block_reconciliation"):
  return {"status":"case_identity_failed","board_type":"Multiple Boards / Case Split Required","grade":"UNRESOLVED","confidence":0,"score":0,"recommendation":"Do not combine these photos. Separate them into one case per physical board and analyze again.","same_board_verification":identity,"case_analysis":{"mode":"multi_photo_identity_blocked","views_analyzed":len(results),"message":"SPIKE stopped before classification because the case contains strong contradictory board evidence."},"recovery_economics":{"needs_values":True,"message":"Economics withheld because board-case identity failed."},"model":"Board Sense v2.9 + SPIKE Multi-Photo Case Reasoner v0.6 + Same-Board Verification Gate v0.1"}
 hard=[]
 for i,r in enumerate(results):
  s=strong_structural_family(r)
  if s:hard.append((i,r,s))
 if hard:_,winner,_=max(hard,key=lambda x:float(x[1].get("confidence",0) or 0))
 else:
  scores={};seen={}
  for r in results:
   label=r.get("board_type","Unknown Board");sig=_evidence_signature(r);base=max(.15,float(r.get("confidence",0) or 0)/100);repeat=seen.get(sig,0);weight=base if repeat==0 else base*(.35 if repeat==1 else .18);scores[label]=scores.get(label,0)+weight;seen[sig]=repeat+1
  label=max(scores,key=scores.get);winner=max((r for r in results if r.get("board_type")==label),key=lambda r:float(r.get("confidence",0) or 0))
 combined=deepcopy(winner);observations={};view_summaries=[];signatures={}
 for i,r in enumerate(results,1):
  mod=r.get("modification_intelligence") or {}
  for name,obs in (mod.get("observations") or {}).items():_merge_observation(observations,name,obs,i)
  sig=_evidence_signature(r);repeat=signatures.get(sig,0);signatures[sig]=repeat+1;view_summaries.append({"view":i,"role":_view_role(r),"board_type":r.get("board_type"),"confidence":r.get("confidence"),"grade":r.get("grade"),"modification_status":mod.get("status","not_evaluated"),"evidence_independence":"primary" if repeat==0 else "corroborating_repeat"})
 cs=combined.setdefault("signals",{})
 for key in ("processor","large_ic_chips","dense_component_board","gold_fingers","gold_finger_edge"):cs[key]=bool(cs.get(key) or any((r.get("signals") or {}).get(key) for r in results))
 condition=condition_harvest_check(combined,observations);combined["condition_and_harvest"]=condition;combined["equipment_subtype"]=infer_equipment_subtype(combined);combined=apply_recovery_grade_guard(combined);econ=_economics_inputs(combined);combined["recovery_economics"]=compare_paths(condition_factor=condition.get("remaining_value_factor",1.0),**econ);combined["recovery_economics"]["condition_link"]={"condition":condition.get("condition"),"remaining_value_factor":condition.get("remaining_value_factor"),"confirmed_losses":len(condition.get("confirmed_value_losses") or []),"remaining_opportunity":condition.get("remaining_recovery_opportunity"),"rule":"Confirmed harvesting may reduce intact-board sale value. Remaining material is valued separately; uncertain absence creates no deduction."}
 unique=len(signatures);combined["same_board_verification"]=identity;combined["case_analysis"]={"mode":"same_board_multi_photo","views_analyzed":len(results),"independent_evidence_patterns":unique,"view_summaries":view_summaries,"identity_gate":identity,"duplicate_evidence_guard":{"active":True,"rule":"Repeated equivalent views corroborate but do not multiply authority at full weight."},"condition_reconciliation":{"active":True,"rule":"A feature visible in one view defeats mere not-visible evidence in another. Only confirmed physical removal creates a deduction."},"message":"Case identity was checked before evidence reconciliation. Structural evidence outranks repeated weak hints; view diversity outranks photo count."};best=max(float(r.get("confidence",0) or 0) for r in results);combined["confidence"]=min(98,max(float(combined.get("confidence",0) or 0),best));combined["model"]="Board Sense v2.9 + SPIKE Multi-Photo Case Reasoner v0.6 + Same-Board Verification Gate v0.1 + Condition & Harvest v0.2 + Recovery Economics v0.2 + Verification v0.1";return combined
