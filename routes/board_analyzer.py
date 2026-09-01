from pathlib import Path
from routes.board_features import detect_board_features
from routes.board_visual import detect_visual_features
from routes.board_scoring import calculate_score
from routes.board_motherboard import detect_motherboard
from routes.board_power import detect_power_board
from routes.board_type import classify_board_type
from routes.board_confidence import calculate_confidence
from routes.board_insight import BoardInsight
from routes.reference_loader import get_knowledge
from routes.reference_reasoner import build_reference_matches
from routes.component_discriminator import discriminate_components
from routes.spike_glass import recognize as spike_glass_recognize
from routes.photo_quality import assess_photo_quality
from routes.board_blueprint import generate_blueprint
from routes.object_gate import classify_object
from routes.modification_detector import detect_modifications
from routes.decision_guard import condition_harvest_check
from routes.board_fingerprint import extract_board_fingerprint
from recovery_lab.core.recovery_engine import build_recovery_plan

def _grade_from_reference(score):
 rules=get_knowledge().get("board_grade",[])
 for rule in rules:
  score_range=rule.get("score_range",[])
  if len(score_range)!=2:continue
  low,high=score_range
  if low<=score<=high:return {"grade":rule.get("grade","UNKNOWN"),"recommendation":rule.get("recommended_action","Manual review recommended."),"pay_dirt_ready":bool(rule.get("pay_dirt_ready",False)),"recovery_signals":rule.get("recovery_signals",[]),"grade_notes":rule.get("notes","")}
 if score>=22:return {"grade":"VERY HIGH","recommendation":"Separate immediately and store securely.","pay_dirt_ready":True,"recovery_signals":["high precious metal potential"],"grade_notes":"Premium recovery candidate."}
 if score>=16:return {"grade":"HIGH","recommendation":"Separate from mixed board loads.","pay_dirt_ready":True,"recovery_signals":["moderate to high precious metal recovery"],"grade_notes":"Strong recovery potential."}
 if score>=9:return {"grade":"MEDIUM","recommendation":"Sort into medium-grade categories.","pay_dirt_ready":False,"recovery_signals":["moderate recovery value"],"grade_notes":"Average recovery category."}
 return {"grade":"LOW","recommendation":"Recover copper, aluminum, transformers, or bulk shred value.","pay_dirt_ready":False,"recovery_signals":["limited precious metal recovery"],"grade_notes":"Low-value or mixed recovery material."}
def _agreement(simple_type,top_hypothesis):
 if not top_hypothesis:return {"status":"insufficient_evidence","message":"Weighted reasoner did not produce a strong competing hypothesis."}
 weighted_type=top_hypothesis.get("type","Unknown");sl,wl=simple_type.lower(),weighted_type.lower();groups=[("ram","memory"),("power","supply","controller"),("motherboard","logic"),("telecom","network"),("expansion","gold finger"),("processor",),("server","enterprise")];agrees=any(any(word in sl for word in g) and any(word in wl for word in g) for g in groups);return {"status":"agree" if agrees else "review","simple_classifier":simple_type,"weighted_hypothesis":weighted_type,"weighted_confidence":top_hypothesis.get("hypothesis_confidence",0),"message":"Independent classifiers agree on the same broad board family." if agrees else "Independent classifiers disagree; keep the result conservative and review the evidence."}
def _non_board_result(object_gate,photo_quality,fingerprint):
 mode=object_gate.get("mode","unknown");label=object_gate.get("label","Unknown object");confidence=int(object_gate.get("confidence",35));recommendation="Keep the item intact, identify the component family, and accumulate similar modules before assigning recovery value." if mode=="component" else "Retake the photo or use Spike Glass for a closer component view before assigning a board grade.";reason=object_gate.get("message","Component mode selected." if mode=="component" else "Object could not be classified safely.")
 return {"grade":"N/A","confidence":confidence,"score":0,"board_type":label,"board_type_reason":reason,"object_gate":object_gate,"physical_fingerprint":fingerprint,"reasoning_crosscheck":{"status":"not_board" if mode=="component" else "insufficient_evidence","message":"Object Gate stopped the board classifiers because this image does not have enough evidence to be treated as a whole PCB."},"photo_quality":photo_quality,"spike_glass":{"status":"object_gate","confidence":confidence,"top_match":{"label":label,"evidence":object_gate.get("evidence",[]),"action":recommendation}},"board_blueprint":{"available":False,"message":"Board Blueprint is reserved for confirmed whole-board scans. Use component mode for this item.","component_index":[]},"pay_dirt_ready":False,"recommendation":recommendation,"recovery_signals":["component-level inspection recommended" if mode=="component" else "insufficient board evidence"],"grade_notes":"Whole-board grading intentionally skipped by Object Gate.","reference_intelligence":{"matches":[],"hypotheses":[],"top_hypothesis":None},"component_intelligence":{},"features":{},"visual":{},"power":{},"signals":{},"recovery_lab":{"labs":[],"risk":{"level":"unclassified"},"economics":{},"decision_options":["IDENTIFY COMPONENT","ACCUMULATE SIMILAR ITEMS","MANUAL REVIEW"],"note":"Board-specific recovery routing is disabled until the object is confirmed as a whole PCB."},"insight":{"summary":reason,"recommendation":recommendation},"model":"Board Sense v3.8 + SPIKE Verification + Physical Fingerprint v0.3"}
def analyze_board(image_path):
 photo_quality=assess_photo_quality(image_path);fingerprint=extract_board_fingerprint(image_path);object_gate=classify_object(image_path)
 if object_gate.get("mode")!="board":return _non_board_result(object_gate,photo_quality,fingerprint)
 features=detect_board_features(image_path);visual=detect_visual_features(image_path);motherboard=detect_motherboard(image_path);power=detect_power_board(image_path);components=discriminate_components(image_path)
 if visual.get("possible_ram",False):features["ram"]=True;features["memory_module"]=True
 if visual.get("gold_finger_edge",False):features["gold_fingers"]=True
 if motherboard.get("possible_motherboard",False):features["motherboard"]=True
 if power.get("possible_power_board",False):features["power_board"]=True
 visual_ic_signal=visual.get("possible_large_ic_chips",False);component_ic_support=components.get("ic_like",0)>=2 and components.get("dominant_family")!="power_components";features["large_ic_chips"]=bool(visual_ic_signal and component_ic_support)
 if components.get("dominant_family")=="power_components":features["power_board"]=True
 board_type=classify_board_type(features,visual,motherboard,power);score=calculate_score(features);grade_result=_grade_from_reference(score);reference_intelligence=build_reference_matches(features,visual,motherboard,power,board_type);reasoning_crosscheck=_agreement(board_type["type"],reference_intelligence.get("top_hypothesis"));spike_glass=spike_glass_recognize(features,visual,motherboard,power,components,reference_intelligence)
 if not photo_quality.get("usable",False):spike_glass["status"]="retake_recommended";spike_glass["confidence"]=min(int(spike_glass.get("confidence",0)),45);spike_glass["photo_warning"]="Recognition confidence capped because the photo quality gate recommends a retake."
 confidence=calculate_confidence(score,features=features,visual=visual,motherboard=motherboard,power=power)
 if reasoning_crosscheck["status"]=="review":confidence=max(25,confidence-10)
 if visual_ic_signal and not component_ic_support:confidence=max(25,confidence-5)
 if not photo_quality.get("usable",False):confidence=max(20,min(confidence,50))
 blueprint_dir=Path(image_path).resolve().parent.parent/"Blueprints";blueprint=generate_blueprint(image_path,components.get("regions",[]),blueprint_dir)
 if blueprint.get("available"):blueprint["image_url"]="/blueprints/"+blueprint["image_filename"]
 result={"grade":grade_result["grade"],"confidence":confidence,"score":score,"board_type":board_type["type"],"board_type_reason":board_type["reason"],"object_gate":object_gate,"physical_fingerprint":fingerprint,"reasoning_crosscheck":reasoning_crosscheck,"photo_quality":photo_quality,"spike_glass":spike_glass,"board_blueprint":blueprint,"pay_dirt_ready":grade_result["pay_dirt_ready"],"recommendation":grade_result["recommendation"],"recovery_signals":grade_result["recovery_signals"],"grade_notes":grade_result["grade_notes"],"reference_intelligence":reference_intelligence,"component_intelligence":components,"features":features,"visual":visual,"motherboard":motherboard,"power":power,"signals":{"motherboard":features.get("motherboard",False),"ram":features.get("ram",False),"power_board":features.get("power_board",False),"gold_fingers":features.get("gold_fingers",False),"large_ic_chips":features.get("large_ic_chips",False),"dense_component_board":features.get("dense_component_board",False),"processor":features.get("processor",False),"component_count":features.get("component_count",0),"component_density":features.get("component_density",0.0),"possible_ram":visual.get("possible_ram",False),"gold_finger_edge":visual.get("gold_finger_edge",False),"raw_large_ic_signal":visual_ic_signal,"ic_signal_confirmed":component_ic_support,"possible_motherboard":motherboard.get("possible_motherboard",False),"confirmed_slot_bank":motherboard.get("confirmed_slot_bank",False),"parallel_slot_bank":motherboard.get("parallel_slot_bank",False),"motherboard_score":motherboard.get("motherboard_score",motherboard.get("score",0)),"large_board":motherboard.get("large_board",False),"possible_power_board":power.get("possible_power_board",False),"power_stage_present":power.get("power_stage_present",False),"mixed_power_control_candidate":power.get("mixed_power_control_candidate",False),"large_round_components":power.get("large_round_components",0),"large_component_regions":power.get("large_component_regions",0),"power_score":power.get("power_score",0),"raw_power_score":power.get("raw_power_score",0),"logic_penalty":power.get("logic_penalty",0)},"model":"Board Sense v3.8 + SPIKE Vision v0.7 + Spike Glass v0.6 + Power Topology v0.2 + Modification Detector v0.2 + Motherboard Detector v0.2 + Physical Fingerprint v0.3"}
 modification=detect_modifications(image_path,result);result["modification_intelligence"]=modification;result["condition_and_harvest"]=condition_harvest_check(result,modification.get("observations"));result["recovery_lab"]=build_recovery_plan(spike_glass,result);result["insight"]=BoardInsight().generate(result);return result
