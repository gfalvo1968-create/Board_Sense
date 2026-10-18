# routes/board_motherboard.py
import cv2
import numpy as np
from routes.board_region import board_region_mask, region_on_board

def _overlap_fraction(a,b):
    x,y,w,h=a;xx,yy,ww,hh=b
    intersection=max(0,min(x+w,xx+ww)-max(x,xx))*max(0,min(y+h,yy+hh)-max(y,yy))
    return intersection/max(1,min(w*h,ww*hh))

def detect_motherboard(image_path):
    """Motherboard detector v0.6. Edge banks use the PCB outline, not photo edges."""
    signals={"large_board":False,"possible_motherboard":False,"motherboard_structure_score":0,"motherboard_score":0,"long_slot_candidates":0,"parallel_slot_bank":False,"confirmed_slot_bank":False,"edge_connector_bank":False,"structural_evidence":[],"structure_regions":[]}
    try:
        image=cv2.imread(image_path)
        if image is None:return signals
        h,w=image.shape[:2];mask=board_region_mask(image)
        if not cv2.countNonZero(mask):return signals
        # Perimeter geometry can bridge component-covered gaps in the solder
        # mask. Keep this hull local: component labels still use the stricter
        # surface mask, and the frame identity gate retains real notches.
        outlines,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        if outlines:
            mask=mask.copy()
            cv2.fillConvexPoly(mask,cv2.convexHull(max(outlines,key=cv2.contourArea)),255)
        bx,by,board_w,board_h=cv2.boundingRect(mask);long_side,short_side=max(board_w,board_h),min(board_w,board_h);ratio=long_side/max(short_side,1);image_area=max(cv2.countNonZero(mask),1);large_board=ratio<2.2 and long_side>=300 and image_area/(h*w)>=.12;signals["large_board"]=large_board
        pcb_bounds={'x':bx,'y':by,'w':board_w,'h':board_h}
        if large_board:signals["structural_evidence"].append("motherboard-scale rectangular board footprint")
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);edges=cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),55,145);edges=cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8));contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE);slots=[]
        for c in contours:
            x,y,cw,ch=cv2.boundingRect(c);area_ratio=(cw*ch)/image_area;aspect=max(cw,ch)/max(min(cw,ch),1)
            if not region_on_board(mask,{'x':x,'y':y,'w':cw,'h':ch}):continue
            if 5.5<=aspect<=20 and .003<=area_ratio<=.04 and max(cw,ch)>=int(long_side*.18):
                fill=cv2.contourArea(c)/max(cw*ch,1)
                if fill>=.18:slots.append((x,y,cw,ch,fill))
        # Molded colored connector bodies can have open channels that defeat
        # closed-edge contours. Directional opening separates adjacent bodies
        # without treating color alone as a motherboard or recovery signal.
        hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
        colored=cv2.inRange(hsv,np.array([95,90,30]),np.array([135,255,255]))
        run=max(20,int(long_side*.075))
        for vertical in (True,False):
            kernel=np.ones((run,1) if vertical else (1,run),np.uint8)
            bodies=cv2.morphologyEx(colored,cv2.MORPH_OPEN,kernel)
            bodies=cv2.morphologyEx(bodies,cv2.MORPH_CLOSE,np.ones((max(1,int(long_side*.004))|1,)*2,np.uint8))
            body_contours,_=cv2.findContours(bodies,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            for c in body_contours:
                x,y,cw,ch=cv2.boundingRect(c)
                aspect=max(cw,ch)/max(min(cw,ch),1)
                fill=cv2.contourArea(c)/max(cw*ch,1)
                if (6<=aspect<=25 and max(cw,ch)>=long_side*.35
                        and .002<=cw*ch/image_area<=.06 and fill>=.4
                        and region_on_board(mask,{'x':x,'y':y,'w':cw,'h':ch})):
                    slots.append((x,y,cw,ch,fill))
        kept=[]
        for x,y,cw,ch,fill in sorted(slots,key=lambda r:r[2]*r[3],reverse=True):
            cx,cy=x+cw//2,y+ch//2
            if all(_overlap_fraction((x,y,cw,ch),(px,py,pw,ph))<.65 for px,py,pw,ph,_ in kept):kept.append((x,y,cw,ch,fill))
        kept=kept[:8];slot_count=len(kept);signals["long_slot_candidates"]=slot_count
        similar_pairs=0
        for i,a in enumerate(kept):
            for b in kept[i+1:]:
                al=max(a[2],a[3]);bl=max(b[2],b[3]);at=min(a[2],a[3]);bt=min(b[2],b[3]);size=max(al,bl)/max(1,min(al,bl));thick=max(at,bt)/max(1,min(at,bt));parallel=(abs((a[2]>=a[3])-(b[2]>=b[3]))==0)
                if parallel:
                    across=abs((a[1]+a[3]/2)-(b[1]+b[3]/2)) if a[2]>=a[3] else abs((a[0]+a[2]/2)-(b[0]+b[2]/2))
                    along=abs((a[0]+a[2]/2)-(b[0]+b[2]/2)) if a[2]>=a[3] else abs((a[1]+a[3]/2)-(b[1]+b[3]/2))
                    if size<=1.35 and thick<=1.55 and .75*max(at,bt)<=across<=long_side*.2 and along<=max(al,bl)*.2:similar_pairs+=1
        signals["parallel_slot_bank"]=slot_count>=2;signals["confirmed_slot_bank"]=slot_count>=2 and similar_pairs>=1
        if signals["confirmed_slot_bank"]:
            signals["structural_evidence"].append(f"{slot_count} long connector structures with corroborating parallel geometry")
            for x,y,cw,ch,_ in kept[:4]:signals["structure_regions"].append({"x":x,"y":y,"w":cw,"h":ch,"type":"Long board connector / possible slot","confidence":72})
        elif slot_count:signals["structural_evidence"].append(f"{slot_count} long connector-like structures detected; slot identity not confirmed")

        # v0.4: random solder-side rectangles near a board edge are not an I/O bank.
        # Require three distinct rectangular low-saturation bodies, similar scale, aligned along that
        # side, and shallow enough that the cluster behaves like a perimeter row.
        edge_band=max(10,int(min(board_w,board_h)*.055));side_boxes={"left":[],"right":[],"top":[],"bottom":[]}
        for c in contours:
            x,y,cw,ch=cv2.boundingRect(c);ar=(cw*ch)/image_area
            if not region_on_board(mask,{'x':x,'y':y,'w':cw,'h':ch}):continue
            if ar<.0015 or ar>.025:continue
            # Connector bodies are rectangular; round capacitor tops and
            # colored solder-mask patches cannot establish an I/O bank.
            fill=cv2.contourArea(c)/max(cw*ch,1)
            perimeter=cv2.arcLength(c,True)
            circularity=4*np.pi*cv2.contourArea(c)/max(perimeter*perimeter,1)
            if fill<.55 or circularity>.82 or float(np.median(hsv[y:y+ch,x:x+cw,1]))>80:continue
            aspect=max(cw,ch)/max(min(cw,ch),1)
            if not 1.0<=aspect<=4.5:continue
            touches=[]
            if x<=bx+edge_band:touches.append("left")
            if x+cw>=bx+board_w-edge_band:touches.append("right")
            if y<=by+edge_band:touches.append("top")
            if y+ch>=by+board_h-edge_band:touches.append("bottom")
            for side in touches:side_boxes[side].append((x,y,cw,ch))
        best_side=None;best=[]
        for side,boxes in side_boxes.items():
            if len(boxes)<3:continue
            dedup=[]
            for b in sorted(boxes,key=lambda z:z[2]*z[3],reverse=True):
                box_x,box_y,bw,bh=b;bcx,bcy=box_x+bw/2,box_y+bh/2
                if all(_overlap_fraction(b,d)<.5 for d in dedup):dedup.append(b)
            if len(dedup)<3:continue
            # Similar-size repetition is a key connector-bank signature.
            areas=np.array([bw*bh for _,_,bw,bh in dedup],dtype=float)
            med_area=float(np.median(areas)) if len(areas) else 0
            similar=[b for b in dedup if med_area and .35<=((b[2]*b[3])/med_area)<=2.8]
            if len(similar)<3:continue
            if side in("left","right"):
                depths=[bw for _,_,bw,_ in similar];centers=sorted(y0+bh/2 for _,y0,_,bh in similar);span=(max(centers)-min(centers))/max(board_h,1)
                shallow=float(np.median(depths))<=board_w*.16
            else:
                depths=[bh for _,_,_,bh in similar];centers=sorted(x0+bw/2 for x0,_,bw,_ in similar);span=(max(centers)-min(centers))/max(board_w,1)
                shallow=float(np.median(depths))<=board_h*.16
            # A real bank occupies a meaningful run of the perimeter, not a tiny
            # damaged/solder cluster that happens to touch the crop boundary.
            if not shallow or span<.25:continue
            if len(similar)>len(best):best_side=side;best=similar
        signals["edge_connector_bank"]=bool(best_side and len(best)>=3)
        if signals["edge_connector_bank"]:
            signals["structural_evidence"].append(f"repeated aligned connector bodies along the {best_side} PCB perimeter")
            xs=[b[0] for b in best];ys=[b[1] for b in best];x2=[b[0]+b[2] for b in best];y2=[b[1]+b[3] for b in best];signals["structure_regions"].append({"x":min(xs),"y":min(ys),"w":max(x2)-min(xs),"h":max(y2)-min(ys),"type":"Board-edge connector bank","confidence":78,"edge_side":best_side,"pcb_bounds":pcb_bounds,"geometry_proof":"three-plus distinct rectangular low-saturation bodies aligned along a meaningful PCB-perimeter run"})
        score=(2 if large_board else 0)+(4 if signals["confirmed_slot_bank"] else 0)+(2 if slot_count>=4 and signals["confirmed_slot_bank"] else 0)+(3 if signals["edge_connector_bank"] else 0);signals["motherboard_structure_score"]=score;signals["motherboard_score"]=score;signals["possible_motherboard"]=bool(large_board and signals["confirmed_slot_bank"] and signals["edge_connector_bank"] and score>=9)
    except Exception as e:print(f"[Motherboard Detector Error] {e}")
    return signals

