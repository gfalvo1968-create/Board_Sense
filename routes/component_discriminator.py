"""Visual component-family discrimination for Board Sense.

SPIKE Vision v0.8 keeps body-before-label filtering and adds a conservative
large-package cue for power-stage reasoning. A large dark package is not called a
power device by itself; it is exposed only as corroborating evidence for topology.
"""
import cv2
import numpy as np

def _board_mask(image):
    h,w=image.shape[:2];gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);band_h,band_w=max(2,h//20),max(2,w//20);border=np.concatenate([gray[:band_h,:].ravel(),gray[-band_h:,:].ravel(),gray[:,:band_w].ravel(),gray[:,-band_w:].ravel()]);bg=int(np.median(border));diff=cv2.absdiff(gray,np.full_like(gray,bg));_,fg=cv2.threshold(diff,22,255,cv2.THRESH_BINARY);fg=cv2.morphologyEx(fg,cv2.MORPH_CLOSE,np.ones((13,13),np.uint8));contours,_=cv2.findContours(fg,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if not contours:return np.full((h,w),255,dtype=np.uint8)
    mask=np.zeros((h,w),dtype=np.uint8);cv2.drawContours(mask,[max(contours,key=cv2.contourArea)],-1,255,-1);return cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((19,19),np.uint8))
def _inside(mask,cx,cy,radius=0):
    h,w=mask.shape[:2];cx,cy=int(cx),int(cy)
    if cx<0 or cy<0 or cx>=w or cy>=h or mask[cy,cx]==0:return False
    if radius<=1:return True
    pts=[(cx+radius,cy),(cx-radius,cy),(cx,cy+radius),(cx,cy-radius)];return sum(1 for x,y in pts if mask[min(h-1,max(0,y)),min(w-1,max(0,x))])>=3
def _gold_ratio(hsv_roi):
    if hsv_roi.size==0:return 0.0
    gold=cv2.inRange(hsv_roi,np.array([8,70,65]),np.array([34,255,255]));return float(cv2.countNonZero(gold)/max(gold.size,1))
def _contact_pattern_score(candidates,width,height):
    if len(candidates)<4:return 0.0
    pts=np.array([[c[0],c[1],c[2]] for c in candidates],dtype=float);radii=pts[:,2];mean_r=max(float(np.mean(radii)),1.0);radius_cv=float(np.std(radii)/mean_r);xs,ys=pts[:,0],pts[:,1];x_span=(xs.max()-xs.min())/max(width,1);y_span=(ys.max()-ys.min())/max(height,1);coherent=min(x_span,y_span)<=.28 or(x_span<=.58 and y_span<=.58);uniform=radius_cv<=.28;score=0.0
    if uniform:score+=.45
    if coherent:score+=.40
    if len(candidates)>=6:score+=.15
    return min(score,1.0)
def discriminate_components(image_path):
    result={"ic_like":0,"capacitor_like":0,"contact_pad_like":0,"solder_joint_like":0,"solder_side_likelihood":0,"contact_pattern_score":0.0,"transformer_relay_like":0,"large_power_package_like":0,"small_component_like":0,"uncertain_like":0,"dominant_family":"unknown","logic_component_ratio":0.0,"power_component_ratio":0.0,"regions":[],"notes":[]}
    try:
        image=cv2.imread(image_path)
        if image is None:return result
        oh,ow=image.shape[:2];scale=1.0
        if max(ow,oh)>1400:scale=1400.0/max(ow,oh);image=cv2.resize(image,(int(ow*scale),int(oh*scale)),interpolation=cv2.INTER_AREA)
        height,width=image.shape[:2];inv=1.0/scale;mask=_board_mask(image);board_area=max(cv2.countNonZero(mask),1);gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);blur=cv2.GaussianBlur(gray,(5,5),0);edges=cv2.Canny(blur,60,155)
        _,dark=cv2.threshold(blur,82,255,cv2.THRESH_BINARY_INV);dark=cv2.bitwise_and(dark,mask);dark=cv2.morphologyEx(dark,cv2.MORPH_OPEN,np.ones((3,3),np.uint8));contours,_=cv2.findContours(dark,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);ic_like=block_like=power_package_like=small_like=uncertain_like=0;regions=[]
        for c in contours:
            area=cv2.contourArea(c)
            if area<=0:continue
            x,y,w,h=cv2.boundingRect(c);cx,cy=x+w//2,y+h//2
            if not _inside(mask,cx,cy):continue
            ar=area/board_area;rect=area/max(w*h,1);aspect=max(w,h)/max(min(w,h),1);roi=gray[y:y+h,x:x+w];roi_edges=edges[y:y+h,x:x+w];darkness=float(np.mean(roi<108)) if roi.size else 0.;ed=float(cv2.countNonZero(roi_edges)/max(roi_edges.size,1)) if roi_edges.size else 0.
            # Very large dark rectangular packages are exposed as a generic power-
            # package cue. This does not name the part and is never sufficient by
            # itself for a power-board call.
            if .030<=ar<=.20 and rect>=.48 and aspect<=4.8 and darkness>=.48 and ed>=.035:
                power_package_like+=1;conf=min(88,int(50+rect*20+min(ed,.18)*65+min(ar,.10)*80));regions.append({"type":"Large power package / module candidate","x":int(x*inv),"y":int(y*inv),"w":int(w*inv),"h":int(h*inv),"confidence":conf})
            elif .001<=ar<=.040 and rect>=.70 and aspect<=3.6 and darkness>=.58 and ed>=.05:
                ic_like+=1;conf=min(91,int(52+rect*24+min(ed,.18)*70))
                if conf>=62:regions.append({"type":"IC-like package","x":int(x*inv),"y":int(y*inv),"w":int(w*inv),"h":int(h*inv),"confidence":conf})
            elif .012<=ar<=.15 and rect>=.58 and aspect<=3.8 and darkness>=.28 and ed>=.045:
                block_like+=1;conf=min(86,int(47+rect*23+min(ed,.18)*60))
                if conf>=62:regions.append({"type":"Power block / transformer / relay-like","x":int(x*inv),"y":int(y*inv),"w":int(w*inv),"h":int(h*inv),"confidence":conf})
            elif .00008<=ar<.001:small_like+=1
            elif .008<=ar<=.20 and rect>=.50:uncertain_like+=1
        circle_blur=cv2.GaussianBlur(gray,(9,9),1.5);min_r=max(5,int(min(width,height)*.008));max_r=max(min_r+2,int(min(width,height)*.065));circles=cv2.HoughCircles(circle_blur,cv2.HOUGH_GRADIENT,dp=1.2,minDist=max(16,min_r*2.4),param1=115,param2=30,minRadius=min_r,maxRadius=max_r);caps=[];contacts=[];solder=[]
        if circles is not None:
            for cx,cy,r in np.round(circles[0]).astype(int):
                if not _inside(mask,cx,cy,max(2,int(r*.7))):continue
                x1,y1,x2,y2=max(0,cx-r),max(0,cy-r),min(width,cx+r+1),min(height,cy+r+1);rg=gray[y1:y2,x1:x2];rh=hsv[y1:y2,x1:x2];re=edges[y1:y2,x1:x2]
                if rg.size==0:continue
                ed=cv2.countNonZero(re)/max(re.size,1);mean_v=float(np.mean(rh[:,:,2]));mean_s=float(np.mean(rh[:,:,1]));gold=_gold_ratio(rh)
                if ed<.075:continue
                metallic_solder=mean_v>=135 and mean_s<=72 and gold<.20
                if metallic_solder:solder.append((cx,cy,r,ed));continue
                if gold>=.34 and mean_s>=62:contacts.append((cx,cy,r,ed,gold));continue
                body_like=r>=int(min_r*1.25) and ed>=.12 and(mean_s>=28 or mean_v<150) and not(mean_v>175 and mean_s<90)
                if body_like:caps.append((cx,cy,r,ed,mean_s,mean_v))
        pattern_score=_contact_pattern_score(contacts,width,height)
        if pattern_score<.60:contacts=[]
        solder_count=min(len(solder),80);board_edge_density=cv2.countNonZero(cv2.bitwise_and(edges,mask))/max(board_area,1);solder_side_likelihood=int(min(100,solder_count*2+max(0,board_edge_density-.06)*240))
        if solder_count>=10 and board_edge_density>=.055:solder_side_likelihood=max(solder_side_likelihood,72)
        suppressed_caps=0
        if solder_side_likelihood>=65 and caps:suppressed_caps=len(caps);caps=[]
        caps=sorted(caps,key=lambda c:c[2],reverse=True)[:12];contacts=sorted(contacts,key=lambda c:c[2],reverse=True)[:24]
        for cx,cy,r,ed,ms,mv in caps:
            conf=min(84,int(48+ed*150+min(10,r/max(min_r,1)*3)))
            if conf>=64:regions.append({"type":"Capacitor-like round component","x":int((cx-r)*inv),"y":int((cy-r)*inv),"w":int(r*2*inv),"h":int(r*2*inv),"confidence":conf})
        for cx,cy,r,ed,gold in contacts:
            conf=min(90,int(58+gold*45+pattern_score*18))
            if conf>=66:regions.append({"type":"Plated contact / keypad pad","x":int((cx-r)*inv),"y":int((cy-r)*inv),"w":int(r*2*inv),"h":int(r*2*inv),"confidence":conf})
        capacitor_like,contact_pad_like=len(caps),len(contacts);result.update({"ic_like":ic_like,"capacitor_like":capacitor_like,"contact_pad_like":contact_pad_like,"solder_joint_like":solder_count,"solder_side_likelihood":solder_side_likelihood,"contact_pattern_score":round(pattern_score,3),"transformer_relay_like":block_like,"large_power_package_like":power_package_like,"small_component_like":small_like,"uncertain_like":uncertain_like});result["regions"]=sorted(regions,key=lambda i:(i["confidence"],i["w"]*i["h"]),reverse=True)[:24];total=max(ic_like+capacitor_like+block_like+power_package_like,1);result["logic_component_ratio"]=round(ic_like/total,3);result["power_component_ratio"]=round((capacitor_like+block_like+power_package_like)/total,3)
        if ic_like>=3 and ic_like>capacitor_like+block_like+power_package_like:result["dominant_family"]="logic_ic"
        elif capacitor_like+block_like+power_package_like>=4 and capacitor_like+block_like+power_package_like>ic_like*1.35:result["dominant_family"]="power_components"
        elif ic_like or capacitor_like or block_like or power_package_like:result["dominant_family"]="mixed"
        result["notes"].append("SPIKE Vision v0.8 body-before-label filtering is active.")
        if power_package_like:result["notes"].append(f"Found {power_package_like} large package/module candidate(s); these are topology cues only and require corroborating power components before a power-stage call.")
        if solder_side_likelihood>=65:result["notes"].append(f"PCB solder/trace-side pattern detected ({solder_side_likelihood}% likelihood); round metallic features were not promoted to capacitor bodies.")
        if suppressed_caps:result["notes"].append(f"Suppressed {suppressed_caps} round capacitor candidates because solder-side context was stronger.")
        if contacts:result["notes"].append(f"Accepted {len(contacts)} intentional plated/contact pads with pattern score {pattern_score:.2f}.")
        if uncertain_like:result["notes"].append(f"Suppressed {uncertain_like} weak rectangular candidates rather than naming them confidently.")
    except Exception as exc:print(f"[Component Discriminator Error] {exc}")
    return result
