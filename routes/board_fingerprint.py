"""SPIKE Physical Board Fingerprint v0.1.

Extracts coarse geometry/landmark evidence from each photo. It is designed for
case consistency checks, not exact board identification. Front/back and detail
views are allowed to differ, so no single fingerprint field proves identity.
"""
import cv2
import numpy as np

def extract_board_fingerprint(image_path):
    out={"version":"SPIKE Physical Board Fingerprint v0.1","available":False,"image_aspect":0.0,"board_aspect":None,"board_area_ratio":None,"corner_count":None,"hole_count":0,"landmark_count":0,"coverage":"unknown"}
    try:
        im=cv2.imread(image_path)
        if im is None:return out
        h,w=im.shape[:2];out["image_aspect"]=round(max(w,h)/max(1,min(w,h)),3)
        gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);blur=cv2.GaussianBlur(gray,(5,5),0)
        edges=cv2.Canny(blur,45,135);edges=cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        contours,_=cv2.findContours(edges,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);area=float(w*h)
        candidates=[c for c in contours if cv2.contourArea(c)>=area*.08]
        if candidates:
            c=max(candidates,key=cv2.contourArea);x,y,bw,bh=cv2.boundingRect(c);ba=cv2.contourArea(c);out["board_aspect"]=round(max(bw,bh)/max(1,min(bw,bh)),3);out["board_area_ratio"]=round(ba/area,3);peri=cv2.arcLength(c,True);poly=cv2.approxPolyDP(c,.025*peri,True);out["corner_count"]=len(poly);out["coverage"]="whole_or_large_view" if ba/area>=.28 else "detail_or_partial_view"
        circles=cv2.HoughCircles(blur,cv2.HOUGH_GRADIENT,1.2,max(12,min(w,h)//18),param1=100,param2=28,minRadius=max(2,min(w,h)//120),maxRadius=max(5,min(w,h)//22));out["hole_count"]=0 if circles is None else min(20,len(circles[0]))
        corners=cv2.goodFeaturesToTrack(gray,maxCorners=80,qualityLevel=.04,minDistance=max(8,min(w,h)//35));out["landmark_count"]=0 if corners is None else len(corners);out["available"]=True
    except Exception as exc:out["error"]=str(exc)
    return out

def fingerprint_conflict(a,b):
    """Return conflict evidence only when both views expose enough board geometry."""
    if not a.get("available") or not b.get("available"):return None
    if a.get("coverage")!="whole_or_large_view" or b.get("coverage")!="whole_or_large_view":return None
    aa=a.get("board_aspect");bb=b.get("board_aspect")
    if not aa or not bb:return None
    ratio=max(aa,bb)/max(.01,min(aa,bb));area_a=a.get("board_area_ratio") or 0;area_b=b.get("board_area_ratio") or 0
    # Perspective can distort shape, so require a large mismatch plus supporting landmark disparity.
    hole_gap=abs(int(a.get("hole_count",0))-int(b.get("hole_count",0)));land_a=max(1,int(a.get("landmark_count",0)));land_b=max(1,int(b.get("landmark_count",0)));land_ratio=max(land_a,land_b)/min(land_a,land_b)
    if ratio>=1.85 and (hole_gap>=3 or land_ratio>=1.8):return {"conflict":True,"aspect_mismatch":round(ratio,2),"hole_gap":hole_gap,"landmark_ratio":round(land_ratio,2),"reason":"Large-view physical geometry differs beyond the conservative same-board tolerance."}
    return {"conflict":False,"aspect_mismatch":round(ratio,2),"hole_gap":hole_gap,"landmark_ratio":round(land_ratio,2)}
