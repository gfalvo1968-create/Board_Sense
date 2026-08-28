# routes/board_motherboard.py

import cv2
import numpy as np


def detect_motherboard(image_path):
    """Conservative structural motherboard detector with blueprint regions."""
    signals = {
        "large_board": False, "possible_motherboard": False,
        "motherboard_structure_score": 0, "long_slot_candidates": 0,
        "parallel_slot_bank": False, "edge_connector_bank": False,
        "structural_evidence": [], "structure_regions": [],
    }
    try:
        image = cv2.imread(image_path)
        if image is None: return signals
        h, w = image.shape[:2]
        long_side, short_side = max(w, h), min(w, h)
        ratio = long_side / max(short_side, 1)
        image_area = max(w*h, 1)
        large_board = ratio < 2.2 and long_side > 700
        signals["large_board"] = large_board
        if large_board: signals["structural_evidence"].append("motherboard-scale rectangular board footprint")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5,5), 0), 55, 145)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        slots = []
        for c in contours:
            x,y,cw,ch = cv2.boundingRect(c)
            area_ratio = (cw*ch)/image_area
            aspect = max(cw,ch)/max(min(cw,ch),1)
            if 4.5 <= aspect <= 24 and .0025 <= area_ratio <= .055 and max(cw,ch) >= int(long_side*.16):
                slots.append((x,y,cw,ch))

        kept=[]
        for x,y,cw,ch in sorted(slots, key=lambda r:r[2]*r[3], reverse=True):
            cx,cy=x+cw//2,y+ch//2
            if all(abs(cx-(px+pw//2)) > long_side*.035 or abs(cy-(py+ph//2)) > long_side*.035 for px,py,pw,ph in kept):
                kept.append((x,y,cw,ch))
        kept=kept[:8]
        slot_count=len(kept)
        signals["long_slot_candidates"]=slot_count
        signals["parallel_slot_bank"]=slot_count>=2
        if slot_count>=2:
            signals["structural_evidence"].append(f"{slot_count} repeated long slot/socket structures")
            for x,y,cw,ch in kept[:4]:
                signals["structure_regions"].append({"x":x,"y":y,"w":cw,"h":ch,"type":"Motherboard slot / socket bank","confidence":90})

        edge_band=int(min(w,h)*.16); edge_boxes=[]
        for c in contours:
            x,y,cw,ch=cv2.boundingRect(c)
            if cw*ch < image_area*.0015: continue
            near=x<edge_band or y<edge_band or x+cw>w-edge_band or y+ch>h-edge_band
            aspect=max(cw,ch)/max(min(cw,ch),1)
            if near and 1.0<=aspect<=5.5: edge_boxes.append((x,y,cw,ch))
        signals["edge_connector_bank"]=len(edge_boxes)>=4
        if signals["edge_connector_bank"]:
            signals["structural_evidence"].append("dense rectangular connector structures along a board edge")
            xs=[b[0] for b in edge_boxes]; ys=[b[1] for b in edge_boxes]
            x2=[b[0]+b[2] for b in edge_boxes]; y2=[b[1]+b[3] for b in edge_boxes]
            signals["structure_regions"].append({"x":min(xs),"y":min(ys),"w":max(x2)-min(xs),"h":max(y2)-min(ys),"type":"Rear I/O / connector bank","confidence":88})

        score=(2 if large_board else 0)+(4 if slot_count>=2 else 0)+(2 if slot_count>=4 else 0)+(3 if signals["edge_connector_bank"] else 0)
        signals["motherboard_structure_score"]=score
        signals["possible_motherboard"]=bool(large_board and (slot_count>=2 or signals["edge_connector_bank"]) and score>=6)
    except Exception as e:
        print(f"[Motherboard Detector Error] {e}")
    return signals
