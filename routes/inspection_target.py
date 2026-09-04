"""Target-aware SPIKE inspection context.

This layer never changes ordinary board grading. It only tells SPIKE whether the
current recognition supports the inspection mission that came from Scrap Radar.
"""
import json
from pathlib import Path
import cv2
from routes.target_visual_refined import inspect_target_visual

SOURCE_SUPPORT = {
    "hard-drive": ("magnet", "actuator", "hard drive", "voice coil"),
    "speaker": ("speaker", "magnet", "voice coil"),
    "motor": ("motor", "rotor", "magnet", "generator"),
    "nimh": ("nimh", "battery", "pack", "cell"),
    "li-ion": ("lithium", "li-ion", "battery", "pack", "cell"),
    "display": ("display", "touchscreen", "screen", "led", "phosphor"),
    "semiconductor": ("ic / logic", "semiconductor", "rf", "power", "logic package"),
    "capacitors": ("capacitor", "tantalum"),
    "carbide": ("carbide", "tool", "insert", "tungsten"),
    "solar": ("solar", "photovoltaic", "module"),
    "optics": ("optic", "laser", "fiber"),
    "alloy": ("alloy", "solder"),
}


def parse_inspection_target(raw):
    if not raw:
        return None
    if isinstance(raw, dict):
        packet = raw
    else:
        try:
            packet = json.loads(raw)
        except Exception:
            return None
    if not isinstance(packet, dict) or not packet.get("target"):
        return None
    return packet


def _text(*values):
    return " ".join(str(v or "") for v in values).lower()


def _annotate_blueprint_target(result, visual_target, image_path, target, status):
    """Draw a navigation-only cyan marker onto the existing Blueprint image.

    A precise marker is intentionally reserved for component-level
    TARGET CANDIDATE results. Area-only evidence can prove the user is in the
    right neighborhood without proving an exact point, so TARGET AREA CANDIDATE
    never receives a precise crosshair.

    Geometry comes from the target detector's resized working image. The Board
    Blueprint preserves the uploaded image's aspect ratio, so coordinates are
    scaled back to the Blueprint dimensions before drawing. This marker locates
    the component candidate only. It is never a composition or value claim.
    """
    if status != "target_candidate":
        return result

    try:
        geometry = (visual_target or {}).get("geometry") or {}
        metrics = (visual_target or {}).get("metrics") or {}
        src_w = float(metrics.get("image_width") or 0)
        src_h = float(metrics.get("image_height") or 0)

        point = geometry.get("plate") or {}
        if not point:
            return result
        px = float(point.get("x"))
        py = float(point.get("y"))
        if src_w <= 0 or src_h <= 0:
            return result

        blueprint = result.get("board_blueprint") or {}
        filename = blueprint.get("image_filename")
        if not filename or not image_path:
            return result
        blueprint_path = Path(image_path).resolve().parent.parent / "Blueprints" / filename
        image = cv2.imread(str(blueprint_path))
        if image is None:
            return result

        h, w = image.shape[:2]
        x = int(round(px * w / src_w))
        y = int(round(py * h / src_h))
        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))

        base = max(w, h)
        radius = max(34, int(base / 18))
        thickness = max(4, int(base / 420))
        arm = max(radius + 18, int(base / 11))
        cyan = (255, 255, 0)  # BGR
        black = (0, 0, 0)

        cv2.circle(image, (x, y), radius + thickness * 2, black, thickness * 2, cv2.LINE_AA)
        cv2.circle(image, (x, y), radius, cyan, thickness, cv2.LINE_AA)
        cv2.line(image, (max(0, x - arm), y), (max(0, x - radius - 8), y), black, thickness * 2, cv2.LINE_AA)
        cv2.line(image, (min(w - 1, x + radius + 8), y), (min(w - 1, x + arm), y), black, thickness * 2, cv2.LINE_AA)
        cv2.line(image, (x, max(0, y - arm)), (x, max(0, y - radius - 8)), black, thickness * 2, cv2.LINE_AA)
        cv2.line(image, (x, min(h - 1, y + radius + 8)), (x, min(h - 1, y + arm)), black, thickness * 2, cv2.LINE_AA)
        cv2.line(image, (max(0, x - arm), y), (max(0, x - radius - 8), y), cyan, thickness, cv2.LINE_AA)
        cv2.line(image, (min(w - 1, x + radius + 8), y), (min(w - 1, x + arm), y), cyan, thickness, cv2.LINE_AA)
        cv2.line(image, (x, max(0, y - arm)), (x, max(0, y - radius - 8)), cyan, thickness, cv2.LINE_AA)
        cv2.line(image, (x, min(h - 1, y + radius + 8)), (x, min(h - 1, y + arm)), cyan, thickness, cv2.LINE_AA)

        label = "TARGET CANDIDATE"
        font = cv2.FONT_HERSHEY_SIMPLEX
        fs = max(0.7, min(1.6, base / 1100.0))
        tw, th = cv2.getTextSize(label, font, fs, thickness)[0]
        tx = max(8, min(w - tw - 8, x - tw // 2))
        ty = y - radius - 18
        if ty < th + 10:
            ty = min(h - 10, y + radius + th + 18)
        cv2.putText(image, label, (tx, ty), font, fs, black, thickness * 3, cv2.LINE_AA)
        cv2.putText(image, label, (tx, ty), font, fs, cyan, thickness, cv2.LINE_AA)
        cv2.imwrite(str(blueprint_path), image)

        blueprint["target_marker"] = {
            "active": True,
            "label": label,
            "target": target,
            "status": status,
            "confidence": visual_target.get("confidence"),
            "x": x,
            "y": y,
            "geometry_source": "plate",
            "rule": "Navigation marker only; it does not prove composition, recoverable mass, or value.",
        }
        result["board_blueprint"] = blueprint
    except Exception:
        pass
    return result


def apply_inspection_target(result, packet, image_path=None):
    packet = parse_inspection_target(packet)
    if not packet:
        return result

    spike = result.get("spike_glass") or {}
    top = spike.get("top_match") or {}
    source_id = str(packet.get("sourceId") or "").strip()
    source_name = str(packet.get("sourceName") or "Scrap Radar source")
    target = str(packet.get("target") or "Saved inspection target")

    visual_target = {"applicable": False, "status": "not_applicable", "confidence": 0, "evidence": []}
    if image_path:
        try:
            visual_target = inspect_target_visual(image_path, source_id, target)
        except Exception as exc:
            visual_target = {
                "applicable": True,
                "status": "target_not_confirmed",
                "confidence": 0,
                "evidence": [],
                "message": "Target-specific visual geometry could not complete safely.",
                "error": str(exc),
            }

    haystack = _text(
        top.get("label"),
        top.get("family"),
        result.get("board_type"),
        (result.get("object_gate") or {}).get("label"),
    )
    support_terms = SOURCE_SUPPORT.get(source_id, ())
    text_supported = bool(support_terms and any(term in haystack for term in support_terms))

    if visual_target.get("status") == "target_candidate":
        status = "target_candidate"
        message = visual_target.get("message") or (
            "Target-specific component geometry supports the saved inspection target as a candidate. "
            "Composition and recoverable mass remain unproven."
        )
    elif visual_target.get("status") == "target_area_candidate":
        status = "target_area_candidate"
        message = visual_target.get("message") or (
            "Target-specific geometry found the expected inspection area. "
            "Use a closer view before treating the component itself as confirmed."
        )
    elif visual_target.get("applicable"):
        status = "target_not_confirmed"
        message = visual_target.get("message") or (
            "Target-specific visual evidence did not confirm the saved inspection target. "
            "Reframe on the expected component and preserve enough surrounding context to place it."
        )
    elif text_supported:
        status = "target_candidate"
        message = (
            "Current visual recognition overlaps the saved inspection mission. "
            "Treat this as a target candidate only; composition and recoverable mass remain unproven."
        )
    else:
        status = "target_not_confirmed"
        generic = top.get("label") or result.get("board_type") or "generic visual features"
        if visual_target.get("applicable") and visual_target.get("message"):
            message = visual_target.get("message")
        else:
            message = (
                f"Current image produced generic recognition '{generic}', but that does not confirm "
                f"the saved target '{target}'. Reframe closer on the target area and include enough "
                "surrounding context to place it on the item."
            )

    target_result = {
        "status": status,
        "source_id": source_id,
        "source_name": source_name,
        "target": target,
        "where": packet.get("where") or "",
        "look": packet.get("look") or "",
        "preserve": packet.get("preserve") or "",
        "watch": packet.get("watch") or "",
        "materials": packet.get("materials") if isinstance(packet.get("materials"), list) else [],
        "message": message,
        "visual_target": visual_target,
        "generic_top_match": {
            "label": top.get("label"),
            "family": top.get("family"),
            "confidence": spike.get("confidence"),
        },
        "rule": "Inspection context can narrow what SPIKE is trying to confirm, but it cannot manufacture visual evidence, composition, recoverable mass, or cash value.",
    }
    result["inspection_target"] = target_result
    spike["target_mode"] = True
    spike["target_status"] = status
    spike["target_name"] = target
    result["spike_glass"] = spike

    if status == "target_candidate" and image_path:
        result = _annotate_blueprint_target(result, visual_target, image_path, target, status)
    return result
