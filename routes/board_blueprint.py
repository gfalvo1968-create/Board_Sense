"""Board Blueprint v0.6: conservative context, component, and edge-connector guards.

Blueprint is an evidence map, not an equipment-family oracle. Generic connector
geometry stays generic, and large component bodies cannot become connector banks
merely because a structural detector sees repeated edges or pins.
"""
from pathlib import Path
import math
import cv2
from routes.board_motherboard import detect_motherboard
LABELS={"IC-like package":"IC / Logic Package","Power block / transformer / relay-like":"Power / Transformer / Relay","Capacitor-like round component":"Capacitor / Power Component","Plated contact / keypad pad":"Likely Plated Contact Zone","Gold finger / edge contact":"Gold Finger / Edge Contact","Motherboard slot / socket bank":"Long Board Connector / Slot","Rear I/O / connector bank":"Board Edge Connector Zone"}
TYPE_PRIORITY={"Motherboard slot / socket bank":9.0,"Rear I/O / connector bank":8.5,"Gold finger / edge contact":8.0,"Plated contact / keypad pad":7.0,"IC-like package":5.0,"Power block / transformer / relay-like":4.5,"Capacitor-like round component":1.0}
CONTEXT_NOTES={"Motherboard slot / socket bank":"Repeated long connector geometry detected. PC context is not independently strong enough to call this a DIMM or expansion slot.","Rear I/O / connector bank":"Dense edge connector geometry detected. Kept generic because edge connectors also occur on telecom, console, industrial, server, and proprietary logic boards.","Gold finger / edge contact":"Contact geometry is a recovery cue only; metal content is not visually assayed."}
def _confidence(r):
 try:v=float(r.get("confidence",0))
 except(TypeError,ValueError):return 0.0
 return v/100 if v>1 else v
def _iou(a,b):
 ax1,ay1=a["x"],a["y"];ax2,ay2=ax1+a["w"],ay1+a["h"];bx1,by1=b["x"],b["y"];bx2,by2=bx1+b["w"],by1+b["h"];iw=max(0,min(ax2,bx2)-max(ax1,bx1));ih=max(0,min(ay2,by2)-max(ay1,by1));inter=iw*ih;union=a["w"]*a["h"]+b["w"]*b["h"]-inter;return inter/union if union else 0
def _component_geometry_guard(r,image_w=None,image_h=None):
 r=dict(r);t=r.get("type","Detected region");w=max(1,int(r.get("w",1)));h=max(1,int(r.get("h",1)));ratio=max(w,h)/max(1,min(w,h));conf=_confidence(r)
 if t=="Capacitor-like round component" and ratio>1.65:r["type"]="IC-like package";r["geometry_guard"]="Capacitor label vetoed: region is too elongated/rectangular for a round-component call."
 if t=="Power block / transformer / relay-like" and ratio>2.8 and conf<.90:r["type"]="IC-like package";r["geometry_guard"]="Power-block label vetoed: thin rectangular geometry is more consistent with a logic package."
 # Real board-edge connector banks should live at the PCB perimeter. An isolated
 # large rectangular body well inside the board is much more likely a module,
 # heatsinked device, relay, transformer, or IC package than a rear-I/O bank.
 if t in("Rear I/O / connector bank","Motherboard slot / socket bank") and image_w and image_h:
  x=max(0,int(r.get("x",0)));y=max(0,int(r.get("y",0)));margin=max(12,int(min(image_w,image_h)*.07));touches_edge=x<=margin or y<=margin or x+w>=image_w-margin or y+h>=image_h-margin
  area_ratio=(w*h)/max(1,image_w*image_h)
  if t=="Rear I/O / connector bank" and (not touches_edge or area_ratio>.20):r["type"]="Power block / transformer / relay-like" if area_ratio>.035 else "IC-like package";r["geometry_guard"]="Edge-connector label vetoed: candidate is an interior/oversized component body rather than a PCB-perimeter connector bank."
  elif t=="Motherboard slot / socket bank" and area_ratio>.24:r["type"]="IC-like package";r["geometry_guard"]="Slot-bank label vetoed: candidate occupies too much board area for a plausible connector/slot bank."
 return r
def _rank_regions(regions,image_area,image_w,image_h,limit=8):
 ranked=[]
 for raw in regions or []:
  r=_component_geometry_guard(raw,image_w,image_h);r["x"]=max(0,int(r.get("x",0)));r["y"]=max(0,int(r.get("y",0)));r["w"]=max(1,int(r.get("w",1)));r["h"]=max(1,int(r.get("h",1)));t=r.get("type","Detected region");ar=r["w"]*r["h"]/max(1,image_area);r["_blueprint_score"]=TYPE_PRIORITY.get(t,1)+_confidence(r)*4+min(1.5,math.sqrt(max(0,ar))*5);ranked.append(r)
 ranked.sort(key=lambda r:r["_blueprint_score"],reverse=True);selected=[];counts={}
 for r in ranked:
  t=r.get("type","Detected region");per_limit=1 if t=="Capacitor-like round component" else(3 if t=="IC-like package" else 4)
  if counts.get(t,0)>=per_limit or any(_iou(r,k)>.38 for k in selected):continue
  selected.append(r);counts[t]=counts.get(t,0)+1
  if len(selected)>=limit:break
 return selected
def generate_blueprint(image_path,component_regions,output_dir):
 image=cv2.imread(str(image_path))
 if image is None:return{"available":False,"message":"Blueprint could not read the uploaded image."}
 motherboard=detect_motherboard(str(image_path));all_regions=list(component_regions or [])+list(motherboard.get("structure_regions",[]));output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True);output_name=f"{Path(image_path).stem}_blueprint.png";output_path=output_dir/output_name;h,w=image.shape[:2];area=w*h;thickness=max(2,int(max(w,h)/720));fs=max(.55,min(1.05,max(w,h)/1500));radius=max(15,int(max(w,h)/62));selected=_rank_regions(all_regions,area,w,h);index=[]
 for n,r in enumerate(selected,1):
  x=min(w-1,r["x"]);y=min(h-1,r["y"]);rw=min(r["w"],max(1,w-x));rh=min(r["h"],max(1,h-y));cx=min(w-radius-2,max(radius+2,x+rw//2));cy=min(h-radius-2,max(radius+2,y+rh//2));cv2.circle(image,(cx,cy),radius,(0,0,0),-1);cv2.circle(image,(cx,cy),radius,(0,255,255),thickness);text=str(n);(tw,th),_=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,fs,thickness);cv2.putText(image,text,(cx-tw//2,cy+th//2),cv2.FONT_HERSHEY_SIMPLEX,fs,(0,255,255),thickness,cv2.LINE_AA);t=r.get("type","Detected region");item={"number":n,"label":LABELS.get(t,t),"detector_label":t,"confidence":r.get("confidence"),"importance":round(r.get("_blueprint_score",0),2),"box":{"x":x,"y":y,"w":rw,"h":rh}}
  if t in CONTEXT_NOTES:item["context_guard"]=CONTEXT_NOTES[t]
  if r.get("geometry_guard"):item["geometry_guard"]=r["geometry_guard"]
  index.append(item)
 cv2.imwrite(str(output_path),image);return{"available":True,"image_filename":output_name,"component_index":index,"marker_count":len(index),"candidate_region_count":len(all_regions),"mode":"Board Blueprint v0.6 + Context Guard v0.1 + Component Guard v0.3","context_guard":{"active":True,"rule":"Generic geometry stays generic until equipment-specific evidence independently earns a subtype label.","motherboard_structure_score":motherboard.get("motherboard_structure_score",0)},"component_guard":{"active":True,"rule":"Component labels must agree with local geometry and PCB position; interior/oversized component bodies cannot be promoted to board-edge connector banks."},"note":"Blueprint prioritizes board-defining and likely value-bearing structures. Connector/contact labels describe visible geometry only; metal content is not visually assayed."}
