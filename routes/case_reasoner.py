"""SPIKE Multi-Photo Case Reasoner v0.17."""
from copy import deepcopy
from routes.decision_guard import strong_structural_family,condition_harvest_check
from routes.equipment_subtype import infer_equipment_subtype
from routes.recovery_grade_guard import apply_recovery_grade_guard
from routes.case_identity_gate import verify_same_board
from recovery_lab.core.time_value import compare_paths
LOSS={"removed","cut","harvested","missing_confirmed","clearly_cut","clearly_harvested"};PRESENT={"present","confirmed_present","visible","retained"};UNCERTAIN={"not_visible","uncertain","unknown","expected_not_visible","probably_removed"}
def _edge_geometry_confirmed(r):
 s=r.get("signals") or {};v=r.get("visual") or {};ri=r.get("reference_intelligence") or {};return bool(s.get("gold_finger_geometry") or s.get("repeated_edge_contacts") or v.get("gold_finger_geometry") or v.get("repeated_edge_contacts") or ri.get("gold_finger_geometry_confirmed"))
def _evidence_signature(r):
 s=r.get("signals") or {};mb=r.get("motherboard") or {};return(str(r.get("board_type","Unknown Board")),bool(s.get("ram") or s.get("possible_ram")),bool(s.get("processor")),bool(s.get("large_ic_chips")),bool(s.get("possible_power_board") or s.get("power_board") or s.get("power_stage_present")),_edge_geometry_confirmed(r),bool(s.get("possible_motherboard")),bool(s.get("confirmed_slot_bank") or mb.get("confirmed_slot_bank")),bool(mb.get("edge_connector_bank")))
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
 power_views=[];logic_views=[];edge_views=[];raw_edge_views=[];candidate_views=[];package_views=[];max_power=0;max_raw_power=0;max_blocks=0;max_rounds=0;max_packages=0
 for i,r in enumerate(results,1):
  s=r.get("signals") or {};p=r.get("power") or {};label=str(r.get("board_type","")).lower();ps=max(int(s.get("power_score",0) or 0),int(p.get("power_score",0) or 0));raw_ps=max(int(s.get("raw_power_score",0) or 0),int(p.get("raw_power_score",0) or 0),ps);blocks=max(int(s.get("large_component_regions",0) or 0),int(p.get("large_component_regions",0) or 0));rounds=max(int(s.get("large_round_components",0) or 0),int(p.get("large_round_components",0) or 0));packages=max(int(s.get("large_power_package_like",0) or 0),int(p.get("large_power_package_like",0) or 0));stage=bool(s.get("power_stage_present") or p.get("power_stage_present"));mixed_candidate=bool(s.get("mixed_power_control_candidate") or p.get("mixed_power_control_candidate"));max_power=max(max_power,ps);max_raw_power=max(max_raw_power,raw_ps);max_blocks=max(max_blocks,blocks);max_rounds=max(max_rounds,rounds);max_packages=max(max_packages,packages)
  if stage or mixed_candidate or (blocks>=1 and(raw_ps>=3 or rounds>=2 or blocks>=2)) or(packages>=1 and rounds>=2 and raw_ps>=3) or "power-control" in label:power_views.append(i)
  if mixed_candidate:candidate_views.append(i)
  if packages:package_views.append(i)
  if s.get("processor") or s.get("large_ic_chips") or s.get("dense_component_board") or any(x in label for x in("logic","controller","power-control")):logic_views.append(i)
  if s.get("gold_edge_color_cue") or "edge-connector" in label:raw_edge_views.append(i)
  if _edge_geometry_confirmed(r):edge_views.append(i)
 supported=bool(candidate_views or(power_views and logic_views))
 return {"supported":supported,"power_views":power_views,"logic_views":logic_views,"mixed_candidate_views":candidate_views,"large_power_package_views":package_views,"edge_geometry_views":edge_views,"raw_edge_color_views":raw_edge_views,"max_power_score":max_power,"max_raw_power_score":max_raw_power,"max_power_blocks":max_blocks,"max_large_round_components":max_rounds,"max_large_power_package_like":max_packages,"rule":"After same-board verification, raw physical power-stage evidence survives logic penalties. Unconfirmed edge color cannot participate in identity voting; actual edge-contact geometry is required."}
def reconcile_case(results):
 if not results:return{"board_type":"Unknown Board","confidence":0,"model":"SPIKE Multi-Photo Case Reasoner v0.17"}
 identity=verify_same_board(results)
 if identity.get("block_reconciliation"):return{"status":"case_identity_failed","board_type":"Multiple Boards / Case Split Required","grade":"UNRESOLVED","confidence":0,"score":0,"recommendation":"Do not combine these photos. Separate them into one case per physical board and analyze again.","same_board_verification":identity,"three_answers":{"identity":{"question":"What is it?","answer":"Multiple Boards / Case Split Required","case_identity_status":identity.get("status")},"recovery":{"question":"What recovery value is physically supported?","grade":"WITHHELD"},"economics":{"question":"What should we do with it?","winner":None}},"model":"Board Sense v4.1 + SPIKE Multi-Photo Case Reasoner v0.17 + Same-Board Verification Gate v0.6"}
 hard=[]
 for i,r in enumerate(results):
  s=strong_structural_family(r)
  if s:hard.append((i,r,s))
 mixed=_mixed_power_control_case(results);suppressed_edge_votes=[]
 if hard:_,winner,_=max(hard,key=lambda x:float(x[1].get("confidence",0) or 0))
 else:
  scores={};seen={}
  for i,r in enumerate(results,1):
   label=r.get("board_type","Unknown Board");low=label.lower()
   if any(x in low for x in("edge-connector","gold finger","expansion")) and not _edge_geometry_confirmed(r):suppressed_edge_votes.append(i);continue
   sig=_evidence_signature(r);base=max(.15,float(r.get("confidence",0) or 0)/100);repeat=seen.get(sig,0);weight=base if repeat==0 else base*(.35 if repeat==1 else .18);scores[label]=scores.get(label,0)+weight;seen[sig]=repeat+1
  if scores:
   label=max(scores,key=scores.get);winner=max((r for r in results if r.get("board_type")==label),key=lambda r:float(r.get("confidence",0) or 0))
  else:
   logic_candidates=[r for r in results if (r.get("signals") or {}).get("dense_component_board") or (r.get("signals") or {}).get("large_ic_chips")]
   winner=deepcopy(max(logic_candidates or results,key=lambda r:float(r.get("confidence",0) or 0)))
   if suppressed_edge_votes and not logic_candidates:winner["board_type"]="General PCB";winner["board_type_reason"]="Edge-colour cues were present, but repeated contact geometry was not confirmed, so SPIKE withheld an expansion-card identity."
 combined=deepcopy(winner);observations={};view_summaries=[];signatures={}
 for i,r in enumerate(results,1):
  mod=r.get("modification_intelligence") or {}
  for name,obs in(mod.get("observations") or {}).items():_merge_observation(observations,name,obs,i)
  sig=_evidence_signature(r);repeat=signatures.get(sig,0);signatures[sig]=repeat+1;mb=r.get("motherboard") or {};s=r.get("signals") or {};view_summaries.append({"view":i,"role":_view_role(r),"board_type":r.get("board_type"),"confidence":r.get("confidence"),"grade":r.get("grade"),"power_stage_present":bool(s.get("power_stage_present")),"mixed_power_control_candidate":bool(s.get("mixed_power_control_candidate")),"large_power_package_like":int(s.get("large_power_package_like",0) or 0),"raw_power_score":int(s.get("raw_power_score",0) or 0),"edge_color_cue":bool(s.get("gold_edge_color_cue")),"edge_geometry_confirmed":_edge_geometry_confirmed(r),"confirmed_slot_bank":bool(s.get("confirmed_slot_bank") or mb.get("confirmed_slot_bank")),"edge_connector_bank":bool(mb.get("edge_connector_bank")),"modification_status":mod.get("status","not_evaluated"),"evidence_independence":"primary" if repeat==0 else "corroborating_repeat"})
 cross=_cross_view_harvest(results,observations);cs=combined.setdefault("signals",{});cp=combined.setdefault("power",{})
 for key in("processor","large_ic_chips","dense_component_board","possible_power_board","power_board","power_stage_present","mixed_power_control_candidate"):cs[key]=bool(cs.get(key) or any((r.get("signals") or {}).get(key) for r in results))
 confirmed_edge=any(_edge_geometry_confirmed(r) for r in results);cs["gold_fingers"]=confirmed_edge;cs["gold_finger_edge"]=confirmed_edge;cs["gold_finger_geometry"]=confirmed_edge;cs["repeated_edge_contacts"]=confirmed_edge;cs["gold_edge_color_cue"]=any((r.get("signals") or {}).get("gold_edge_color_cue") for r in results)
 cs["power_score"]=max([int((r.get("signals") or {}).get("power_score",0) or 0) for r in results]+[int(cs.get("power_score",0) or 0),mixed["max_power_score"]]);cs["raw_power_score"]=max([int((r.get("signals") or {}).get("raw_power_score",0) or 0) for r in results]+[int(cs.get("raw_power_score",0) or 0),mixed["max_raw_power_score"]]);cs["large_power_package_like"]=max([int((r.get("signals") or {}).get("large_power_package_like",0) or 0) for r in results]+[int(cs.get("large_power_package_like",0) or 0),mixed["max_large_power_package_like"]])
 if mixed["supported"] and not hard:
  combined["board_type"]="Power-Control / Controller Board";combined["board_type_reason"]="Across verified same-board views, raw physical power-stage evidence and control/logic evidence are both present. Logic penalties may reject a pure PSU label, but they do not erase the observed power stage.";cs["mixed_power_control_topology"]=True;cs["power_stage_present"]=True;cs["mixed_power_control_candidate"]=True;cs["possible_power_board"]=True;cs["power_board"]=True
  cp["possible_power_board"]=True;cp["power_stage_present"]=True;cp["mixed_power_control_candidate"]=True;cp["power_score"]=max(int(cp.get("power_score",0) or 0),mixed["max_power_score"]);cp["raw_power_score"]=max(int(cp.get("raw_power_score",0) or 0),mixed["max_raw_power_score"]);cp["large_component_regions"]=max(int(cp.get("large_component_regions",0) or 0),mixed["max_power_blocks"]);cp["large_round_components"]=max(int(cp.get("large_round_components",0) or 0),mixed["max_large_round_components"]);cp["large_power_package_like"]=max(int(cp.get("large_power_package_like",0) or 0),mixed["max_large_power_package_like"]);cp["case_reconciled_power_topology"]=True
 condition=condition_harvest_check(combined,observations);combined["condition_and_harvest"]=condition;combined["cross_view_harvest"]=cross;combined["equipment_subtype"]=infer_equipment_subtype(combined);combined=apply_recovery_grade_guard(combined);econ=_economics_inputs(combined);combined["recovery_economics"]=compare_paths(condition_factor=condition.get("remaining_value_factor",1.0),**econ);combined["same_board_verification"]=identity;combined["case_analysis"]={"mode":"same_board_multi_photo","views_analyzed":len(results),"independent_evidence_patterns":len(signatures),"view_summaries":view_summaries,"identity_gate":identity,"cross_view_harvest":cross,"mixed_power_control_evidence":mixed,"suppressed_unconfirmed_edge_votes":suppressed_edge_votes,"edge_identity_guard":{"active":True,"rule":"Gold-like color near an image edge is an inspection cue only. Expansion/gold-finger identity requires repeated edge-contact geometry."},"duplicate_evidence_guard":{"active":True,"rule":"Repeated equivalent views corroborate but do not multiply authority at full weight."},"message":"Case identity is checked before evidence reconciliation. Raw physical power-stage evidence is preserved separately from pure-PSU logic penalties; unconfirmed edge color is barred from identity voting; recovery value remains independently graded."}
 best=max(float(r.get("confidence",0) or 0) for r in results);combined["confidence"]=min(98,max(float(combined.get("confidence",0) or 0),best))
 if identity.get("status")=="IDENTITY_UNCERTAIN":combined["confidence"]=min(combined["confidence"],65);combined["recommendation"]=identity.get("identity_next_step") or "Add a clear full-board photo."
 combined["three_answers"]=_three_answers(combined,identity,condition,combined["recovery_economics"]);combined["model"]="Board Sense v4.1 + SPIKE Multi-Photo Case Reasoner v0.17 + Same-Board Verification Gate v0.6 + Physical Fingerprint v0.3 + SPIKE Vision v0.8 + Edge Contact Geometry v0.1 + Power Topology v0.3 + Motherboard Detector v0.3 + Cross-View Harvest Corroborator v0.1 + Decision Guard v0.3 + Equipment Subtype v0.3 + Recovery Grade Guard v0.3 + Condition & Harvest v0.2 + Recovery Economics v0.2";return combined
