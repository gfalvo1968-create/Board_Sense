"""Shared Recovery Lab decision engine."""

from recovery_lab.registry import RECOVERY_LABS
from recovery_lab.core.safety_rules import classify_recovery_risk
from recovery_lab.core.time_value import compare_recovery_to_sale
from recovery_lab.core.workflow_loader import attach_workflows


def choose_labs(spike_glass, board_result):
    labels = []
    top = (spike_glass or {}).get("top_match") or {}
    text = " ".join([
        str(top.get("label", "")),
        str(board_result.get("board_type", "")),
        " ".join(board_result.get("recovery_signals", []) or []),
    ]).lower()

    keyword_map = {
        "speakers": ["speaker", "audio driver", "loudspeaker", "voice coil"],
        "ram": ["ram", "memory"],
        "processors": ["processor", "cpu", "bga", "ceramic"],
        "gold_fingers": ["gold finger", "edge connector"],
        "transformers": ["transformer", "power board", "supply board"],
        "relays_contacts": ["relay", "contact", "switchgear"],
        "circuit_boards": ["circuit board", "pcb", "motherboard", "logic board"],
        "gold": ["gold"],
        "silver": ["silver"],
        "copper": ["copper", "winding", "voice coil", "bus bar"],
        "aluminum": ["aluminum", "heat sink"],
        "brass": ["brass", "terminal"],
    }

    for lab_key, words in keyword_map.items():
        if any(word in text for word in words):
            labels.append(lab_key)

    # Only true PCB results get the automatic Circuit Board Lab fallback.
    # Component/object routes such as speakers must never be pushed into a
    # whole-board recovery plan just because board_type contains a label.
    object_mode=((board_result.get("object_gate") or {}).get("mode") or "").lower()
    board_type=str(board_result.get("board_type","")).lower()
    if object_mode=="board" and "circuit_boards" not in labels:
        labels.append("circuit_boards")
    elif not object_mode and "circuit_boards" not in labels and any(k in board_type for k in ("board","pcb","motherboard")):
        labels.append("circuit_boards")

    # Preserve order while preventing duplicate lab buttons.
    seen=set();ordered=[]
    for key in labels:
        if key not in seen:
            seen.add(key);ordered.append(key)

    labs = [RECOVERY_LABS[key] | {"key": key} for key in ordered if key in RECOVERY_LABS]
    return attach_workflows(labs)


def build_recovery_plan(spike_glass, board_result, sell_value=None, recovered_value=None, minutes=None):
    labs = choose_labs(spike_glass, board_result)
    risk = classify_recovery_risk(labs)
    economics = compare_recovery_to_sale(sell_value, recovered_value, minutes)

    return {
        "labs": labs,
        "risk": risk,
        "economics": economics,
        "decision_options": [
            "SELL WHOLE",
            "MECHANICALLY SORT / DISASSEMBLE",
            "SEND TO REFINER",
            "REVIEW RECOVERY LAB",
        ],
        "note": "Recovery Lab separates safe mechanical guidance from hazardous refining operations and compares labor against sale value.",
    }
