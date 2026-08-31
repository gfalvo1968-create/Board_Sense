"""SPIKE Physical Board Fingerprint v0.3.
Board-shape evidence for multi-photo identity. Handles full boards that nearly fill
the frame, where ordinary external-edge contours can fragment on components.
"""
import cv2
import numpy as np

def _green_board_mask(im):
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    # Broad PCB-green family; intentionally only used to support coverage/outline,
    # never as proof that two boards are identical.
    m=cv2.inRange(hsv,np.array([28,35,22]),np.array([105,255,255]))
    k=max(5,(min(im.shape[:2])//45)|1)
    m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((k,k),np.uint8),iterations=2)
    return m

def extract_board_fingerprint(image_path):
    out={"version":"SPIKE Physical Board Fingerprint v0.3","available":False,"image_aspect":0.0,"board_aspect":None,"board_area_ratio":None,"rectangularity":None,"solidity":None,"corner_count":None,"hole_count":0,"landmark_count":0,"coverage":"unknown","geometry_quality":"low","coverage_basis":"none"}
    try:
        im=cv2.imread(image_path)
        if im is None:return out
        h,w=im.shape[:2];area=float(w*h);out["image_aspect"]=round(max(w,h)/max(1,min(w,h)),3);gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);blur=cv2.GaussianBlur(gray,(5,5),0)
        edges=cv2.Canny(blur,45,135);edges=cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8));contours,_=cv2.findContours(edges,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);candidates=[c for c in contours if cv2.contourArea(c)>=area*.08]
        best=None;basis="edge_contour"
        if candidates:best=max(candidates,key=cv2.contourArea)
        # A close full-board photo often loses one outer edge to the frame or has its
        # contour broken by tall components. Recover coverage from the PCB surface.
        mask=_green_board_mask(im);mc,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);mc=[c for c in mc if cv2.contourArea(c)>=area*.12]
        if mc:
            gm=max(mc,key=cv2.contourArea)
            if best is None or cv2.contourArea(gm)>cv2.contourArea(best)*1.15:best=gm;basis="pcb_surface"
        if best is not None:
            c=best;ba=cv2.contourArea(c);rect=cv2.minAreaRect(c);rw,rh=rect[1];rw=max(float(rw),1.0);rh=max(float(rh),1.0);out["board_aspect"]=round(max(rw,rh)/max(1.0,min(rw,rh)),3);out["board_area_ratio"]=round(ba/area,3);out["rectangularity"]=round(ba/max(rw*rh,1.0),3);hull=cv2.convexHull(c);out["solidity"]=round(ba/max(cv2.contourArea(hull),1.0),3);peri=cv2.arcLength(c,True);poly=cv2.approxPolyDP(c,.025*peri,True);out["corner_count"]=len(poly);out["coverage_basis"]=basis
            x,y,bw,bh=cv2.boundingRect(c);touches=sum((x<=w*.035,y<=h*.035,x+bw>=w*.965,y+bh>=h*.965));span=max(bw/w,bh/h);cross_span=min(bw/w,bh/h)
            large=ba/area>=.22 or (span>=.82 and cross_span>=.55)
            frame_full=large and touches>=2 and span>=.88
            quality=large and (out["rectangularity"]>=.38 or out["solidity"]>=.60)
            out["coverage"]="whole_or_large_view" if large else "detail_or_partial_view";out["geometry_quality"]="good" if quality and (ba/area>=.34 or frame_full) else ("medium" if large else "low")
            out["frame_edge_contacts"]=int(touches);out["board_span"]=[round(bw/w,3),round(bh/h,3)]
        circles=cv2.HoughCircles(blur,cv2.HOUGH_GRADIENT,1.2,max(12,min(w,h)//18),param1=100,param2=28,minRadius=max(2,min(w,h)//120),maxRadius=max(5,min(w,h)//22));out["hole_count"]=0 if circles is None else min(20,len(circles[0]));corners=cv2.goodFeaturesToTrack(gray,maxCorners=80,qualityLevel=.04,minDistance=max(8,min(w,h)//35));out["landmark_count"]=0 if corners is None else len(corners);out["available"]=True
    except Exception as exc:out["error"]=str(exc)
    return out

def fingerprint_conflict(a,b):
    if not a.get("available") or not b.get("available"):return None
    if a.get("coverage")!="whole_or_large_view" or b.get("coverage")!="whole_or_large_view":return None
    if a.get("geometry_quality")=="low" or b.get("geometry_quality")=="low":return None
    aa=a.get("board_aspect");bb=b.get("board_aspect")
    if not aa or not bb:return None
    ratio=max(aa,bb)/max(.01,min(aa,bb));hole_gap=abs(int(a.get("hole_count",0))-int(b.get("hole_count",0)));land_a=max(1,int(a.get("landmark_count",0)));land_b=max(1,int(b.get("landmark_count",0)));land_ratio=max(land_a,land_b)/min(land_a,land_b);rect_gap=abs(float(a.get("rectangularity") or 0)-float(b.get("rectangularity") or 0));solidity_gap=abs(float(a.get("solidity") or 0)-float(b.get("solidity") or 0));support=(hole_gap>=3)+(land_ratio>=1.8)+(rect_gap>=.22)+(solidity_gap>=.20);conflict=bool(ratio>=1.85 and support>=1)
    return {"conflict":conflict,"aspect_mismatch":round(ratio,2),"hole_gap":hole_gap,"landmark_ratio":round(land_ratio,2),"rectangularity_gap":round(rect_gap,2),"solidity_gap":round(solidity_gap,2),"supporting_mismatches":int(support),"reason":"Rotation-safe large-view board geometry differs beyond conservative same-board tolerance." if conflict else "No strong physical geometry contradiction."}
