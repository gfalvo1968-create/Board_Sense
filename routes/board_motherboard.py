# routes/board_motherboard.py
import cv2
import numpy as np

def detect_motherboard(image_path):
    """Motherboard detector v0.3. Edge banks require a coherent PCB-perimeter cluster."""
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
        similar_pairs=0
        for i,a in enumerate(kept):
            for b in kept[i+1:]:
                al=max(a[2],a[3]);bl=max(b[2],b[3]);at=min(a[2],a[3]);bt=min(b[2],b[3]);size=max(al,bl)/max(1,min(al,bl));thick=max(at,bt)/max(1,min(at,bt));parallel=(abs((a[2]>=a[3])-(b[2]>=b[3]))==0)
                if size<=1.35 and thick<=1.55 and parallel:similar_pairs+=1
        signals["parallel_slot_bank"]=slot_count>=2;signals["confirmed_slot_bank"]=slot_count>=2 and similar_pairs>=1
        if signals["confirmed_slot_bank"]:
            signals["structural_evidence"].append(f"{slot_count} long connector structures with corroborating parallel geometry")
            for x,y,cw,ch,_ in kept[:4]:signals["structure_regions"].append({"x":x,"y":y,"w":cw,"h":ch,"type":"Long board connector / possible slot","confidence":72})
        elif slot_count:signals["structural_evidence"].append(f"{slot_count} long connector-like structures detected; slot identity not confirmed")
        # v0.3: a connector bank is not just five rectangles somewhere near an edge.
        # Candidates must be small/moderate, actually touch a narrow perimeter band,
        # and cluster along the same physical side of the PCB.
        edge_band=max(10,int(min(w,h)*.07));side_boxes={"left":[],"right":[],"top":[],"bottom":[]}
        for c in contours:
            x,y,cw,ch=cv2.boundingRect(c);ar=(cw*ch)/image_area
            if ar<.0015 or ar>.035:continue
            aspect=max(cw,ch)/max(min(cw,ch),1)
            if not 1.0<=aspect<=5.5:continue
            touches=[]
            if x<=edge_band:touches.append("left")
            if x+cw>=w-edge_band:touches.append("right")
            if y<=edge_band:touches.append("top")
            if y+ch>=h-edge_band:touches.append("bottom")
            for side in touches:side_boxes[side].append((x,y,cw,ch))
        best_side=None;best=[]
        for side,boxes in side_boxes.items():
            if len(boxes)<5:continue
            # Deduplicate nested contour boxes before deciding that a bank exists.
            dedup=[]
            for b in sorted(boxes,key=lambda z:z[2]*z[3],reverse=True):
                bx,by,bw,bh=b;bcx,bcy=bx+bw/2,by+bh/2
                if all(abs(bcx-(dx+dw/2))>max(8,min(bw,dw)*.35) or abs(bcy-(dy+dh/2))>max(8,min(bh,dh)*.35) for dx,dy,dw,dh in dedup):dedup.append(b)
            if len(dedup)>=5 and len(dedup)>len(best):best_side=side;best=dedup
        signals["edge_connector_bank"]=bool(best_side and len(best)>=5)
        if signals["edge_connector_bank"]:
            signals["structural_evidence"].append(f"coherent rectangular connector structures along the {best_side} PCB perimeter")
            xs=[b[0] for b in best];ys=[b[1] for b in best];x2=[b[0]+b[2] for b in best];y2=[b[1]+b[3] for b in best];signals["structure_regions"].append({"x":min(xs),"y":min(ys),"w":max(x2)-min(xs),"h":max(y2)-min(ys),"type":"Board-edge connector bank","confidence":76,"edge_side":best_side})
        score=(2 if large_board else 0)+(4 if signals["confirmed_slot_bank"] else 0)+(2 if slot_count>=4 and signals["confirmed_slot_bank"] else 0)+(3 if signals["edge_connector_bank"] else 0);signals["motherboard_structure_score"]=score;signals["possible_motherboard"]=bool(large_board and signals["confirmed_slot_bank"] and signals["edge_connector_bank"] and score>=9)
    except Exception as e:print(f"[Motherboard Detector Error] {e}")
    return signals
