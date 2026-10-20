"""Visual component-family discrimination for Board Sense.

SPIKE Vision v1.6 keeps body-before-label filtering and conservative power cues.
Density-aware logic detection now preserves smaller legacy IC packages instead of
letting one large package represent an entire populated board.
"""
import cv2
import numpy as np
from routes.board_region import board_region_mask, region_on_board

def _board_mask(image):
    return board_region_mask(image)

def _package_body_support(gray,hsv,x,y,w,h):
    # A package needs an enclosed, mostly coherent face. Printed legends and
    # exposed connector pins can have repeating edges without a package body.
    px,py=max(1,int(w*.15)),max(1,int(h*.15));core=gray[y+py:y+h-py,x+px:x+w-px]
    if not core.size:return False
    median=float(np.median(core));coherent=float(np.mean(np.abs(core.astype(np.float32)-median)<=15))
    core_hsv=hsv[y+py:y+h-py,x+px:x+w-px]
    # Warm illumination shifts green solder mask toward yellow. Repeating
    # traces on that surface still need to be rejected as a package face.
    surface=cv2.inRange(core_hsv,np.array([14,70,22]),np.array([105,255,255]))
    if cv2.countNonZero(surface)/core.size>.45:return False
    texture=cv2.Canny(core,35,95)
    return coherent>=.65 and cv2.countNonZero(texture)/core.size<=.14

def _nested_die_support(gray,hsv,x,y,w,h):
    """Inspection-only nested face geometry; never establishes chip identity."""
    if max(w,h)/max(1,min(w,h))>1.4:return False
    face=gray[y:y+h,x:x+w];color=hsv[y:y+h,x:x+w]
    if face.size==0 or float(np.median(face))>=115:return False
    surface=cv2.inRange(color,np.array([14,70,22]),np.array([105,255,255]))
    if np.mean(surface>0)>.35:return False
    _,bright=cv2.threshold(face,max(110,float(np.median(face))+35),255,cv2.THRESH_BINARY)
    contours,_=cv2.findContours(bright,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        ix,iy,iw,ih=cv2.boundingRect(c);area=cv2.contourArea(c)
        if not (.04<=area/(w*h)<=.32 and area/max(1,iw*ih)>=.60):continue
        if max(iw,ih)/max(1,min(iw,ih))>1.4:continue
        if abs((ix+iw/2)/w-.5)>.18 or abs((iy+ih/2)/h-.5)>.18:continue
        if ix<w*.12 or iy<h*.12 or ix+iw>w*.88 or iy+ih>h*.88:continue
        if float(np.median(color[iy:iy+ih,ix:ix+iw,1]))>95:continue
        return True
    return False

def _pin_edge_support(gray,x,y,w,h):
    """Require repeated pin-like contrast along two opposing package sides."""
    ih,iw=gray.shape[:2];pad=max(3,int(min(w,h)*.08))
    bands=[gray[max(0,y-pad):min(ih,y+pad),x+pad:x+w-pad],gray[max(0,y+h-pad):min(ih,y+h+pad),x+pad:x+w-pad],gray[y+pad:y+h-pad,max(0,x-pad):min(iw,x+pad)],gray[y+pad:y+h-pad,max(0,x+w-pad):min(iw,x+w+pad)]]
    support=[]
    for i,band in enumerate(bands):
        if not band.size:support.append(False);continue
        profile=np.mean(band,axis=0 if i<2 else 1).astype(np.float32)
        profile=cv2.GaussianBlur(profile.reshape(1,-1),(3,1),0).ravel();std=float(np.std(profile));threshold=float(np.median(profile))+max(3,std*.25)
        peaks=[j for j in range(1,len(profile)-1) if profile[j]>profile[j-1] and profile[j]>=profile[j+1] and profile[j]>threshold]
        support.append(std>=5 and len(peaks)>=3 and (peaks[-1]-peaks[0])/max(1,len(profile))>=.35)
    return (support[0] and support[1]) or (support[2] and support[3])

def _overlap(a,b):
    iw=max(0,min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x']));ih=max(0,min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y']));intersection=iw*ih
    return intersection/max(1,a['w']*a['h']+b['w']*b['h']-intersection)

def _inside(mask,cx,cy,radius=0):
    h,w=mask.shape[:2];cx,cy=int(cx),int(cy)
    if cx<0 or cy<0 or cx>=w or cy>=h or mask[cy,cx]==0:return False
    if radius<=1:return True
    pts=[(cx+radius,cy),(cx-radius,cy),(cx,cy+radius),(cx,cy-radius)]
    return sum(1 for x,y in pts if mask[min(h-1,max(0,y)),min(w-1,max(0,x))])>=3

def _gold_ratio(hsv_roi):
    if hsv_roi.size==0:return 0.0
    gold=cv2.inRange(hsv_roi,np.array([8,70,65]),np.array([34,255,255]))
    return float(cv2.countNonZero(gold)/max(gold.size,1))

def _annular_hole_like(image,cx,cy,radius):
    """Withhold a dark open center bounded by a brighter annular rim.

    Relative contrast handles shaded holes that evade a fixed black threshold.
    This is an ambiguity veto, not a positive identification of hole chemistry.
    """
    left=max(0,int(cx-radius)-1);top=max(0,int(cy-radius)-1)
    right=min(image.shape[1],int(cx+radius)+2);bottom=min(image.shape[0],int(cy+radius)+2)
    gray=cv2.cvtColor(image[top:bottom,left:right],cv2.COLOR_BGR2GRAY)
    cx,cy=cx-left,cy-top
    theta=np.linspace(0,2*np.pi,72,endpoint=False).astype(np.float32)
    values=[]
    for factor in (.15,.30,.50,.65,.75):
        x=(cx+np.cos(theta)*radius*factor).astype(np.float32).reshape(1,-1)
        y=(cy+np.sin(theta)*radius*factor).astype(np.float32).reshape(1,-1)
        values.append(cv2.remap(gray,x,y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT).astype(np.float32).ravel())
    center=(values[0]+values[1])/2
    ring=np.median(np.stack(values[2:]),axis=0)
    return bool(np.median(center)<np.median(ring)*.70 and np.mean(ring-center>=25)>=.72)

def _round_body_support(image,cx,cy,radius):
    """Require a coherent circular rim, not scattered edges in a large disk."""
    height,width=image.shape[:2]
    if radius<4 or cx-radius<1 or cy-radius<1 or cx+radius>=width-1 or cy+radius>=height-1:return False
    if _annular_hole_like(image,cx,cy,radius):return False
    # Average short arcs on either side of the proposed rim. A real body
    # boundary produces a color transition across most angular sectors.
    theta=np.linspace(0,2*np.pi,108,endpoint=False).astype(np.float32)
    rings=[]
    for factor in (.87,.93,1.07,1.13):
        x=(cx+np.cos(theta)*radius*factor).astype(np.float32).reshape(1,-1)
        y=(cy+np.sin(theta)*radius*factor).astype(np.float32).reshape(1,-1)
        rings.append(cv2.remap(image,x,y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT).astype(np.float32))
    delta=((rings[0]+rings[1]-rings[2]-rings[3])/2).reshape(36,3,3).mean(axis=1)
    transition=np.linalg.norm(delta,axis=1)
    if np.mean(transition>=24)<.67:return False
    if np.linalg.norm(delta.mean(axis=0))/max(1,float(transition.mean()))<.60:return False
    # The strongest local transition should trace the proposed rim, rather
    # than unrelated parts scattered at different distances from the center.
    radii=np.linspace(.70,1.30,13,dtype=np.float32)
    mx=(cx+radius*radii[:,None]*np.cos(theta)[None,:]).astype(np.float32)
    my=(cy+radius*radii[:,None]*np.sin(theta)[None,:]).astype(np.float32)
    profile=cv2.remap(image,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    profile=profile.reshape(13,36,3,3).mean(axis=2)
    gradients=np.linalg.norm(np.diff(profile,axis=0),axis=2)
    strongest=gradients.argmax(axis=0)
    rim=(radii[:-1]+radii[1:])/2
    if np.mean((np.abs(rim[strongest]-1)<=.11)&(gradients.max(axis=0)>=15))<.72:return False
    # A dark open center surrounded by a rim is more consistent with a hole
    # than an independently supported capacitor top.
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    rr=max(2,int(radius*.35));core=gray[int(cy)-rr:int(cy)+rr+1,int(cx)-rr:int(cx)+rr+1]
    if np.mean(core<35)>.65:return False
    return True

def _contact_pattern_score(candidates,width,height):
    if len(candidates)<4:return 0.0
    pts=np.array([[c[0],c[1],c[2]] for c in candidates],dtype=float);radii=pts[:,2];mean_r=max(float(np.mean(radii)),1.0);radius_cv=float(np.std(radii)/mean_r);xs,ys=pts[:,0],pts[:,1];x_span=(xs.max()-xs.min())/max(width,1);y_span=(ys.max()-ys.min())/max(height,1);coherent=min(x_span,y_span)<=.28 or(x_span<=.58 and y_span<=.58);uniform=radius_cv<=.28;score=0.0
    if uniform:score+=.45
    if coherent:score+=.40
    if len(candidates)>=6:score+=.15
    return min(score,1.0)

def discriminate_components(image_path):
    result={"ic_like":0,"unverified_package_like":0,"capacitor_like":0,"contact_pad_like":0,"solder_joint_like":0,"solder_side_likelihood":0,"contact_pattern_score":0.0,"transformer_relay_like":0,"large_power_package_like":0,"magnetic_winding_like":0,"small_component_like":0,"uncertain_like":0,"dominant_family":"unknown","logic_component_ratio":0.0,"power_component_ratio":0.0,"regions":[],"notes":[]}
    try:
        image=cv2.imread(image_path)
        if image is None:return result
        oh,ow=image.shape[:2];scale=1.0
        if max(ow,oh)>1400:
            scale=1400.0/max(ow,oh);image=cv2.resize(image,(int(ow*scale),int(oh*scale)),interpolation=cv2.INTER_AREA)
        height,width=image.shape[:2];inv=1.0/scale;mask=_board_mask(image);board_area=max(cv2.countNonZero(mask),1);gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);blur=cv2.GaussianBlur(gray,(5,5),0);edges=cv2.Canny(blur,55,150)
        if not cv2.countNonZero(mask):
            result['notes'].append('Component regions withheld: PCB outline could not be isolated from the photo background.')
            return result

        # Slightly brighter threshold catches older matte plastic IC packages.
        _,dark=cv2.threshold(blur,90,255,cv2.THRESH_BINARY_INV)
        dark=cv2.bitwise_and(dark,mask);dark=cv2.morphologyEx(dark,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
        contours,_=cv2.findContours(dark,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        ic_like=block_like=power_package_like=small_like=uncertain_like=0;regions=[]

        for c in contours:
            area=cv2.contourArea(c)
            if area<=0:continue
            x,y,w,h=cv2.boundingRect(c);cx,cy=x+w//2,y+h//2
            if x==0 or y==0 or x+w>=width or y+h>=height or not region_on_board(mask,{'x':x,'y':y,'w':w,'h':h}):continue
            ar=area/board_area;rect=area/max(w*h,1);aspect=max(w,h)/max(min(w,h),1);roi=gray[y:y+h,x:x+w];roi_edges=edges[y:y+h,x:x+w];darkness=float(np.mean(roi<118)) if roi.size else 0.;ed=float(cv2.countNonZero(roi_edges)/max(roi_edges.size,1)) if roi_edges.size else 0.

            if .030<=ar<=.20 and rect>=.48 and aspect<=4.8 and darkness>=.48 and ed>=.035:
                power_package_like+=1;conf=min(88,int(50+rect*20+min(ed,.18)*65+min(ar,.10)*80));regions.append({"type":"Large power package / module candidate","x":int(x*inv),"y":int(y*inv),"w":int(w*inv),"h":int(h*inv),"confidence":conf})
            elif .00022<=ar<=.065 and rect>=.50 and aspect<=5.2 and darkness>=.42 and ed>=.025:
                # Legacy boards often contain many small plastic logic packages.
                # Count them even when individual confidence is modest, but only
                # render stronger regions on the blueprint.
                if not _package_body_support(gray,hsv,x,y,w,h) or not _pin_edge_support(gray,x,y,w,h):
                    uncertain_like+=1
                    continue
                ic_like+=1
                conf=min(92,int(45+rect*24+min(ed,.20)*85+min(darkness,.95)*12))
                if conf>=58:
                    regions.append({"type":"IC-like package","x":int(x*inv),"y":int(y*inv),"w":int(w*inv),"h":int(h*inv),"confidence":conf})
            elif .012<=ar<=.15 and rect>=.58 and aspect<=3.8 and darkness>=.28 and ed>=.045:
                block_like+=1;conf=min(86,int(47+rect*23+min(ed,.18)*60))
                if conf>=62:regions.append({"type":"Power block / transformer / relay-like","x":int(x*inv),"y":int(y*inv),"w":int(w*inv),"h":int(h*inv),"confidence":conf})
            elif .00005<=ar<.00022:
                small_like+=1
            elif .006<=ar<=.20 and rect>=.45:
                uncertain_like+=1

        # Dark solder mask can connect a chip body to nearby traces in a simple
        # threshold. Closed edge contours recover enclosed packages, with pin
        # geometry preventing PCB holes or printed rectangles becoming ICs.
        package_edges=cv2.Canny(cv2.GaussianBlur(gray,(3,3),0),35,95)
        for kernel_size in (3,7):
            closed=cv2.morphologyEx(package_edges,cv2.MORPH_CLOSE,np.ones((kernel_size,kernel_size),np.uint8))
            package_contours,_=cv2.findContours(closed,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
            for contour in package_contours:
                x,y,w,h=cv2.boundingRect(contour);a=cv2.contourArea(contour);ar=a/board_area;rect=a/max(1,w*h)
                if not (.001<=ar<=.15 and rect>=.65 and max(w,h)/max(1,min(w,h))<=4.8):continue
                if not region_on_board(mask,{'x':x,'y':y,'w':w,'h':h}):continue
                body_supported=_package_body_support(gray,hsv,x,y,w,h)
                pins_supported=_pin_edge_support(gray,x,y,w,h)
                mean_face=float(np.mean(gray[y:y+h,x:x+w]))
                if .002<=ar<=.065 and rect>=.80 and _nested_die_support(gray,hsv,x,y,w,h):
                    candidate={'type':'Exposed-die / package candidate','x':int(x*inv),'y':int(y*inv),'w':max(1,int(w*inv)),'h':max(1,int(h*inv)),'confidence':50,'geometry_guard':'Central light die-like area inside an enclosed dark package-like face. Connections, part family, and composition are unverified; paste or other features can imitate this geometry. Inspection only: excluded from IC counts and recovery points.'}
                    if not any(_overlap(candidate,r)>.42 for r in regions):regions.append(candidate)
                # An enclosed square face without visible opposing pins is an
                # inspection candidate, never a confirmed IC or recovery anchor.
                # High rectangularity excludes circular mounting-hole contours.
                if body_supported and not pins_supported and .002<=ar<=.065 and rect>=.88 and max(w,h)/max(1,min(w,h))<=1.65 and mean_face<150:
                    candidate={'type':'Unverified package-like region','x':int(x*inv),'y':int(y*inv),'w':max(1,int(w*inv)),'h':max(1,int(h*inv)),'confidence':50,'geometry_guard':'Enclosed package-like face; opposing pins are not confirmed. Hidden connections are possible, but this may be another rectangular feature. Excluded from IC counts, recovery points, and metal-yield claims.'}
                    if not any(_overlap(candidate,r)>.42 for r in regions):regions.append(candidate)
                if mean_face>=100 or not body_supported or not pins_supported:continue
                region={'type':'IC-like package','x':int(x*inv),'y':int(y*inv),'w':max(1,int(w*inv)),'h':max(1,int(h*inv)),'confidence':min(90,int(65+rect*25)),'geometry_guard':'Enclosed dark package with repeated pin-like edges on opposing sides; part markings and composition still require inspection.'}
                duplicate=next((r for r in regions if _overlap(region,r)>.42),None)
                if duplicate:
                    if duplicate['type']=='IC-like package':continue
                    if duplicate['type']=='Large power package / module candidate':power_package_like=max(0,power_package_like-1)
                    elif duplicate['type']=='Power block / transformer / relay-like':block_like=max(0,block_like-1)
                    regions.remove(duplicate)
                regions.append(region);ic_like+=1

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

        raw_solder_side_likelihood=solder_side_likelihood
        # Solder joints exist on populated faces too. Three independently
        # supported package bodies defeat a solder-only interpretation; retain
        # the raw cue for audit and keep each capacitor/winding geometry gate.
        component_face_supported=ic_like>=3
        if component_face_supported:solder_side_likelihood=min(solder_side_likelihood,64)
        result['side_context']={'raw_solder_pattern_score':raw_solder_side_likelihood,'component_face_supported':component_face_supported,'supported_ic_packages':ic_like,'status':'populated_or_mixed_face' if component_face_supported else ('solder_pattern_dominant' if solder_side_likelihood>=65 else 'unresolved'),'rule':'Solder patterns alone cannot suppress component candidates when multiple supported package bodies are present.'}
        winding_like=0
        if solder_side_likelihood<65:
            copper=cv2.inRange(hsv,np.array([4,90,55]),np.array([24,255,245]));copper=cv2.bitwise_and(copper,mask);copper=cv2.morphologyEx(copper,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8));cc,_=cv2.findContours(copper,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            for c in cc:
                area=cv2.contourArea(c);ar=area/board_area
                if not .0025<=ar<=.10:continue
                x,y,w,h=cv2.boundingRect(c);cx,cy=x+w//2,y+h//2
                if not _inside(mask,cx,cy):continue
                aspect=max(w,h)/max(1,min(w,h));rect=area/max(1,w*h)
                if aspect>5.0 or rect<.28:continue
                roi_edges=edges[y:y+h,x:x+w];edge_density=cv2.countNonZero(roi_edges)/max(1,roi_edges.size)
                if edge_density<.105:continue
                winding_like+=1;conf=min(88,int(56+edge_density*160+min(ar,.06)*120));regions.append({"type":"Copper-wound magnetic candidate","x":int(x*inv),"y":int(y*inv),"w":int(w*inv),"h":int(h*inv),"confidence":conf})
            winding_like=min(winding_like,4)

        raw_cap_candidates=len(caps)
        accepted_caps=[]
        package_regions=[q for q in regions if q['type'] in ('IC-like package','Unverified package-like region','Exposed-die / package candidate')]
        for candidate in sorted(caps,key=lambda c:c[2],reverse=True):
            cx,cy,r=candidate[:3]
            circle={'x':int((cx-r)*inv),'y':int((cy-r)*inv),'w':int(r*2*inv),'h':int(r*2*inv)}
            # Package geometry takes precedence over a circle fitted through
            # chip corners, die paste or nearby scattered components.
            if any(q['x']<=cx*inv<=q['x']+q['w'] and q['y']<=cy*inv<=q['y']+q['h'] for q in package_regions):continue
            if not region_on_board(mask,{'x':cx-r,'y':cy-r,'w':r*2,'h':r*2},minimum_coverage=.80):continue
            if not _round_body_support(image,cx,cy,r):continue
            if any(_overlap(circle,{'x':int((a[0]-a[2])*inv),'y':int((a[1]-a[2])*inv),'w':int(a[2]*2*inv),'h':int(a[2]*2*inv)})>.40 for a in accepted_caps):continue
            accepted_caps.append(candidate)
        caps=accepted_caps
        result['round_body_guard']={'raw_candidates':raw_cap_candidates,'supported_candidates':len(caps),'rejected_candidates':raw_cap_candidates-len(caps),'rule':'Round component candidates require a PCB-supported circular rim. Dark-center annular features, package-centered circles, and duplicate circles are withheld.'}
        caps=sorted(caps,key=lambda c:c[2],reverse=True)[:12];contacts=sorted(contacts,key=lambda c:c[2],reverse=True)[:24];suppressed_caps=0
        if solder_side_likelihood>=65 and caps:suppressed_caps=len(caps);caps=[]
        for cx,cy,r,ed,ms,mv in caps:
            conf=min(84,int(48+ed*150+min(10,r/max(min_r,1)*3)))
            if conf>=64:regions.append({"type":"Capacitor-like round component","x":int((cx-r)*inv),"y":int((cy-r)*inv),"w":int(r*2*inv),"h":int(r*2*inv),"confidence":conf})
        for cx,cy,r,ed,gold in contacts:
            conf=min(90,int(58+gold*45+pattern_score*18))
            if conf>=66:regions.append({"type":"Plated contact / keypad pad","x":int((cx-r)*inv),"y":int((cy-r)*inv),"w":int(r*2*inv),"h":int(r*2*inv),"confidence":conf})

        capacitor_like,contact_pad_like=len(caps),len(contacts)
        result.update({"ic_like":ic_like,"capacitor_like":capacitor_like,"contact_pad_like":contact_pad_like,"solder_joint_like":solder_count,"solder_side_likelihood":solder_side_likelihood,"contact_pattern_score":round(pattern_score,3),"transformer_relay_like":block_like,"large_power_package_like":power_package_like,"magnetic_winding_like":winding_like,"small_component_like":small_like,"uncertain_like":uncertain_like})
        result["unverified_package_like"]=sum(r["type"] in ("Unverified package-like region","Exposed-die / package candidate") for r in regions)
        result["regions"]=sorted(regions,key=lambda i:(i["confidence"],i["w"]*i["h"]),reverse=True)[:48]
        total=max(ic_like+capacitor_like+block_like+power_package_like+winding_like,1)
        result["logic_component_ratio"]=round(ic_like/total,3)
        result["power_component_ratio"]=round((capacitor_like+block_like+power_package_like+winding_like)/total,3)

        if component_face_supported and not (block_like or power_package_like or winding_like):
            # Round capacitor candidates alone do not prove power topology.
            result["dominant_family"]="logic_ic"
        elif ic_like>=4 and ic_like>capacitor_like+block_like+power_package_like+winding_like:
            result["dominant_family"]="logic_ic"
        elif capacitor_like+block_like+power_package_like+winding_like>=4 and capacitor_like+block_like+power_package_like+winding_like>ic_like*1.35:
            result["dominant_family"]="power_components"
        elif ic_like or capacitor_like or block_like or power_package_like or winding_like:
            result["dominant_family"]="mixed"

        result["notes"].append("SPIKE Vision v1.6 PCB-outline and package-body filtering is active.")
        if ic_like>=8:result["notes"].append(f"Dense logic population detected: {ic_like} IC-like package candidates.")
        if solder_side_likelihood>=65:result["notes"].append(f"PCB solder/trace-side pattern detected ({solder_side_likelihood}% likelihood); capacitor and copper-winding promotion is suppressed on this view.")
        if winding_like:result["notes"].append(f"Found {winding_like} copper-wound magnetic candidate(s) on a component-side-compatible view.")
        if suppressed_caps:result["notes"].append(f"Suppressed {suppressed_caps} round capacitor candidates because solder-side context was stronger.")
    except Exception as exc:
        print(f"[Component Discriminator Error] {exc}")
    return result
