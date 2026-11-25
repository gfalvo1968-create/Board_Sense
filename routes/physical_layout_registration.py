"""Compare verified physical landmarks across PCB faces; inspection only.

Inputs must be manually or independently verified physical hole centers in
rectified board coordinates (x and y normalized to the board outline).
Hough-circle candidates, image-frame coordinates and generic feature counts
are not valid substitutes. Layout agreement cannot prove unique identity.
"""
import itertools
import numpy as np

def compare_layouts(a,b,tolerance=.035):
    result={"compatible":False,"inspection_only":True,"matched_holes":0,
            "max_error":None,"transform":None,"reason":"Insufficient verified geometry"}
    try:
        pa,pb=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
        if pa.ndim!=2 or pb.ndim!=2 or pa.shape[1]!=2 or pb.shape[1]!=2:
            return result
        if not 3<=len(pa)==len(pb)<=8 or not .005<=tolerance<=.05:
            return result
        if not all(np.isfinite(p).all() and np.all((p>=0)&(p<=1)) for p in (pa,pb)):
            return result
        for p in (pa,pb):
            if np.linalg.matrix_rank(p-p.mean(axis=0),tol=.035)<2:
                return result
            distances=np.linalg.norm(p[:,None]-p[None,:],axis=2)
            if np.min(distances[np.triu_indices(len(p),1)])<.05:
                return result
        best=None
        for swap,flip_x,flip_y in itertools.product((False,True),repeat=3):
            q=pb[:,::-1].copy() if swap else pb.copy()
            if flip_x:q[:,0]=1-q[:,0]
            if flip_y:q[:,1]=1-q[:,1]
            distance=np.linalg.norm(pa[:,None]-q[None,:],axis=2)
            # One-to-one assignment: no landmark can be reused.
            for order in itertools.permutations(range(len(q))):
                errors=distance[np.arange(len(pa)),order]
                score=(float(errors.max()),float(errors.mean()))
                if best is None or score<best[0]:
                    best=(score,errors,dict(swap_axes=swap,flip_x=flip_x,flip_y=flip_y))
        score,errors,transform=best
        result.update(compatible=bool(score[0]<=tolerance),
                      matched_holes=int(np.sum(errors<=tolerance)),
                      max_error=round(score[0],5),transform=transform,
                      reason="Compatible layout; unique physical identity unverified" if score[0]<=tolerance else "Verified landmark layouts differ")
    except (TypeError,ValueError,np.linalg.LinAlgError):
        pass
    return result
