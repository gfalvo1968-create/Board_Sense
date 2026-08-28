"""Conservative first-stage object gate for Board Sense.

SPIKE Object Gate v0.3 answers whether an upload is a PCB, loose component, or
unknown. PCB construction is now judged from structure first, not solder-mask
color, so tan/brown, blue, red and black boards can pass alongside green boards.
"""

import cv2
import numpy as np
from routes.component_discriminator import discriminate_components


def _largest_foreground(gray):
    h, w = gray.shape[:2]
    border = np.concatenate([
        gray[:max(2,h//20),:].ravel(), gray[-max(2,h//20):,:].ravel(),
        gray[:,:max(2,w//20)].ravel(), gray[:,-max(2,w//20):].ravel()
    ])
    bg = float(np.median(border))
    diff = cv2.absdiff(gray, np.full_like(gray, int(bg)))
    _, mask = cv2.threshold(diff, 22, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9,9),np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3,3),np.uint8))
    contours,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None,0.0
    c=max(contours,key=cv2.contourArea)
    return c,float(cv2.contourArea(c)/max(h*w,1))


def _pcb_color_ratio(hsv):
    """Broad solder-mask/substrate support only. Never used as sole proof."""
    masks = [
        cv2.inRange(hsv,np.array([28,35,20]),np.array([105,255,255])),  # green
        cv2.inRange(hsv,np.array([90,35,20]),np.array([135,255,255])),  # blue
        cv2.inRange(hsv,np.array([0,35,20]),np.array([12,255,255])),    # red/brown low hue
        cv2.inRange(hsv,np.array([8,25,20]),np.array([30,220,230])),    # tan/brown
    ]
    dark = cv2.inRange(hsv,np.array([0,0,0]),np.array([179,255,72]))    # black mask/substrate
    combined = dark.copy()
    for m in masks:
        combined = cv2.bitwise_or(combined,m)
    return float(cv2.countNonZero(combined)/max(combined.size,1))


def classify_object(image_path):
    result={"mode":"unknown","label":"Unknown object","confidence":35,
            "board_likelihood":0,"component_likelihood":0,"camera_module_likelihood":0,
            "evidence":[],"message":"Not enough evidence to run board grading safely."}
    try:
        image=cv2.imread(image_path)
        if image is None:
            result["message"]="Image could not be read."
            return result
        h0,w0=image.shape[:2]
        if max(h0,w0)>1200:
            s=1200.0/max(h0,w0)
            image=cv2.resize(image,(max(1,int(w0*s)),max(1,int(h0*s))),interpolation=cv2.INTER_AREA)
        h,w=image.shape[:2]; area=max(h*w,1)
        hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        edges=cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),55,145)
        edge_ratio=float(cv2.countNonZero(edges)/area)
        color_ratio=_pcb_color_ratio(hsv)

        foreground,foreground_ratio=_largest_foreground(gray)
        bbox_aspect=bbox_fill=0.0; compact=False; rectangularity=0.0
        if foreground is not None:
            x,y,bw,bh=cv2.boundingRect(foreground)
            bbox_aspect=max(bw,bh)/max(min(bw,bh),1)
            bbox_fill=(bw*bh)/area
            rectangularity=cv2.contourArea(foreground)/max(bw*bh,1)
            compact=bbox_aspect<=1.8 and bbox_fill<=0.38

        comps=discriminate_components(image_path)
        ic=int(comps.get("ic_like",0)); cap=int(comps.get("capacitor_like",0))
        contact=int(comps.get("contact_pad_like",0)); block=int(comps.get("transformer_relay_like",0))
        solder=int(comps.get("solder_joint_like",0)); solder_side=int(comps.get("solder_side_likelihood",0))
        major=ic+cap+block

        # Structural PCB evidence. Color helps, but no color is mandatory.
        board_score=0
        if foreground_ratio>=0.28: board_score+=22
        elif foreground_ratio>=0.12: board_score+=14
        elif foreground_ratio>=0.05: board_score+=7
        if edge_ratio>=0.075: board_score+=22
        elif edge_ratio>=0.045: board_score+=15
        elif edge_ratio>=0.025: board_score+=8
        if rectangularity>=0.50 and foreground_ratio>=0.10: board_score+=10
        if major>=4: board_score+=18
        elif major>=2: board_score+=12
        elif major>=1: board_score+=6
        if solder_side>=70: board_score+=22
        elif solder_side>=50: board_score+=13
        if solder>=10: board_score+=8
        if contact>=4: board_score+=6
        if color_ratio>=0.22: board_score+=12
        elif color_ratio>=0.10: board_score+=7

        # Rescue visibly board-scale circuitry even if mask/substrate color is odd.
        structural_rescue = foreground_ratio>=0.16 and edge_ratio>=0.045 and (major>=2 or solder_side>=55)
        if structural_rescue: board_score+=12
        board_score=min(board_score,100)

        component_score=0
        if 0.003<=foreground_ratio<=0.38: component_score+=34
        if compact: component_score+=18
        if edge_ratio>=0.01: component_score+=8
        if major<=1 and solder_side<35: component_score+=12
        if foreground_ratio<0.10: component_score+=10
        component_score=min(component_score,100)

        blur=cv2.GaussianBlur(gray,(9,9),1.6)
        min_r=max(5,int(min(h,w)*0.012)); max_r=max(min_r+2,int(min(h,w)*0.11))
        circles=cv2.HoughCircles(blur,cv2.HOUGH_GRADIENT,dp=1.2,minDist=max(18,min_r*2),param1=100,param2=26,minRadius=min_r,maxRadius=max_r)
        circle_count=0 if circles is None else len(circles[0])
        camera_score=0
        if component_score>=55 and compact: camera_score+=35
        if circle_count>=1: camera_score+=35
        if bbox_aspect and bbox_aspect<=1.45: camera_score+=10
        if board_score>=55 or solder_side>=50 or major>=3: camera_score-=30
        camera_score=max(0,min(camera_score,100))

        result.update({"board_likelihood":int(board_score),"component_likelihood":int(component_score),
                       "camera_module_likelihood":int(camera_score),
                       "metrics":{"pcb_color_support_ratio":round(color_ratio,4),"foreground_ratio":round(foreground_ratio,4),
                                  "edge_ratio":round(edge_ratio,4),"foreground_rectangularity":round(rectangularity,3),
                                  "circle_count":int(circle_count),"ic_like":ic,"capacitor_like":cap,
                                  "contact_pad_like":contact,"solder_joint_like":solder,
                                  "solder_side_likelihood":solder_side,"power_block_like":block}})

        if board_score>=58 and board_score>=component_score+3:
            result["mode"]="board"; result["label"]="Circuit board / PCB"; result["confidence"]=max(60,min(97,board_score))
            ev=[]
            if foreground_ratio>=0.12: ev.append("Board-scale foreground geometry detected")
            if edge_ratio>=0.025: ev.append("Circuit-detail edge density supports PCB construction")
            if major: ev.append(f"Electronic component population detected ({major} major candidates)")
            if solder_side>=55: ev.append(f"PCB solder/trace-side pattern detected ({solder_side}% likelihood)")
            if color_ratio>=0.10: ev.append("PCB substrate/solder-mask color support detected")
            result["evidence"]=ev or ["Multiple PCB construction signals agree"]
            result["message"]="Board evidence is strong enough to continue into Board Sense grading."
            return result

        if camera_score>=65:
            result.update({"mode":"component","label":"Phone camera / optical module","confidence":max(65,min(94,camera_score)),
                           "evidence":["Compact loose electronic module detected","Circular lens-like structure detected","Insufficient whole-PCB structural evidence"],
                           "message":"Component mode selected; board-specific grading was intentionally skipped."})
            return result
        if component_score>=58 and board_score<55:
            result.update({"mode":"component","label":"Loose electronic component / module","confidence":max(58,min(90,component_score)),
                           "evidence":["Compact foreground object detected","Insufficient whole-PCB structural evidence"],
                           "message":"Component mode selected; board-specific grading was intentionally skipped."})
            return result
        result["confidence"]=max(30,min(57,max(board_score,component_score)))
        result["evidence"]=["Input does not yet meet the confidence threshold for board or component mode."]
        return result
    except Exception as exc:
        print(f"[Object Gate Error] {exc}")
        result["message"]="Object gate could not classify the image safely."
        return result
