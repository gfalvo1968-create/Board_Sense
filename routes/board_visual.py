# routes/board_visual.py
import cv2
import numpy as np

def _confirmed_gold_finger_geometry(gold_mask,width,height):
    """Require repeated contact-like gold regions aligned on one narrow PCB edge."""
    band=max(6,int(min(width,height)*.08));sides={"top":gold_mask[:band,:],"bottom":gold_mask[-band:,:],"left":gold_mask[:,:band],"right":gold_mask[:,-band:]}
    best={"confirmed":False,"side":None,"count":0,"span":0.0}
    for side,roi in sides.items():
        roi=cv2.morphologyEx(roi,cv2.MORPH_OPEN,np.ones((2,2),np.uint8));contours,_=cv2.findContours(roi,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);items=[]
        rh,rw=roi.shape[:2];area=max(rw*rh,1)
        for c in contours:
            a=cv2.contourArea(c)
            if a<=0:continue
            x,y,w,h=cv2.boundingRect(c);ar=a/area;aspect=max(w,h)/max(1,min(w,h));rect=a/max(1,w*h)
            # Edge fingers are repeated compact/elongated contacts, not one broad stain.
            if .00015<=ar<=.08 and 1.15<=aspect<=8.0 and rect>=.45:items.append((x,y,w,h))
        if len(items)<4:continue
        centers=[(x+w/2,y+h/2) for x,y,w,h in items]
        if side in("top","bottom"):
            vals=[p[0] for p in centers];span=(max(vals)-min(vals))/max(width,1)
        else:
            vals=[p[1] for p in centers];span=(max(vals)-min(vals))/max(height,1)
        if len(items)>=4 and span>=.10 and (len(items)>best["count"] or span>best["span"]):best={"confirmed":True,"side":side,"count":len(items),"span":round(float(span),3)}
    return best

def detect_visual_features(image_path):
    """Extract visual evidence directly from the uploaded board image."""
    visual={"wide_skinny_board":False,"possible_ram":False,"gold_finger_edge":False,"gold_edge_color_cue":False,"gold_finger_geometry":False,"repeated_edge_contacts":False,"gold_contact_count":0,"gold_contact_side":None,"possible_large_ic_chips":False,"aspect_ratio":0.0,"gold_ratio":0.0,"dark_component_density":0.0,"large_dark_components":0}
    try:
        image=cv2.imread(image_path)
        if image is None:return visual
        height,width=image.shape[:2];long_side=max(width,height);short_side=min(width,height);ratio=long_side/short_side if short_side else 0.0;visual["aspect_ratio"]=round(float(ratio),3)
        if ratio>=2.4:visual["wide_skinny_board"]=True;visual["possible_ram"]=True
        hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);gold_lower=np.array([10,70,80],dtype=np.uint8);gold_upper=np.array([38,255,255],dtype=np.uint8);gold_mask=cv2.inRange(hsv,gold_lower,gold_upper)
        edge_band=max(1,int(min(width,height)*.18));edge_mask=np.zeros((height,width),dtype=np.uint8);edge_mask[:edge_band,:]=255;edge_mask[-edge_band:,:]=255;edge_mask[:,:edge_band]=255;edge_mask[:,-edge_band:]=255;edge_gold=cv2.bitwise_and(gold_mask,edge_mask);edge_pixels=max(int(np.count_nonzero(edge_mask)),1);gold_ratio=np.count_nonzero(edge_gold)/edge_pixels;visual["gold_ratio"]=round(float(gold_ratio),4);visual["gold_edge_color_cue"]=bool(gold_ratio>=.025)
        geom=_confirmed_gold_finger_geometry(gold_mask,width,height);visual["gold_finger_geometry"]=bool(geom["confirmed"]);visual["repeated_edge_contacts"]=bool(geom["confirmed"]);visual["gold_finger_edge"]=bool(geom["confirmed"]);visual["gold_contact_count"]=int(geom["count"]);visual["gold_contact_side"]=geom["side"]
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);_,dark_mask=cv2.threshold(gray,72,255,cv2.THRESH_BINARY_INV);dark_mask=cv2.morphologyEx(dark_mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8));contours,_=cv2.findContours(dark_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);image_area=max(width*height,1);qualifying_components=0;qualifying_area=0.0
        for contour in contours:
            area=cv2.contourArea(contour)
            if area<=0:continue
            area_ratio=area/image_area
            if area_ratio<.0015 or area_ratio>.08:continue
            x,y,w,h=cv2.boundingRect(contour);rectangularity=area/max(w*h,1)
            if rectangularity>=.55:qualifying_components+=1;qualifying_area+=area
        visual["large_dark_components"]=qualifying_components;visual["dark_component_density"]=round(float(qualifying_area/image_area),4)
        if qualifying_components>=2:visual["possible_large_ic_chips"]=True
    except Exception as exc:print(f"[Board Visual Error] {exc}")
    return visual
