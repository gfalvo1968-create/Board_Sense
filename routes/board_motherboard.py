# routes/board_motherboard.py
import cv2
import numpy as np

def detect_motherboard(image_path):
    """Motherboard detector v0.2. Long solder patterns alone are not DIMM/PCI proof."""
    signals={"large_board":False,"possible_motherboard":False,"motherboard_structure_score":0,"long_slot_candidates":0,"parallel_slot_bank":False,"confirmed_slot_bank":False,"edge_connector_bank":False,"structural_evidence":[],"structure_regions":[]}
    try:
        image=cv2.imread(image_path)
        if image is None:return signals
        h,w=image.shape[:2];long_side,short_side=max(w,h),min(w,h);ratio=long_side/max(short_side,1);image_area=max(w*h,1);large_board=ratio<2.2 and long_side>700;signals["large_board"]=large_board
        if large_board:signals["structural_evidence"].append("motherboard-scale rectangular board footprint")
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);edges=cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),55,145);edges=cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8));contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE);slots=[]
        for c in contours:
            x,y,cw,ch=cv2.boundingRect(c);area_ratio=(cw*ch)/image_area;aspect=max(cw,ch)/max(min(cw,ch),1)
            if 5.5<=aspect<=20 and .003<=area_ratio<=.04 and max(cw,ch)>=int(long_side*.18):
                fill=cv2.contourArea(c)/max(cw*ch,1)
                if fill>=.18:slots.append((x,y,cw,ch,fill))
        kept=[]
        for x,y,cw,ch,fill in sorted(slots,key=lambda r:r[2]*r[3],reverse=True):
            cx,cy=x+cw//2,y+ch//2
            if all(abs(cx-(px+pw//2))>long_side*.035 or abs(cy-(py+ph//2))>long_side*.035 for px,py,pw,ph,_ in kept):kept.append((x,y,cw,ch,fill))
        kept=kept[:8];slot_count=len(kept);signals["long_slot_candidates"]=slot_count
        # Require repeated structures with similar dimensions and alignment, not just several long marks.
        similar_pairs=0
        for i,a in enumerate(kept):
            for b in kept[i+1:]:
                al=max(a[2],a[3]);bl=max(b[2],b[3]);at=min(a[2],a[3]);bt=min(b[2],b[3]);size=max(al,bl)/max(1,min(al,bl));thick=max(at,bt)/max(1,min(at,bt));parallel=(abs((a[2]>=a[3])-(b[2]>=b[3]))==0)
                if size<=1.35 and thick<=1.55 and parallel:similar_pairs+=1
        signals["parallel_slot_bank"]=slot_count>=2
        signals["confirmed_slot_bank"]=slot_count>=2 and similar_pairs>=1
        if signals["confirmed_slot_bank"]:
            signals["structural_evidence"].append(f"{slot_count} long connector structures with corroborating parallel geometry")
            for x,y,cw,ch,_ in kept[:4]:signals["structure_regions"].append({"x":x,"y":y,"w":cw,"h":ch,"type":"Long board connector / possible slot","confidence":72})
        elif slot_count:signals["structural_evidence"].append(f"{slot_count} long connector-like structures detected; slot identity not confirmed")
        edge_band=int(min(w,h)*.16);edge_boxes=[]
        for c in contours:
            x,y,cw,ch=cv2.boundingRect(c)
            if cw*ch<image_area*.0015:continue
            near=x<edge_band or y<edge_band or x+cw>w-edge_band or y+ch>h-edge_band;aspect=max(cw,ch)/max(min(cw,ch),1)
            if near and 1.0<=aspect<=5.5:edge_boxes.append((x,y,cw,ch))
        signals["edge_connector_bank"]=len(edge_boxes)>=5
        if signals["edge_connector_bank"]:
            signals["structural_evidence"].append("dense rectangular connector structures along a board edge");xs=[b[0] for b in edge_boxes];ys=[b[1] for b in edge_boxes];x2=[b[0]+b[2] for b in edge_boxes];y2=[b[1]+b[3] for b in edge_boxes];signals["structure_regions"].append({"x":min(xs),"y":min(ys),"w":max(x2)-min(xs),"h":max(y2)-min(ys),"type":"Board-edge connector bank","confidence":72})
        score=(2 if large_board else 0)+(4 if signals["confirmed_slot_bank"] else 0)+(2 if slot_count>=4 and signals["confirmed_slot_bank"] else 0)+(3 if signals["edge_connector_bank"] else 0);signals["motherboard_structure_score"]=score;signals["possible_motherboard"]=bool(large_board and signals["confirmed_slot_bank"] and signals["edge_connector_bank"] and score>=9)
    except Exception as e:print(f"[Motherboard Detector Error] {e}")
    return signals
