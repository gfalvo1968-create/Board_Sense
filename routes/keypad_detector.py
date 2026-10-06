"""Repeated round contact-array evidence; never a phone model or metal assay."""
import cv2
import numpy as np


def detect_keypad(image_path):
    result = {"supported": False, "contact_count": 0, "model": "Keypad Array v0.1",
              "rule": "Round colored contacts indicate a keypad candidate, not gold mass or an exact device model."}
    image = cv2.imread(str(image_path))
    if image is None:
        return result
    scale = min(1.0, 1200/max(image.shape[:2]))
    image = cv2.resize(image, (int(image.shape[1]*scale), int(image.shape[0]*scale)))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    candidates = []
    # Several brightness levels keep shadowed and bright pads independent of
    # the green substrate; one threshold can connect pads to nearby traces.
    for brightness in (80, 100, 120, 140, 160):
        mask = cv2.inRange(hsv, np.array([5,65,brightness]), np.array([35,255,255]))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3,3),np.uint8))
        contours,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            x,y,w,h = cv2.boundingRect(contour)
            if not (.00025 < area/mask.size < .03 and
                    4*np.pi*area/max(1,perimeter*perimeter) > .60 and
                    max(w,h)/max(1,min(w,h)) < 1.4):
                continue
            candidates.append((x+w/2,y+h/2,float(np.sqrt(area/np.pi))))
    best = []
    for seed in candidates:
        similar = sorted((c for c in candidates if .80*seed[2] <= c[2] <= 1.20*seed[2]),
                         key=lambda c:c[2], reverse=True)
        unique = []
        for c in similar:
            if not any(np.hypot(c[0]-u[0],c[1]-u[1]) < .85*max(c[2],u[2]) for u in unique):
                unique.append(c)
        if len(unique) > len(best):
            best = unique
    if len(best) < 9:
        return result
    points = np.array(best)
    _,_,axes = np.linalg.svd(points[:,:2]-points[:,:2].mean(axis=0), full_matrices=False)
    projected = points[:,:2] @ axes.T
    spans = np.ptp(projected,axis=0)
    radius = float(np.median(points[:,2]))
    if min(spans) < 3*radius or max(spans)/max(1,min(spans)) > 8:
        return result
    distances = np.linalg.norm(points[:,None,:2]-points[None,:,:2],axis=2)
    np.fill_diagonal(distances,np.inf)
    neighbors = distances.min(axis=1)
    # A repeated pad bank needs comparable neighbor spacing. Scattered screw
    # holes or isolated metallic circles are insufficient.
    if float(np.std(neighbors)/max(1,np.mean(neighbors))) > .35:
        return result
    result.update(supported=True, contact_count=len(best),
                  contacts=[{"x":round(c[0]/scale,1),"y":round(c[1]/scale,1),
                             "radius":round(c[2]/scale,1)} for c in best],
                  evidence="At least nine similarly sized round contacts form a repeated two-dimensional keypad-like bank.")
    return result
