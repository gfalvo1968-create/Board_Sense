"""SPIKE Modification Detector v0.2.
Conservative screening for harvested/modified PCB features. Empty IC footprints
are inspection evidence, not proof: factory-unpopulated footprints are common.
"""
import cv2
import numpy as np

def _empty_ic_footprints(gray):
    """Find rectangular empty centers bordered by repeated bright solder pads."""
    h,w=gray.shape;_,bright=cv2.threshold(gray,185,255,cv2.THRESH_BINARY);contours,_=cv2.findContours(bright,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE);pads=[]
    for c in contours:
        x,y,cw,ch=cv2.boundingRect(c);a=cw*ch
        if 6<=a<=max(90,int(h*w*.00012)) and max(cw,ch)/max(1,min(cw,ch))<=4.5:pads.append((x+cw/2,y+ch/2,cw,ch))
    candidates=[]
    # Grid search around sparse image locations. A convincing footprint needs pads
    # on at least two opposing sides and a relatively quiet center.
    step=max(18,int(min(h,w)*.035));box=max(34,int(min(h,w)*.075))
    for cy in range(box,h-box,step):
        for cx in range(box,w-box,step):
            near=[p for p in pads if abs(p[0]-cx)<=box and abs(p[1]-cy)<=box]
            if len(near)<10:continue
            left=sum(1 for p in near if p[0]<cx-box*.35);right=sum(1 for p in near if p[0]>cx+box*.35);top=sum(1 for p in near if p[1]<cy-box*.35);bottom=sum(1 for p in near if p[1]>cy+box*.35)
            opposed=(left>=3 and right>=3) or (top>=3 and bottom>=3)
            if not opposed:continue
            r=max(5,int(box*.32));center=gray[max(0,cy-r):min(h,cy+r),max(0,cx-r):min(w,cx+r)]
            if center.size and float(np.std(center))<38:candidates.append({"x":cx-box,"y":cy-box,"w":box*2,"h":box*2,"pad_candidates":len(near)})
    # suppress overlapping grid hits
    kept=[]
    for c in candidates:
        if not any(abs(c["x"]-k["x"])<box and abs(c["y"]-k["y"])<box for k in kept):kept.append(c)
    return kept[:6]

def detect_modifications(image_path,result=None):
    image=cv2.imread(str(image_path))
    if image is None:return {"mode":"SPIKE Modification Detector v0.2","status":"not_evaluated","observations":{},"signals":[]}
    h,w=image.shape[:2];gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);observations={};signals=[]
    exposed=cv2.inRange(hsv,np.array([0,0,105]),np.array([179,85,245]));edges=cv2.Canny(gray,70,170);kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(5,3));candidate=cv2.morphologyEx(cv2.bitwise_and(exposed,edges),cv2.MORPH_CLOSE,kernel);contours,_=cv2.findContours(candidate,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);suspicious=[]
    for c in contours:
        x,y,cw,ch=cv2.boundingRect(c);area=cv2.contourArea(c);margin=max(4,int(min(h,w)*.012))
        if area<max(35,h*w*.00008) or x<=margin or y<=margin or x+cw>=w-margin or y+ch>=h-margin:continue
        elong=max(cw,ch)/max(1,min(cw,ch))
        if elong>=3:suspicious.append({"x":x,"y":y,"w":cw,"h":ch,"elongation":round(elong,1)})
    if suspicious:
        signals.append({"signal":"possible_cut_or_scraped_region","confidence":"low","count":len(suspicious[:8]),"regions":suspicious[:8],"meaning":"Possible exposed/cut PCB region. Requires visual confirmation before value deduction."});observations["board_modification"]={"status":"uncertain","value_impact":"unknown","note":"Vision found a possible cut/scraped region, but it is not confirmed harvesting."}
    empty=_empty_ic_footprints(gray)
    if empty:
        signals.append({"signal":"possible_empty_ic_footprint","confidence":"inspection","count":len(empty),"regions":empty,"meaning":"Repeated solder-pad geometry surrounds an apparently empty component center. Could be removed or factory-unpopulated; verify across views."});observations["possible_removed_component"]={"status":"uncertain","value_impact":"unknown","note":"Possible empty IC/component footprint detected. Do not call it harvested until another view, solder disturbance, or known-populated reference corroborates removal."}
    result=result or {};label=str(result.get("board_type","")).lower();sd=result.get("signals") or {};expected=any(k in label for k in ("edge-connector","expansion","ram","memory module"));fingers=bool(sd.get("gold_fingers") or sd.get("gold_finger_edge"))
    if expected and not fingers:observations["gold_finger_edge"]={"status":"expected_not_visible","value_impact":"high","note":"Board family commonly carries an edge connector, but gold fingers are not verified in this image. Inspect for cropping or harvesting before pricing."};signals.append({"signal":"expected_value_feature_not_verified","feature":"gold_finger_edge","confidence":"advisory"})
    status="inspection_needed" if observations else "no_visual_modification_signal"
    return {"mode":"SPIKE Modification Detector v0.2","status":status,"observations":observations,"signals":signals,"rule":"Empty footprints and possible absence are inspection evidence, not proof of harvesting. Only corroborated physical removal may reduce value."}
