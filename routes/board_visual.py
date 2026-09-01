# routes/board_visual.py
import cv2
import numpy as np

def _confirmed_gold_finger_geometry(gold_mask,width,height):
    """Require a regular row of similarly sized contacts running along one PCB edge."""
    band=max(6,int(min(width,height)*.065));sides={"top":gold_mask[:band,:],"bottom":gold_mask[-band:,:],"left":gold_mask[:,:band],"right":gold_mask[:,-band:]};best={"confirmed":False,"side":None,"count":0,"span":0.0,"spacing_cv":None,"size_cv":None}
    for side,roi in sides.items():
        roi=cv2.morphologyEx(roi,cv2.MORPH_OPEN,np.ones((2,2),np.uint8));contours,_=cv2.findContours(roi,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);items=[];rh,rw=roi.shape[:2];area=max(rw*rh,1)
        for c in contours:
            a=cv2.contourArea(c)
            if a<=0:continue
            x,y,w,h=cv2.boundingRect(c);ar=a/area;rect=a/max(1,w*h);aspect=max(w,h)/max(1,min(w,h))
            if not(.0002<=ar<=.04 and rect>=.52 and 1.25<=aspect<=7.0):continue
            # Card fingers normally extend inward from the edge, so their long axis
            # is perpendicular to that edge. Random solder/copper islands do not.
            perpendicular=(h>=w*1.2) if side in("top","bottom") else (w>=h*1.2)
            if not perpendicular:continue
            # Contact must actually reach the narrow perimeter band boundary.
            touches=(y<=2 if side=="top" else y+h>=rh-2 if side=="bottom" else x<=2 if side=="left" else x+w>=rw-2)
            if touches:items.append((x,y,w,h))
        if len(items)<5:continue
        centers=sorted([(x+w/2,y+h/2,w,h) for x,y,w,h in items],key=lambda p:p[0] if side in("top","bottom") else p[1]);axis=np.array([p[0] if side in("top","bottom") else p[1] for p in centers],dtype=float);spacing=np.diff(axis)
        if len(spacing)<4 or np.mean(spacing)<=0:continue
        spacing_cv=float(np.std(spacing)/max(np.mean(spacing),1e-6));sizes=np.array([min(p[2],p[3]) for p in centers],dtype=float);size_cv=float(np.std(sizes)/max(np.mean(sizes),1e-6));span=(axis.max()-axis.min())/max(width if side in("top","bottom") else height,1)
        if spacing_cv<=.55 and size_cv<=.45 and span>=.12:
            if len(items)>best["count"] or span>best["span"]:best={"confirmed":True,"side":side,"count":len(items),"span":round(float(span),3),"spacing_cv":round(spacing_cv,3),"size_cv":round(size_cv,3)}
    return best

def detect_visual_features(image_path):
    visual={"wide_skinny_board":False,"possible_ram":False,"gold_finger_edge":False,"gold_edge_color_cue":False,"gold_finger_geometry":False,"repeated_edge_contacts":False,"gold_contact_count":0,"gold_contact_side":None,"gold_contact_spacing_cv":None,"gold_contact_size_cv":None,"possible_large_ic_chips":False,"aspect_ratio":0.0,"gold_ratio":0.0,"dark_component_density":0.0,"large_dark_components":0}
    try:
        image=cv2.imread(image_path)
        if image is None:return visual
        height,width=image.shape[:2];long_side=max(width,height);short_side=min(width,height);ratio=long_side/short_side if short_side else 0.0;visual["aspect_ratio"]=round(float(ratio),3)
        if ratio>=2.4:visual["wide_skinny_board"]=True;visual["possible_ram"]=True
        hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);gold_mask=cv2.inRange(hsv,np.array([10,70,80],dtype=np.uint8),np.array([38,255,255],dtype=np.uint8));edge_band=max(1,int(min(width,height)*.18));edge_mask=np.zeros((height,width),dtype=np.uint8);edge_mask[:edge_band,:]=255;edge_mask[-edge_band:,:]=255;edge_mask[:,:edge_band]=255;edge_mask[:,-edge_band:]=255;edge_gold=cv2.bitwise_and(gold_mask,edge_mask);edge_pixels=max(int(np.count_nonzero(edge_mask)),1);gold_ratio=np.count_nonzero(edge_gold)/edge_pixels;visual["gold_ratio"]=round(float(gold_ratio),4);visual["gold_edge_color_cue"]=bool(gold_ratio>=.025)
        geom=_confirmed_gold_finger_geometry(gold_mask,width,height);visual["gold_finger_geometry"]=bool(geom["confirmed"]);visual["repeated_edge_contacts"]=bool(geom["confirmed"]);visual["gold_finger_edge"]=bool(geom["confirmed"]);visual["gold_contact_count"]=int(geom["count"]);visual["gold_contact_side"]=geom["side"];visual["gold_contact_spacing_cv"]=geom["spacing_cv"];visual["gold_contact_size_cv"]=geom["size_cv"]
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);_,dark_mask=cv2.threshold(gray,72,255,cv2.THRESH_BINARY_INV);dark_mask=cv2.morphologyEx(dark_mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8));contours,_=cv2.findContours(dark_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);image_area=max(width*height,1);qualifying_components=0;qualifying_area=0.0
        for contour in contours:
            a=cv2.contourArea(contour)
            if a<=0:continue
            ar=a/image_area
            if ar<.0015 or ar>.08:continue
            x,y,w,h=cv2.boundingRect(contour)
            if a/max(w*h,1)>=.55:qualifying_components+=1;qualifying_area+=a
        visual["large_dark_components"]=qualifying_components;visual["dark_component_density"]=round(float(qualifying_area/image_area),4);visual["possible_large_ic_chips"]=bool(qualifying_components>=2)
    except Exception as exc:print(f"[Board Visual Error] {exc}")
    return visual
