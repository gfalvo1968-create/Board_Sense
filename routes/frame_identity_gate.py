"""SPIKE Single-Frame Board Identity Gate v0.3.

Blocks a single uploaded photograph when strong physical evidence says more than
one PCB is present. PCB confirmation and board identity remain separate gates.
Color is only used to find candidate PCB regions; geometry supplies the block.
"""
import cv2
import numpy as np


def inspect_frame(image_path):
    result={"version":"SPIKE Single-Frame Board Identity Gate v0.3","status":"SINGLE_BOARD_NOT_CONTRADICTED","block_analysis":False,"confidence":0,"evidence":[],"next_step":"Continue normal board analysis."}
    try:
        im=cv2.imread(image_path)
        if im is None:
            result.update({"status":"FRAME_UNREADABLE","confidence":0}); return result
        h,w=im.shape[:2]; area=float(max(1,h*w)); hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
        raw=cv2.inRange(hsv,np.array([28,35,22]),np.array([105,255,255]))

        # First look for two independently substantial PCB-colored bodies BEFORE
        # the stronger closing step can accidentally weld neighboring boards into
        # one contour. Small islands are ignored to protect normal component gaps.
        k0=max(3,(min(h,w)//110)|1)
        separated=cv2.morphologyEx(raw,cv2.MORPH_CLOSE,np.ones((k0,k0),np.uint8),iterations=1)
        sep_contours,_=cv2.findContours(separated,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        sep_areas=sorted([float(cv2.contourArea(c)) for c in sep_contours if cv2.contourArea(c)>=area*.035],reverse=True)
        two_regions=(len(sep_areas)>=2 and sep_areas[0]>=area*.12 and sep_areas[1]>=area*.055 and (sep_areas[0]+sep_areas[1])>=area*.24)

        k=max(5,(min(h,w)//45)|1)
        mask=cv2.morphologyEx(raw,cv2.MORPH_CLOSE,np.ones((k,k),np.uint8),iterations=2)
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        contours=[c for c in contours if cv2.contourArea(c)>=area*.12]
        if not contours:
            if two_regions:
                result.update({"status":"MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED","block_analysis":True,"confidence":90,"evidence":["Two independently substantial PCB-like regions are visible in one photograph.","One physical board per photo is required before blueprinting or grading."],"next_step":"Retake with exactly one physical board in frame."})
            return result

        c=max(contours,key=cv2.contourArea); board_area=float(cv2.contourArea(c)); rect=cv2.minAreaRect(c)
        rw,rh=rect[1]; rw,rh=max(float(rw),1.0),max(float(rh),1.0)
        hull=cv2.convexHull(c); hull_area=max(float(cv2.contourArea(hull)),1.0)
        solidity=board_area/hull_area; rectangularity=board_area/max(rw*rh,1.0)
        hull_idx=cv2.convexHull(c,returnPoints=False)
        defects=cv2.convexityDefects(c,hull_idx) if hull_idx is not None and len(hull_idx)>=3 and len(c)>=4 else None
        deep=[]; scale=max(rw,rh)
        if defects is not None:
            for d in defects[:,0]:
                depth=float(d[3])/256.0
                if depth>=scale*.04: deep.append(depth/scale)
        area_ratio=board_area/area; deep_count=len(deep); deepest=max(deep) if deep else 0.0

        profile_a=(.20<=area_ratio<=.80 and solidity<.91 and rectangularity<.82 and deep_count>=5 and deepest>=.08)
        profile_b=(.40<=area_ratio<=.85 and solidity<.94 and rectangularity<.86 and deep_count>=4 and deepest>=.07)
        # Extreme compound outline: catches touching/overlapping boards that merge
        # into one green contour. Requires a much deeper notch, so ordinary single
        # board edge irregularities do not earn a block merely for being irregular.
        profile_c=(.28<=area_ratio<=.88 and solidity<.90 and rectangularity<.80 and deep_count>=2 and deepest>=.12)
        suspicious=bool(two_regions or profile_a or profile_b or profile_c)
        result["metrics"]={"pcb_region_area_ratio":round(area_ratio,3),"solidity":round(solidity,3),"rectangularity":round(rectangularity,3),"deep_concavity_count":deep_count,"deepest_concavity_ratio":round(deepest,3),"independent_pcb_regions":len(sep_areas),"second_region_area_ratio":round(sep_areas[1]/area,3) if len(sep_areas)>1 else 0,"compound_profile_a":bool(profile_a),"compound_profile_b":bool(profile_b),"compound_profile_c":bool(profile_c),"two_region_trigger":bool(two_regions)}
        if suspicious:
            why=[]
            if two_regions: why.append("Two independently substantial PCB-like regions are visible in the same photograph.")
            if profile_a or profile_b or profile_c: why.append("The PCB-like silhouette has compound geometry consistent with touching or overlapping physical boards.")
            why.append("Board grading and blueprinting are withheld until one physical board is isolated.")
            result.update({"status":"MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED","block_analysis":True,"confidence":92 if two_regions else (88 if profile_c else 84),"evidence":why,"next_step":"Retake the photo with exactly one physical board in the frame, separated from other boards."})
        return result
    except Exception as exc:
        result["status"]="FRAME_GATE_UNCERTAIN"; result["error"]=str(exc); return result
