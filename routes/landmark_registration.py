"""Experimental same-face registration; never authorizes merging or grading."""
import cv2
import numpy as np

def compare_landmarks(image_a, image_b, mask_a, mask_b):
    """Compare features inside independently established PCB masks only.

    Matching evidence is diagnostic, not proof of unique physical identity.
    Opposite faces, identical manufactured boards and ambiguous masks require
    separate validation. No user confirmation or grade is changed here.
    """
    result={"supported":False,"matches":0,"inliers":0,"inlier_ratio":0.0,
            "coverage_a":0.0,"coverage_b":0.0,"inspection_only":True}
    if image_a is None or image_b is None or mask_a is None or mask_b is None:
        return result
    def features(image,mask):
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image
        if mask.shape!=gray.shape or mask.dtype!=np.uint8 or not np.any(mask):
            return [],None
        mask=cv2.erode(mask,np.ones((7,7),np.uint8))
        return cv2.ORB_create(nfeatures=1800).detectAndCompute(gray,mask)
    ka,da=features(image_a,mask_a)
    kb,db=features(image_b,mask_b)
    if da is None or db is None or min(len(ka),len(kb))<24:
        return result
    bf=cv2.BFMatcher(cv2.NORM_HAMMING)
    def good(x,y):
        return {(m.queryIdx,m.trainIdx) for pair in bf.knnMatch(x,y,k=2)
                if len(pair)==2 for m,n in [pair] if m.distance<.70*n.distance}
    forward=good(da,db)
    backward=good(db,da)
    pairs=sorted((i,j) for i,j in forward if (j,i) in backward)
    result["matches"]=len(pairs)
    if len(pairs)<24:
        return result
    pa=np.float32([ka[i].pt for i,j in pairs])
    pb=np.float32([kb[j].pt for i,j in pairs])
    matrix,flags=cv2.findHomography(pa,pb,cv2.RANSAC,3.0)
    if matrix is None or flags is None or not np.isfinite(matrix).all():
        return result
    selected=flags.ravel().astype(bool)
    n=int(selected.sum())
    result["inliers"]=n
    result["inlier_ratio"]=round(n/len(pairs),3)
    if n<24:
        return result
    for label,pts,mask in (("a",pa,mask_a),("b",pb,mask_b)):
        hull=cv2.convexHull(pts[selected])
        result["coverage_"+label]=round(cv2.contourArea(hull)/max(1,cv2.countNonZero(mask)),3)
    result["supported"]=bool(result["inlier_ratio"]>=.75 and
                            min(result["coverage_a"],result["coverage_b"])>=.25)
    return result
