"""SPIKE Physical Board Fingerprint v0.2.
Conservative board-shape evidence for multi-photo case identity. Positive geometry
conflicts require large-board views and corroboration; detail views are never used
as negative identity evidence.
"""
import cv2
import numpy as np

def extract_board_fingerprint(image_path):
    out={"version":"SPIKE Physical Board Fingerprint v0.2","available":False,"image_aspect":0.0,"board_aspect":None,"board_area_ratio":None,"rectangularity":None,"solidity":None,"corner_count":None,"hole_count":0,"landmark_count":0,"coverage":"unknown","geometry_quality":"low"}
    try:
        im=cv2.imread(image_path)
        if im is None:return out
        h,w=im.shape[:2];area=float(w*h);out["image_aspect"]=round(max(w,h)/max(1,min(w,h)),3);gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);blur=cv2.GaussianBlur(gray,(5,5),0);edges=cv2.Canny(blur,45,135);edges=cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8));contours,_=cv2.findContours(edges,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);candidates=[c for c in contours if cv2.contourArea(c)>=area*.08]
        if candidates:
            c=max(candidates,key=cv2.contourArea);ba=cv2.contourArea(c);rect=cv2.minAreaRect(c);rw,rh=rect[1];rw=max(float(rw),1.0);rh=max(float(rh),1.0);out["board_aspect"]=round(max(rw,rh)/max(1.0,min(rw,rh)),3);out["board_area_ratio"]=round(ba/area,3);out["rectangularity"]=round(ba/max(rw*rh,1.0),3);hull=cv2.convexHull(c);hull_area=max(cv2.contourArea(hull),1.0);out["solidity"]=round(ba/hull_area,3);peri=cv2.arcLength(c,True);poly=cv2.approxPolyDP(c,.025*peri,True);out["corner_count"]=len(poly)
            large=ba/area>=.28;quality=large and out["rectangularity"]>=.42 and out["solidity"]>=.62;out["coverage"]="whole_or_large_view" if large else "detail_or_partial_view";out["geometry_quality"]="good" if quality else ("medium" if large else "low")
        circles=cv2.HoughCircles(blur,cv2.HOUGH_GRADIENT,1.2,max(12,min(w,h)//18),param1=100,param2=28,minRadius=max(2,min(w,h)//120),maxRadius=max(5,min(w,h)//22));out["hole_count"]=0 if circles is None else min(20,len(circles[0]));corners=cv2.goodFeaturesToTrack(gray,maxCorners=80,qualityLevel=.04,minDistance=max(8,min(w,h)//35));out["landmark_count"]=0 if corners is None else len(corners);out["available"]=True
    except Exception as exc:out["error"]=str(exc)
    return out

def fingerprint_conflict(a,b):
    """Negative evidence only from two sufficiently exposed, credible board contours."""
    if not a.get("available") or not b.get("available"):return None
    if a.get("coverage")!="whole_or_large_view" or b.get("coverage")!="whole_or_large_view":return None
    if a.get("geometry_quality")=="low" or b.get("geometry_quality")=="low":return None
    aa=a.get("board_aspect");bb=b.get("board_aspect")
    if not aa or not bb:return None
    ratio=max(aa,bb)/max(.01,min(aa,bb));hole_gap=abs(int(a.get("hole_count",0))-int(b.get("hole_count",0)));land_a=max(1,int(a.get("landmark_count",0)));land_b=max(1,int(b.get("landmark_count",0)));land_ratio=max(land_a,land_b)/min(land_a,land_b);rect_gap=abs(float(a.get("rectangularity") or 0)-float(b.get("rectangularity") or 0));solidity_gap=abs(float(a.get("solidity") or 0)-float(b.get("solidity") or 0));support=(hole_gap>=3)+(land_ratio>=1.8)+(rect_gap>=.22)+(solidity_gap>=.20);conflict=bool(ratio>=1.85 and support>=1)
    return {"conflict":conflict,"aspect_mismatch":round(ratio,2),"hole_gap":hole_gap,"landmark_ratio":round(land_ratio,2),"rectangularity_gap":round(rect_gap,2),"solidity_gap":round(solidity_gap,2),"supporting_mismatches":int(support),"reason":"Rotation-safe large-view board geometry differs beyond conservative same-board tolerance." if conflict else "No strong physical geometry contradiction."}
