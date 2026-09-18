"""Regression guards for sparse legacy/electromechanical control boards."""
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from routes.component_discriminator import discriminate_components
from routes.board_power import detect_power_board
from routes.reference_reasoner import build_reference_matches


def _write_sparse_mechanical_control_fixture(path):
    image = np.full((900, 700, 3), 38, dtype=np.uint8)
    # Green PCB body.
    cv2.rectangle(image, (120, 90), (590, 820), (70, 150, 85), -1)

    # Mounting holes and LED-like circular bodies must not become IC packages.
    for x, y in [(170, 160), (520, 170), (190, 720), (520, 700)]:
        cv2.circle(image, (x, y), 24, (20, 20, 20), -1)
        cv2.circle(image, (x, y), 30, (130, 160, 110), 4)

    for x in [205, 280, 355, 430, 505]:
        cv2.circle(image, (x, 240), 22, (30, 30, 215), -1)

    # Mechanical wheel / gear-like body.
    cv2.circle(image, (460, 520), 78, (225, 225, 225), -1)
    cv2.circle(image, (460, 520), 14, (35, 35, 35), -1)

    # Switch and passive blocks.
    cv2.rectangle(image, (160, 570), (250, 620), (45, 45, 45), -1)
    for x, y in [(210, 360), (300, 390), (390, 350), (260, 470), (350, 450)]:
        cv2.rectangle(image, (x, y), (x + 18, y + 42), (25, 25, 25), -1)

    # One real DIP-style IC with pin evidence.
    cv2.rectangle(image, (285, 635), (410, 690), (18, 18, 18), -1)
    for x in range(295, 405, 16):
        cv2.line(image, (x, 628), (x, 635), (210, 210, 210), 3)
        cv2.line(image, (x, 690), (x, 697), (210, 210, 210), 3)

    cv2.imwrite(str(path), image)


def test_sparse_mechanical_control_board_does_not_become_dense_ic_population():
    with TemporaryDirectory() as td:
        path = Path(td) / "legacy_control.png"
        _write_sparse_mechanical_control_fixture(path)
        components = discriminate_components(str(path))

    assert components["ic_like"] <= 3, components
    assert components["capacitor_like"] <= 4, components
    assert components["dominant_family"] != "logic_ic" or components["ic_like"] >= 4


def test_weak_gold_color_and_large_photo_do_not_create_expansion_or_server_hypotheses():
    features = {
        "ram": False,
        "memory_module": False,
        "gold_fingers": False,
        "dense_component_board": False,
        "large_ic_chips": False,
        "processor": False,
        "motherboard": False,
        "power_board": False,
        "component_count": 1,
    }
    visual = {
        "possible_ram": False,
        "gold_finger_edge": False,
        "gold_edge_color_cue": True,
        "gold_finger_geometry": False,
        "repeated_edge_contacts": False,
        "gold_contact_count": 0,
        "aspect_ratio": 1.4,
        "possible_large_ic_chips": False,
    }
    motherboard = {
        "possible_motherboard": False,
        "large_board": True,
        "motherboard_structure_score": 0,
        "long_slot_candidates": 0,
        "edge_connector_bank": False,
    }
    power = {
        "possible_power_board": False,
        "power_stage_present": False,
        "power_score": 0,
        "raw_power_score": 0,
        "large_round_components": 0,
        "large_component_regions": 0,
    }
    result = build_reference_matches(
        features,
        visual,
        motherboard,
        power,
        {"type": "General PCB"},
    )
    labels = [x["type"] for x in result.get("hypotheses", [])]

    assert "Expansion / Gold Finger Card" not in labels, result
    assert "Server / Enterprise Board" not in labels, result
    assert result["gold_color_cue_only"] is True


def test_sparse_led_gear_control_board_does_not_become_power_supply():
    """LEDs, holes and a mechanical wheel may coexist with small capacitors without proving PSU topology."""
    with TemporaryDirectory() as td:
        path = Path(td) / "legacy_control_power_guard.png"
        _write_sparse_mechanical_control_fixture(path)
        power = detect_power_board(str(path))

    assert power["possible_power_board"] is False, power
    assert power["power_stage_present"] is False, power
    assert power.get("strong_power_hardware", False) is False, power
