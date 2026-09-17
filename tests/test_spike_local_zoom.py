import cv2
import numpy as np

from routes.spike_local_zoom import compare_visual_source, inspect_identity_zoom
import routes.spike_tool_layer as tool_layer


def _feature_rich_board(path):
    im = np.full((900, 1200, 3), 235, dtype=np.uint8)
    cv2.rectangle(im, (120, 90), (1080, 810), (35, 125, 55), -1)
    rng = np.random.default_rng(42)
    for i in range(70):
        x = int(rng.integers(160, 1040))
        y = int(rng.integers(130, 770))
        r = int(rng.integers(5, 18))
        cv2.circle(im, (x, y), r, (210, 210, 210), 2)
        cv2.line(im, (x - 15, y), (x + 25, y + 12), (15, 45, 20), 2)
    for i, text in enumerate(["R310", "IC201", "JR425R3HC0K", "79", "34", "H50C"]):
        cv2.putText(im, text, (180 + (i % 3) * 290, 220 + (i // 3) * 300), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (245, 245, 245), 2, cv2.LINE_AA)
    cv2.imwrite(str(path), im)
    return im


def test_zoomed_crop_is_non_independent_visual_evidence(tmp_path):
    base_path = tmp_path / "base.jpg"
    crop_path = tmp_path / "zoom.jpg"
    im = _feature_rich_board(base_path)
    crop = im[180:720, 260:940]
    crop = cv2.resize(crop, (1000, 800), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(str(crop_path), crop)

    rel = compare_visual_source(str(base_path), str(crop_path))
    assert rel["non_independent"] is True
    assert rel["relation"] == "same_visual_source_or_near_duplicate"
    assert rel["homography_inliers"] >= 18


def test_local_zoom_uses_existing_pixels_without_becoming_new_evidence(tmp_path):
    base_path = tmp_path / "base.jpg"
    _feature_rich_board(base_path)
    zoom = inspect_identity_zoom(str(base_path), "x", 600)
    assert zoom["status"] == "inspectable_existing_pixels"
    assert zoom["independent_evidence"] is False
    assert zoom["identity_override"] is False
    assert zoom["feature_count"] >= 12


def test_identity_clarification_zooms_before_any_paid_web_lookup(tmp_path, monkeypatch):
    base_path = tmp_path / "base.jpg"
    crop_path = tmp_path / "zoom.jpg"
    im = _feature_rich_board(base_path)
    crop = cv2.resize(im[180:720, 260:940], (1000, 800), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(str(crop_path), crop)

    def web_must_not_run(*args, **kwargs):
        raise AssertionError("paid/external web lookup must not run for local physical-continuity clarification")

    monkeypatch.setattr(tool_layer, "search_visual_matches", web_must_not_run)
    identity = {
        "status": "IDENTITY_CLARIFICATION_NEEDED",
        "same_board": None,
        "block_reconciliation": True,
        "whole_view_count": 1,
        "requested_photos": [
            {
                "flagged_view": 1,
                "request_type": "targeted_continuity_photo",
                "axis": "x",
                "cut": 600,
            }
        ],
    }
    packet = tool_layer.investigate_identity(
        [{"view_number": 1}, {"view_number": 2}],
        [str(base_path), str(crop_path)],
        identity,
    )
    assert "local_zoom_inspection" in packet["tools_used"]
    assert packet["web_reference_searches"] == []
    assert packet["identity_override"] is False
    assert packet["local_zoom_inspections"][0]["independent_evidence"] is False
    assert packet.get("non_independent_view_pairs") == [[1, 2]]


def test_probable_same_board_is_withheld_with_only_one_usable_whole_view(tmp_path, monkeypatch):
    base_path = tmp_path / "base.jpg"
    detail_path = tmp_path / "detail.jpg"
    im = _feature_rich_board(base_path)
    detail = cv2.resize(im[160:760, 220:980], (1000, 800), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(str(detail_path), detail)

    def web_must_not_run(*args, **kwargs):
        raise AssertionError("paid web lookup must not run when a new independent whole-board photo is required")

    monkeypatch.setattr(tool_layer, "search_visual_matches", web_must_not_run)
    results = [
        {
            "view_number": 1,
            "physical_fingerprint": {"coverage": "whole_or_large_view", "geometry_quality": "medium"},
        },
        {
            "view_number": 2,
            "physical_fingerprint": {"coverage": "detail_or_partial_view", "geometry_quality": "low"},
        },
    ]
    identity = {
        "status": "PROBABLY_SAME_BOARD",
        "same_board": True,
        "confidence": 82,
        "block_reconciliation": False,
        "whole_view_count": 1,
        "reasons": ["No strong contradiction was found."],
    }

    packet = tool_layer.investigate_identity(results, [str(base_path), str(detail_path)], identity)

    assert identity["status"] == "IDENTITY_CLARIFICATION_NEEDED"
    assert identity["same_board"] is None
    assert identity["block_reconciliation"] is True
    assert identity["independent_whole_view_count"] == 1
    assert packet["status"] == "identity_photo_needed"
    assert packet["evidence_floor_applied"] is True
    assert packet["web_reference_searches"] == []


def test_duplicate_whole_views_count_as_one_identity_witness(tmp_path, monkeypatch):
    base_path = tmp_path / "base.jpg"
    crop_path = tmp_path / "zoom.jpg"
    im = _feature_rich_board(base_path)
    crop = cv2.resize(im[140:780, 190:1010], (1200, 900), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(str(crop_path), crop)

    def web_must_not_run(*args, **kwargs):
        raise AssertionError("duplicate whole views must request a new physical view before paid lookup")

    monkeypatch.setattr(tool_layer, "search_visual_matches", web_must_not_run)
    results = [
        {
            "view_number": 1,
            "physical_fingerprint": {"coverage": "whole_or_large_view", "geometry_quality": "good"},
        },
        {
            "view_number": 2,
            "physical_fingerprint": {"coverage": "whole_or_large_view", "geometry_quality": "good"},
        },
    ]
    identity = {
        "status": "PROBABLY_SAME_BOARD",
        "same_board": True,
        "confidence": 88,
        "block_reconciliation": False,
        "whole_view_count": 2,
        "reasons": [],
    }

    packet = tool_layer.investigate_identity(results, [str(base_path), str(crop_path)], identity)

    assert packet.get("non_independent_view_pairs") == [[1, 2]]
    assert packet["independent_whole_view_count"] == 1
    assert identity["status"] == "IDENTITY_CLARIFICATION_NEEDED"
    assert identity["block_reconciliation"] is True
    assert packet["status"] == "identity_photo_needed"
