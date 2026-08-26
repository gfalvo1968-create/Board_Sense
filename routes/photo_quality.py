"""Photo-quality checks for Board Sense / Spike Glass.

This gate estimates whether a photo is sharp, bright, and usable enough for
recognition. It provides retake guidance instead of letting weak images drive
high-confidence identifications.
"""

import cv2
import numpy as np


def assess_photo_quality(image_path):
    result = {
        "status": "unknown",
        "score": 0,
        "sharpness": 0.0,
        "brightness": 0.0,
        "glare_ratio": 0.0,
        "dark_ratio": 0.0,
        "resolution": {"width": 0, "height": 0},
        "issues": [],
        "guidance": [],
        "usable": False,
    }

    try:
        image = cv2.imread(image_path)
        if image is None:
            result["status"] = "unreadable"
            result["issues"].append("Image could not be decoded.")
            result["guidance"].append("Retake the photo or choose a different image file.")
            return result

        height, width = image.shape[:2]
        result["resolution"] = {"width": int(width), "height": int(height)}

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(np.mean(gray))
        glare_ratio = float(np.mean(gray >= 245))
        dark_ratio = float(np.mean(gray <= 25))

        result["sharpness"] = round(sharpness, 2)
        result["brightness"] = round(brightness, 2)
        result["glare_ratio"] = round(glare_ratio, 4)
        result["dark_ratio"] = round(dark_ratio, 4)

        score = 100

        if min(width, height) < 500:
            score -= 20
            result["issues"].append("Low image resolution.")
            result["guidance"].append("Move closer or use a higher-resolution photo.")

        if sharpness < 45:
            score -= 35
            result["issues"].append("Image appears blurry or out of focus.")
            result["guidance"].append("Hold the camera steady and tap the component to focus before retaking.")
        elif sharpness < 90:
            score -= 15
            result["issues"].append("Image is somewhat soft.")
            result["guidance"].append("A sharper close-up may improve recognition confidence.")

        if brightness < 55:
            score -= 30
            result["issues"].append("Image is too dark.")
            result["guidance"].append("Add more even light or move the item into a brighter area.")
        elif brightness > 215:
            score -= 20
            result["issues"].append("Image is very bright and may be overexposed.")
            result["guidance"].append("Reduce direct light and retake with softer lighting.")

        if glare_ratio > 0.12:
            score -= 25
            result["issues"].append("Strong glare or blown highlights detected.")
            result["guidance"].append("Tilt the board or light source so reflections do not cover markings or contacts.")
        elif glare_ratio > 0.06:
            score -= 10
            result["issues"].append("Moderate glare detected.")
            result["guidance"].append("A slightly different camera angle may reveal more detail.")

        if dark_ratio > 0.45:
            score -= 15
            result["issues"].append("Large portions of the image are nearly black.")
            result["guidance"].append("Improve lighting or reframe so the item fills more of the image.")

        score = max(0, min(100, int(round(score))))
        result["score"] = score
        result["usable"] = score >= 55

        if score >= 80:
            result["status"] = "good"
        elif score >= 55:
            result["status"] = "usable"
        else:
            result["status"] = "retake_recommended"

        if not result["issues"]:
            result["guidance"].append("Photo quality looks good for recognition.")

    except Exception as exc:
        print(f"[Photo Quality Error] {exc}")
        result["status"] = "error"
        result["issues"].append("Photo quality check failed.")
        result["guidance"].append("Retake the image if recognition confidence looks suspicious.")

    return result
