"""Conservative PCB surface support for component and connector geometry.

The photo boundary is never evidence of a PCB perimeter. An uncertain outline
returns an empty mask rather than admitting the whole textured background.
"""
import cv2
import numpy as np



def _dark_board_on_light_surface(image, gray, k):
    """Locate a dark PCB silhouette on moderately textured light surroundings.

    A silhouette is *not* evidence of components or recoverable material.
    Clipped frames, highly variable backgrounds and plain dark objects do not
    acquire board identity from this helper.
    """
    h, w = gray.shape[:2]
    bh, bw = max(2, h // 20), max(2, w // 20)
    border = np.concatenate([gray[:bh, :].ravel(), gray[-bh:, :].ravel(),
                             gray[:, :bw].ravel(), gray[:, -bw:].ravel()])
    if np.median(border) < 145 or np.std(border) > 55:
        return np.zeros((h, w), dtype=np.uint8)
    foreground = cv2.inRange(gray, 0, 110)
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE,
                                  np.ones((k, k), np.uint8), iterations=2)
    contours, _ = cv2.findContours(foreground, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return np.zeros((h, w), dtype=np.uint8)
    c = max(contours, key=cv2.contourArea)
    x, y, rw, rh = cv2.boundingRect(c)
    area = cv2.contourArea(c) / max(1, h * w)
    margin = max(4, int(min(h, w) * .012))
    if not (.10 <= area <= .60) or x < margin or y < margin or x + rw > w - margin or y + rh > h - margin:
        return np.zeros((h, w), dtype=np.uint8)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(mask, [c], -1, 255, -1)
    # Reject plain panels: interior edges must support populated texture, but
    # this is only an outline mask, not an IC or monetary-value claim.
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 55, 150)
    interior = cv2.erode(mask, np.ones((max(9, (min(h, w) // 50) | 1),) * 2, np.uint8))
    evidence = cv2.countNonZero(cv2.bitwise_and(edges, interior)) / max(1, cv2.countNonZero(interior))
    if evidence < .045:
        return np.zeros((h, w), dtype=np.uint8)
    return mask


def _fragmented_green_board_support(image, hsv):
    """Conservatively reconnect green PCB surface hidden by tall power hardware.

    Warm, textured surroundings can dominate the broad solder-mask hue
    histogram, while a relay/capacitor population fragments the true green
    surface. This fallback only supplies an approximate *support region* for
    downstream inspection markers. It does not prove a physical board outline,
    part identity, same-board identity, buyer grade, or metal content.
    """
    h, w = image.shape[:2]
    area = max(1, h * w)
    empty = np.zeros((h, w), dtype=np.uint8)

    # Avoid the yellow/brown cloth hues that can dominate broad [18, 105]
    # searches. This fallback is deliberately narrower than the primary path;
    # warm-lit PCB handling remains available in the existing primary path.
    green = cv2.inRange(hsv, np.array([36, 65, 24]),
                       np.array([100, 255, 255]))
    margin = max(6, int(min(h, w) * .04))
    border_count = (
        cv2.countNonZero(green[:margin, :])
        + cv2.countNonZero(green[-margin:, :])
        + cv2.countNonZero(green[margin:-margin, :margin])
        + cv2.countNonZero(green[margin:-margin, -margin:])
    )
    border_area = 2 * margin * w + 2 * margin * max(0, h - 2 * margin)
    if border_count / max(1, border_area) > .02:
        return empty

    kernel = max(3, (min(h, w) // 200) | 1)
    green = cv2.morphologyEx(green, cv2.MORPH_OPEN,
                            np.ones((kernel, kernel), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(green, 8)
    minimum_island = max(90, int(area * .00004))
    islands = [i for i in range(1, count)
               if stats[i, cv2.CC_STAT_AREA] >= minimum_island]
    # Some legitimate populated PCB faces expose only one or two connected
    # green islands. Interior population evidence below still vetoes plain
    # green panels, and the primary object/identity gates remain independent.
    if not 1 <= len(islands) <= 180:
        return empty

    island_sizes = [int(stats[i, cv2.CC_STAT_AREA]) for i in islands]
    total_green = sum(island_sizes)
    # Insist on one dominant populated surface, rather than bridging scattered
    # green objects or several separate boards into one synthetic outline.
    if total_green < area * .025 or max(island_sizes) < total_green * .55:
        return empty

    lookup = np.zeros(count, dtype=np.uint8)
    lookup[islands] = 255
    supported_pixels = lookup[labels]
    ys, xs = np.nonzero(supported_pixels)
    hull = cv2.convexHull(np.column_stack((xs, ys)).astype(np.int32))
    x, y, bw, bh = cv2.boundingRect(hull)
    if x < margin or y < margin or x + bw >= w - margin or y + bh >= h - margin:
        return empty
    hull_area = cv2.contourArea(hull)
    if not (.12 <= hull_area / area <= .84):
        return empty
    if total_green / max(1, hull_area) < .14:
        return empty

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(mask, [hull], -1, 255, -1)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 55, 150)
    erosion = max(9, (min(h, w) // 70) | 1)
    interior = cv2.erode(mask, np.ones((erosion, erosion), np.uint8))
    evidence = cv2.countNonZero(cv2.bitwise_and(edges, interior)) / max(
        1, cv2.countNonZero(interior))
    if evidence < .045:
        return empty
    return mask


def _isolated_blue_surface(image, hsv):
    """Alternative support region for a fragmented blue PCB on warm background.

    Only considered when the original color region covers an unusually large
    portion of the frame. This is not a physical identity or grade detector.
    """
    h,w=image.shape[:2]
    area=h*w
    empty=np.zeros((h,w),np.uint8)
    blue=cv2.inRange(hsv,np.array([85,45,20]),np.array([135,255,255]))
    k=max(3,(min(h,w)//85)|1)
    blue=cv2.morphologyEx(blue,cv2.MORPH_CLOSE,np.ones((k,k),np.uint8),iterations=2)
    n,labels,stats,_=cv2.connectedComponentsWithStats(blue)
    ids=[i for i in range(1,n) if stats[i,cv2.CC_STAT_AREA]>=area*.001]
    if not 2<=len(ids)<=20:
        return empty
    ys,xs=np.nonzero(np.isin(labels,ids))
    hull=cv2.convexHull(np.column_stack((xs,ys)).astype(np.int32))
    a=cv2.contourArea(hull)
    rw,rh=cv2.minAreaRect(hull)[1]
    x,y,bw,bh=cv2.boundingRect(hull)
    margin=max(4,int(min(h,w)*.025))
    if not (.12<=a/area<=.65 and a/max(1,rw*rh)>=.75 and len(xs)/max(1,a)>=.20):
        return empty
    if x<margin or y<margin or x+bw>w-margin or y+bh>h-margin:
        return empty
    mask=empty.copy()
    cv2.drawContours(mask,[hull],-1,255,-1)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    edges=cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),55,150)
    detail=cv2.countNonZero(cv2.bitwise_and(edges,mask))/max(1,cv2.countNonZero(mask))
    return mask if detail>=.075 else empty


def board_region_mask(image):
    h, w = image.shape[:2]
    area = max(1, h * w)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Include warm-lit green solder mask. Saturation excludes most gray cloth;
    # color locates a surface only and supplies no board identity or value.
    surface = cv2.inRange(hsv, np.array([18, 70, 22]), np.array([105, 255, 255]))
    # Separate a dominant green/teal solder-mask hue from blue cloth that can
    # otherwise join the outline. Only refine when a strong color mode exists;
    # this locates the surface and never supplies identity or value evidence.
    hue = hsv[:, :, 0]
    hist = np.bincount(hue[surface > 0], minlength=180)
    if hist.sum():
        smooth = np.convolve(hist, np.ones(5), mode="same")
        peak = int(np.argmax(smooth[18:91]) + 18)
        radius = 7 if peak >= 70 else 15
        lo, hi = max(18, peak-radius), min(105, peak+radius)
        if hist[lo:hi+1].sum() / hist.sum() >= .45:
            surface = cv2.inRange(hsv, np.array([lo, 70, 22]),
                                 np.array([hi, 255, 255]))
    k = max(3, (min(h, w) // 85) | 1)
    surface = cv2.morphologyEx(surface, cv2.MORPH_CLOSE,
                               np.ones((k, k), np.uint8), iterations=2)
    contours, _ = cv2.findContours(surface, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for c in contours:
        a = cv2.contourArea(c)
        rw, rh = cv2.minAreaRect(c)[1]
        if .08 <= a / area <= .95 and a / max(1, rw * rh) >= .55:
            candidates.append(c)
    if candidates:
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(mask, [max(candidates, key=cv2.contourArea)], -1, 255, -1)
        if cv2.countNonZero(mask)/area >= .80:
            blue = _isolated_blue_surface(image, hsv)
            if cv2.countNonZero(blue):
                return blue
        return mask

    # Non-green boards can still have a clear outline against a plain surface.
    # A variable border (folds, shadows, weave) cannot support this fallback.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bh, bw = max(2, h // 20), max(2, w // 20)
    border = np.concatenate([gray[:bh, :].ravel(), gray[-bh:, :].ravel(),
                             gray[:, :bw].ravel(), gray[:, -bw:].ravel()])
    if np.std(border) > 24:
        supported = _fragmented_green_board_support(image, hsv)
        if cv2.countNonZero(supported):
            return supported
        return _dark_board_on_light_surface(image, gray, k)
    diff = cv2.absdiff(gray, np.full_like(gray, int(np.median(border))))
    _, foreground = cv2.threshold(diff, 22, 255, cv2.THRESH_BINARY)
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE,
                                  np.ones((k, k), np.uint8), iterations=2)
    contours, _ = cv2.findContours(foreground, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = [c for c in contours if .08 <= cv2.contourArea(c) / area <= .95]
    mask = np.zeros((h, w), dtype=np.uint8)
    if candidates:
        cv2.drawContours(mask, [max(candidates, key=cv2.contourArea)], -1, 255, -1)
        return mask

    # A plain/light border may cause generic foreground thresholding to fail
    # even though a populated PCB still has well-supported green patches.
    # Apply the guarded green-surface fallback here too, never the whole frame.
    return _fragmented_green_board_support(image, hsv)


def region_on_board(mask, region, minimum_coverage=.65):
    h, w = mask.shape[:2]
    x, y = int(region.get('x', 0)), int(region.get('y', 0))
    rw, rh = int(region.get('w', 0)), int(region.get('h', 0))
    if rw <= 0 or rh <= 0 or x < 0 or y < 0 or x + rw > w or y + rh > h:
        return False
    if not mask[y + rh // 2, x + rw // 2]:
        return False
    return cv2.countNonZero(mask[y:y + rh, x:x + rw]) / (rw * rh) >= minimum_coverage

