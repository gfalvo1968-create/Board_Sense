"""Board Sense reference knowledge reasoner, SPIKE weighted evidence v5."""
from routes.reference_loader import get_knowledge

def _compact_match(item,reason):return {"category":item.get("category","Unknown"),"grade":item.get("grade","UNKNOWN"),"value_rank":item.get("value_rank",0),"reason":reason,"material_signals":item.get("material_signals",[]),"sorting_advice":item.get("sorting_advice",""),"notes":item.get("notes","")}
def _add(h,n,p,r):
 x=h.setdefault(n,{"score":0,"evidence":[],"against":[]});x["score"]+=p;(x["evidence"] if p>=0 else x["against"]).append(r)
def _normalize(h):
 out=[]
 for n,d in h.items():
  raw=d["score"];conf=max(20,min(94,int(round(38+raw*4.2))));out.append({"type":n,"evidence_score":raw,"hypothesis_confidence":conf,"evidence":d["evidence"],"against":d["against"]})
 out.sort(key=lambda x:x["evidence_score"],reverse=True)
 if len(out)>1:
  m=out[0]["evidence_score"]-out[1]["evidence_score"]
  if m<=2:out[0]["hypothesis_confidence"]=min(out[0]["hypothesis_confidence"],72)
  elif m<=4:out[0]["hypothesis_confidence"]=min(out[0]["hypothesis_confidence"],80)
 return out
def build_reference_matches(features,visual,motherboard,power,board_type):
 knowledge=get_knowledge();matches=[];h={};raw_gold=bool(features.get("gold_fingers") or visual.get("gold_finger_edge") or visual.get("gold_edge_color_cue"));contact_count=int(visual.get("gold_contact_count",0) or 0);contact_side=visual.get("gold_contact_side");spacing_cv=visual.get("gold_contact_spacing_cv");size_cv=visual.get("gold_contact_size_cv");finger_geometry=bool(visual.get("gold_finger_geometry") and visual.get("repeated_edge_contacts") and contact_count>=5 and contact_side and spacing_cv is not None and size_cv is not None and float(spacing_cv)<=.55 and float(size_cv)<=.45);gold=bool(features.get("gold_fingers") and finger_geometry)
 ram=bool(features.get("ram") or features.get("memory_module") or visual.get("possible_ram"));dense=bool(features.get("dense_component_board"));large_ics=bool(features.get("large_ic_chips") or visual.get("possible_large_ic_chips"));processor=bool(features.get("processor"));mobo=bool(features.get("motherboard") or motherboard.get("possible_motherboard"));large_board=bool(motherboard.get("large_board"));structure=int(motherboard.get("motherboard_structure_score",0) or 0);slots=int(motherboard.get("long_slot_candidates",0) or 0);edge_bank=bool(motherboard.get("edge_connector_bank"));power_like=bool(features.get("power_board") or features.get("possible_power_board") or power.get("possible_power_board") or power.get("power_stage_present"));power_score=max(int(features.get("power_score",0) or 0),int(power.get("power_score",0) or 0),int(power.get("raw_power_score",0) or 0));large_round=int(power.get("large_round_components",0) or 0);large_regions=int(power.get("large_component_regions",0) or 0);component_count=int(features.get("component_count",0) or 0);aspect=float(visual.get("aspect_ratio",0) or 0);logic=bool(processor or large_ics or dense);mixed_power_control=bool(logic and power_like and structure<6)
 if ram:_add(h,"RAM / Memory Module",4,"Memory-module geometry detector fired")
 if aspect>=2.8:_add(h,"RAM / Memory Module",2,f"Long narrow aspect ratio ({aspect:.2f}:1)")
 if gold:_add(h,"Expansion / Gold Finger Card",6,"Strict repeated edge-contact geometry confirmed")
 elif raw_gold:_add(h,"Expansion / Gold Finger Card",1,"Gold-colored edge cue only; strict finger geometry not confirmed")
 if dense:_add(h,"Motherboard / Logic Board",2,"Dense logic population");_add(h,"Mixed Consumer Control Board",2,"Dense mixed control circuitry")
 if large_ics:_add(h,"Motherboard / Logic Board",2,"Large IC packages support logic architecture");_add(h,"Mixed Consumer Control Board",1,"Large IC packages support control logic")
 if processor:_add(h,"Motherboard / Logic Board",5,"Processor-like region supports main logic board")
 if large_board:_add(h,"Motherboard / Logic Board",1,"Large board geometry");_add(h,"Server / Enterprise Board",1,"Large board size")
 if structure>=6:
  _add(h,"Motherboard / Logic Board",8,f"Strong motherboard structural score {structure}")
  if slots>=2:_add(h,"Motherboard / Logic Board",5,f"{slots} repeated long DIMM/expansion-slot-like structures")
  if edge_bank:_add(h,"Motherboard / Logic Board",4,"Dense rear-I/O/connector-style edge bank")
  _add(h,"Mixed Consumer Control Board",-3,"PC-style slot/socket architecture argues against generic control board")
 if power_like:
  _add(h,"Power / Supply Board",5,"Power detector found substantial power-handling topology")
  if structure<6:_add(h,"Mixed Consumer Control Board",3,"Power handling plus control circuitry")
  if structure>=6:_add(h,"Power / Supply Board",-5,"Motherboard-specific architecture outweighs generic power circuitry")
 if mixed_power_control:
  _add(h,"Power-Control / Controller Board",5,"Substantial power topology and control/logic evidence coexist")
  if power_score>=5:_add(h,"Power-Control / Controller Board",2,f"Strong power topology score {power_score}")
  if large_ics or processor:_add(h,"Power-Control / Controller Board",2,"Controller/large-IC evidence accompanies the power stage")
  _add(h,"Power / Supply Board",-2,"Control logic argues against a pure supply")
  if not gold:_add(h,"Expansion / Gold Finger Card",-2,"No strict edge-finger geometry proof")
 if large_round>=2:_add(h,"Power / Supply Board",1,f"{large_round} round power-component candidates")
 if large_regions>=1:_add(h,"Power / Supply Board",2,f"{large_regions} substantial power-block regions")
 if component_count>=8:_add(h,"Mixed Consumer Control Board",2,f"High populated-component count ({component_count})")
 if gold:
  for item in knowledge.get("gold_fingers",[]):
   if item.get("category") in ("High Quality Gold Finger Card","Full Gold Fingers"):matches.append(_compact_match(item,"Strict repeated rectangular edge contacts confirmed"));break
 if large_ics or processor:
  for item in knowledge.get("ic_chips",[]):
   target="BGA Chip" if processor else "Plastic IC Chip"
   if item.get("category")==target:matches.append(_compact_match(item,"Logic-package evidence detected"));break
 motherboard_specific=bool(structure>=6 or (mobo and(processor or(dense and component_count>=8 and not power_like))))
 if motherboard_specific:
  target="High Grade Motherboard" if dense and gold else "Medium Grade Motherboard"
  for item in knowledge.get("motherboards",[]):
   if item.get("category")==target:matches.append(_compact_match(item,"Motherboard-scale geometry plus PC-style structural evidence detected"));break
 ranked=_normalize(h);top=ranked[0] if ranked else None;runner=ranked[1] if len(ranked)>1 else None;margin=(top["evidence_score"]-runner["evidence_score"]) if top and runner else(top["evidence_score"] if top else 0);return {"matches":matches,"match_count":len(matches),"hypotheses":ranked[:5],"top_hypothesis":top,"hypothesis_margin":margin,"telecom_pattern":False,"board_type_context":board_type.get("type","General PCB"),"gold_finger_geometry_confirmed":gold,"gold_finger_proof":{"contact_count":contact_count,"side":contact_side,"spacing_cv":spacing_cv,"size_cv":size_cv},"motherboard_structure_score":structure,"mixed_power_control_supported":mixed_power_control,"reasoning_version":"SPIKE-weighted-evidence-v5"}
