"""SPIKE Multi-Photo Case Reasoner v0.13."""
from copy import deepcopy
from routes.decision_guard import strong_structural_family,condition_harvest_check
from routes.equipment_subtype import infer_equipment_subtype
from routes.recovery_grade_guard import apply_recovery_grade_guard
from routes.case_identity_gate import verify_same_board
from recovery_lab.core.time_value import compare_paths
LOSS={"removed","cut","harvested","missing_confirmed","clearly_cut","clearly_harvested"};PRESENT={"present","confirmed_present","visible","retained"};UNCERTAIN={"not_visible","uncertain","unknown","expected_not_visible","probably_removed"}
def _evidence_signature(r):
 s=r.get("signals") or {};mb=r.get("motherboard") or {};return(str(r.get("board_type","Unknown Board")),bool(s.get("ram") or s.get("possible_ram")),bool(s.get("processor")),bool(s.get("large_ic_chips")),bool(s.get("possible_power_board") or s.get("power_board")),bool(s.get("gold_fingers") or s.get("gold_finger_edge")),bool(s.get("possible_motherboard")),bool(s.get("confirmed_slot_bank") or mb.get("confirmed_slot_bank")),bool(mb.get("edge_connector_bank")))
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
def _cross_view_harvest(results,observations):
 flagged=[]
 for i,r in enumerate(results,1):
  mod=r.get("modification_intelligence") or {};obs=mod.get("observations") or {};sig=mod.get("signals") or []
  if "possible_removed_component" in obs or any(x.get("signal")=="possible_empty_ic_footprint" for x in sig if isinstance(x,dict)):flagged.append(i)
 corroborated=len(flagged)>=2
 if corroborated:observations["possible_removed_component"]={"status":"probably_removed","value_impact":"unknown","source":"cross_view","supporting_views":flagged,"note":"Two or more independent views contain removal-like empty component-footprint evidence. Board may be partially harvested; verify solder disturbance or known-populated reference before assigning confirmed value loss."}
 return {"model":"SPIKE Cross-View Harvest Corroborator v0.1","supporting_views":flagged,"corroborated":corroborated,"status":"probable_partial_harvest" if corroborated else("inspection_needed" if flagged else "no_cross_view_removal_signal"),"rule":"Independent views can strengthen a removal hypothesis. Probable removal is not confirmed monetary loss."}
def _economics_inputs(result):
 raw=result.get("economics_inputs") or result.get("recovery_economics_inputs") or {};return{"sell_whole_value":raw.get("sell_whole_value"),"partial_recovered_value":raw.get("partial_recovered_value"),"partial_residual_value":raw.get("partial_residual_value"),"partial_minutes":raw.get("partial_minutes"),"partial_costs":raw.get("partial_costs"),"full_recovery_value":raw.get("full_recovery_value"),"full_minutes":raw.get("full_minutes"),"full_costs":raw.get("full_costs")}
def _three_answers(result,identity,condition,economics):
 subtype=result.get("equipment_subtype") or {};guard=result.get("recovery_grade_guard") or {};return{"identity":{"question":"What is it?","answer":result.get("board_type","Unknown Board"),"subtype":subtype.get("subtype") or subtype.get("type"),"confidence":result.get("confidence",0),"case_identity_status":identity.get("status")},"recovery":{"question":"What recovery value is physically supported?","grade":result.get("grade","UNRESOLVED"),"score":result.get("score",0),"pay_dirt_ready":bool(result.get("pay_dirt_ready",False)),"condition":condition.get("condition"),"remaining_opportunity":condition.get("remaining_recovery_opportunity"),"grade_guard":guard.get("model")},"economics":{"question":"What should we do with it?","winner":economics.get("winner"),"needs_values":bool(economics.get("needs_values",False)),"message":economics.get("message")},"separation_rule":"Identity, recovery grade, and economics are independent answers."}
def _mixed_power_control_case(results):
 """Cross-view structural vote for boards carrying both power-stage and control logic.

 A case may show the transformer/capacitor stage clearly in one photograph and
 the controller/IC population in another. Those observations describe one
 physical topology after the identity gate passes and should outrank an isolated
 gold-coloured edge hint.
 """
 power_views=[];logic_views=[];edge_views=[];max_power=0
 for i,r in enumerate(results,1):
  s=r.get("signals") or {};p=r.get("power") or {};label=str(r.get("board_type","")).lower()
  ps=max(int(s.get("power_score",0) or 0),int(p.get("power_score",0) or 0));max_power=max(max_power,ps)
  blocks=max(int(s.get("large_component_regions",0) or 0),int(p.get("large_component_regions",0) or 0));rounds=max(int(s.get("large_round_components",0) or 0),int(p.get("large_round_components",0) or 0))
  if (blocks>=1 and (ps>=3 or rounds>=2 or blocks>=2)) or "power-control" in label:power_views.append(i)
  if s.get("processor") or s.get("large_ic_chips") or s.get("dense_component_board") or any(x in label for x in ("logic","controller","power-control")):logic_views.append(i)
  if s.get("gold_fingers") or s.get("gold_finger_edge") or "edge-connector" in label:edge_views.append(i)
 supported=bool(power_views and logic_views)
 return {"supported":supported,"power_views":power_views,"logic_views":logic_views,"edge_signal_views":edge_views,"max_power_score":max_power,"rule":"After same-board verification, substantial power-stage evidence plus control/logic evidence outranks an isolated edge/gold-colour identity hint."}
def reconcile_case(results):
 if not results:return{"board_type":"Unknown Board","confidence":0,"model":"SPIKE Multi-Photo Case Reasoner v0.13"}
 identity=verify_same_board(results)
 if identity.get("block_reconciliation"):return{"status":"case_identity_failed","board_type":"Multiple Boards / Case Split Required","grade":"UNRESOLVED","confidence":0,"score":0,"recommendation":"Do not combine these photos. Separate them into one case per physical board and analyze again.","same_board_verification":identity,"three_answers":{"identity":{"question":"What is it?","answer":"Multiple Boards / Case Split Required","case_identity_status":identity.get("status")},"recovery":{"question":"What recovery value is physically supported?","grade":"WITHHELD"},"economics":{"question":"What should we do with it?","winner":None}},"model":"Board Sense v3.6 + SPIKE Multi-Photo Case Reasoner v0.13 + Same-Board Verification Gate v0.6"}
 hard=[]
 for i,r in enumerate(results):
  s=strong_structural_family(r)
  if s:hard.append((i,r,s))
 mixed=_mixed_power_control_case(results)
 if hard:_,winner,_=max(hard,key=lambda x:float(x[1].get("confidence",0) or 0))
 else:
  scores={};seen={}
  for r in results:
   label=r.get("board_type","Unknown Board");sig=_evidence_signature(r);base=max(.15,float(r.get("confidence",0) or 0)/100);repeat=seen.get(sig,0);weight=base if repeat==0 else base*(.35 if repeat==1 else .18);scores[label]=scores.get(label,0)+weight;seen[sig]=repeat+1
  label=max(scores,key=scores.get);winner=max((r for r in results if r.get("board_type")==label),key=lambda r:float(r.get("confidence",0) or 0))
 combined=deepcopy(winner);observations={};view_summaries=[];signatures={}
 for i,r in enumerate(results,1):
  mod=r.get("modification_intelligence") or {}
  for name,obs in(mod.get("observations") or {}).items():_merge_observation(observations,name,obs,i)
  sig=_evidence_signature(r);repeat=signatures.get(sig,0);signatures[sig]=repeat+1;mb=r.get("motherboard") or {};view_summaries.append({"view":i,"role":_view_role(r),"board_type":r.get("board_type"),"confidence":r.get("confidence"),"grade":r.get("grade"),"confirmed_slot_bank":bool((r.get("signals") or {}).get("confirmed_slot_bank") or mb.get("confirmed_slot_bank")),"edge_connector_bank":bool(mb.get("edge_connector_bank")),"modification_status":mod.get("status","not_evaluated"),"evidence_independence":"primary" if repeat==0 else "corroborating_repeat"})
 cross=_cross_view_harvest(results,observations);cs=combined.setdefault("signals",{})
 for key in("processor","large_ic_chips","dense_component_board","gold_fingers","gold_finger_edge","possible_power_board","power_board"):cs[key]=bool(cs.get(key) or any((r.get("signals") or {}).get(key) for r in results))
 cs["power_score"]=max([int((r.get("signals") or {}).get("power_score",0) or 0) for r in results]+[int(cs.get("power_score",0) or 0)])
 # Cross-view topology is allowed only after the same-board gate has accepted the
 # case. It changes identity, never recovery grade or metal assay conclusions.
 if mixed["supported"] and not hard:
  combined["board_type"]="Power-Control / Controller Board"
  combined["board_type_reason"]="Across verified same-board views, substantial power-stage hardware and control/logic evidence are both present. This structural topology outranks isolated edge-connector or gold-colour hints."
  cs["mixed_power_control_topology"]=True
 condition=condition_harvest_check(combined,observations);combined["condition_and_harvest"]=condition;combined["cross_view_harvest"]=cross;combined["equipment_subtype"]=infer_equipment_subtype(combined);combined=apply_recovery_grade_guard(combined);econ=_economics_inputs(combined);combined["recovery_economics"]=compare_paths(condition_factor=condition.get("remaining_value_factor",1.0),**econ);combined["same_board_verification"]=identity;combined["case_analysis"]={"mode":"same_board_multi_photo","views_analyzed":len(results),"independent_evidence_patterns":len(signatures),"view_summaries":view_summaries,"identity_gate":identity,"cross_view_harvest":cross,"mixed_power_control_evidence":mixed,"duplicate_evidence_guard":{"active":True,"rule":"Repeated equivalent views corroborate but do not multiply authority at full weight."},"message":"Case identity is checked before evidence reconciliation. Strong mixed power and logic topology can outrank weak edge-connector hints, while recovery value remains independently graded."}
 best=max(float(r.get("confidence",0) or 0) for r in results);combined["confidence"]=min(98,max(float(combined.get("confidence",0) or 0),best))
 if identity.get("status")=="IDENTITY_UNCERTAIN":combined["confidence"]=min(combined["confidence"],65);combined["recommendation"]=identity.get("identity_next_step") or "Add a clear full-board photo."
 combined["three_answers"]=_three_answers(combined,identity,condition,combined["recovery_economics"]);combined["model"]="Board Sense v3.6 + SPIKE Multi-Photo Case Reasoner v0.13 + Same-Board Verification Gate v0.6 + Physical Fingerprint v0.3 + Cross-View Harvest Corroborator v0.1 + Decision Guard v0.3 + Equipment Subtype v0.3 + Recovery Grade Guard v0.3 + Condition & Harvest v0.2 + Recovery Economics v0.2";return combined
