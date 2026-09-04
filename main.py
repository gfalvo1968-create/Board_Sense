from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import List, Optional
import shutil
import uvicorn
from ecosystem import get_ecosystem
from routes.board_analyzer import analyze_board
from routes.pair_reasoner import reconcile_pair
from routes.pair_decision_guard import guard_pair
from routes.spike_evidence_packet import build_evidence_packet
from routes.case_reasoner import reconcile_case
from routes.inspection_target import parse_inspection_target, apply_inspection_target
from recovery_lab.core.time_value import compare_paths
from routes.grade import router as grade_router
from routes.irm_core import router as irm_router
from routes.market_bridge import router as market_router
from routes.reference_loader import load_reference_data
app=FastAPI(title="Board Sense")
app.add_middleware(CORSMiddleware,allow_origins=["https://gfalvo1968-create.github.io","https://boardsense.scrapradarfamily.com"],allow_credentials=False,allow_methods=["GET","POST","OPTIONS"],allow_headers=["*"])
@app.on_event("startup")
def startup_event():load_reference_data()
BASE_DIR=Path(__file__).resolve().parent;STATIC_DIR=BASE_DIR/"Static";DATA_DIR=BASE_DIR/"data";IMAGE_DIR=DATA_DIR/"Images";BLUEPRINT_DIR=DATA_DIR/"Blueprints";IMAGE_DIR.mkdir(parents=True,exist_ok=True);BLUEPRINT_DIR.mkdir(parents=True,exist_ok=True);app.mount("/Static",StaticFiles(directory=STATIC_DIR),name="Static");app.mount("/blueprints",StaticFiles(directory=BLUEPRINT_DIR),name="blueprints");app.include_router(grade_router);app.include_router(irm_router);app.include_router(market_router)
@app.get("/")
async def root():return FileResponse(BASE_DIR/"index.html")
@app.get("/ecosystem")
def ecosystem_data():return get_ecosystem()
def _save_upload(upload:UploadFile,target:Path):
 with open(target,"wb") as buffer:shutil.copyfileobj(upload.file,buffer)
def _economics_payload(**values):return {k:v for k,v in values.items() if v is not None}
def _spike_target_rank(result):
 t=(result or {}).get("inspection_target") or {};status=t.get("status");rank={"target_candidate":3,"target_area_candidate":2,"target_not_confirmed":1}.get(status,0)
 vt=t.get("visual_target") or {};visual=float(vt.get("confidence") or 0);role_bonus=1 if (result or {}).get("spike_role")=="closeup" else 0;spike=(result or {}).get("spike_glass") or {};generic=float(spike.get("confidence") or 0)
 return (rank,visual,role_bonus,generic)
@app.post("/analyze")
async def analyze_board_route(file:UploadFile=File(...),inspection_target:Optional[str]=Form(None)):
 file_path=IMAGE_DIR/file.filename;_save_upload(file,file_path);result=analyze_board(str(file_path));target_packet=parse_inspection_target(inspection_target)
 if target_packet:result=apply_inspection_target(result,target_packet,str(file_path))
 result["status"]="success";result["board"]=file.filename;result["spike_evidence"]=build_evidence_packet(result);return result
@app.post("/analyze-spike-pair")
async def analyze_spike_pair_route(context:UploadFile=File(...),closeup:Optional[UploadFile]=File(None),inspection_target:Optional[str]=Form(None)):
 target_packet=parse_inspection_target(inspection_target);uploads=[("context",context)]
 if closeup is not None:uploads.append(("closeup",closeup))
 views=[]
 for role,upload in uploads:
  path=IMAGE_DIR/f"spike_{role}_{upload.filename}";_save_upload(upload,path);result=analyze_board(str(path))
  if target_packet:result=apply_inspection_target(result,target_packet,str(path))
  result["status"]="success";result["board"]=upload.filename;result["spike_role"]=role;result["spike_evidence"]=build_evidence_packet(result);views.append(result)
 selected=max(views,key=_spike_target_rank) if target_packet else max(views,key=lambda r:float(((r.get("spike_glass") or {}).get("confidence")) or 0))
 summary=[]
 for view in views:
  spike=view.get("spike_glass") or {};top=spike.get("top_match") or {};target=view.get("inspection_target") or {}
  summary.append({"role":view.get("spike_role"),"board":view.get("board"),"generic_label":top.get("label"),"generic_confidence":spike.get("confidence"),"target_status":target.get("status"),"target_confidence":((target.get("visual_target") or {}).get("confidence"))})
 return {"status":"success","mode":"spike_two_photo","photo_count":len(views),"views":views,"combined":selected,"selected_role":selected.get("spike_role"),"pair_summary":summary,"integrity_rule":"Two-photo Spike Glass compares context and close-up evidence for one inspection target. It does not merge board economics or manufacture composition/value."}
@app.post("/analyze-pair")
async def analyze_board_pair_route(side_a:UploadFile=File(...),side_b:UploadFile=File(...)):
 side_a_path=IMAGE_DIR/f"side_a_{side_a.filename}";side_b_path=IMAGE_DIR/f"side_b_{side_b.filename}";_save_upload(side_a,side_a_path);_save_upload(side_b,side_b_path);result_a=analyze_board(str(side_a_path));result_b=analyze_board(str(side_b_path));result_a["spike_evidence"]=build_evidence_packet(result_a);result_b["spike_evidence"]=build_evidence_packet(result_b);paired=guard_pair(result_a,result_b,reconcile_pair(result_a,result_b));paired["spike_evidence"]=build_evidence_packet(paired);paired["model"]="Board Sense v2.3 + SPIKE Verification v0.1 + Pair Reasoner v1.1";return {"status":"success","mode":"two_sided_same_board","side_a":result_a,"side_b":result_b,"paired":paired}
@app.post("/analyze-case")
async def analyze_board_case_route(files:List[UploadFile]=File(...),current_sell_whole_value:Optional[float]=Form(None),intact_sell_whole_value:Optional[float]=Form(None),partial_recovered_value:Optional[float]=Form(None),partial_residual_value:Optional[float]=Form(None),partial_minutes:Optional[float]=Form(None),partial_costs:Optional[float]=Form(None),full_recovery_value:Optional[float]=Form(None),full_minutes:Optional[float]=Form(None),full_costs:Optional[float]=Form(None)):
 """Analyze 2-6 photos only after SPIKE verifies that reconciliation is safe."""
 if len(files)<2 or len(files)>6:return {"status":"error","message":"Choose between 2 and 6 photos of the same board."}
 results=[]
 for i,upload in enumerate(files,1):
  safe_name=f"case_{i}_{upload.filename}";path=IMAGE_DIR/safe_name;_save_upload(upload,path);result=analyze_board(str(path));result["board"]=upload.filename;result["view_number"]=i;result["spike_evidence"]=build_evidence_packet(result);results.append(result)
 combined=reconcile_case(results)
 if combined.get("status")=="case_identity_failed" or (combined.get("same_board_verification") or {}).get("block_reconciliation"):
  return {"status":"success","mode":"multi_photo_identity_blocked","photo_count":len(results),"views":results,"combined":combined,"case_warning":"MULTIPLE BOARDS DETECTED - split these photos into one case per physical board."}
 econ=_economics_payload(sell_whole_value=intact_sell_whole_value,partial_recovered_value=partial_recovered_value,partial_residual_value=partial_residual_value,partial_minutes=partial_minutes,partial_costs=partial_costs,full_recovery_value=full_recovery_value,full_minutes=full_minutes,full_costs=full_costs);condition=combined.get("condition_and_harvest") or {};factor=condition.get("remaining_value_factor",1.0)
 if current_sell_whole_value is not None:econ["sell_whole_value"]=current_sell_whole_value;factor=1.0;sell_basis="CURRENT CONDITION OFFER"
 elif intact_sell_whole_value is not None:sell_basis="INTACT BOARD BASELINE"
 else:sell_basis="NOT PROVIDED"
 combined["recovery_economics"]=compare_paths(condition_factor=factor,**econ);combined["recovery_economics"]["sell_value_basis"]=sell_basis;combined["recovery_economics"]["condition_link"]={"condition":condition.get("condition"),"remaining_value_factor":condition.get("remaining_value_factor",1.0),"rule":"Current-condition offers are never discounted twice. Intact-board baselines may be reduced only by confirmed harvesting. Uncertain absence creates no deduction."};combined["spike_evidence"]=build_evidence_packet(combined,condition_observations=condition.get("observations"));return {"status":"success","mode":"same_board_multi_photo","photo_count":len(results),"views":results,"combined":combined}
if __name__=="__main__":uvicorn.run(app,host="0.0.0.0",port=8080)
