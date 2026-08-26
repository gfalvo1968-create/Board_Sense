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
        "ram": ["ram", "memory"],
        "processors": ["processor", "cpu", "bga", "ceramic"],
        "gold_fingers": ["gold finger", "edge connector"],
        "transformers": ["transformer", "power board", "supply board"],
        "relays_contacts": ["relay", "contact", "switchgear"],
        "circuit_boards": ["board", "pcb", "motherboard", "logic"],
        "gold": ["gold"],
        "silver": ["silver"],
        "copper": ["copper", "winding", "bus bar"],
        "aluminum": ["aluminum", "heat sink"],
        "brass": ["brass", "terminal"],
    }

    for lab_key, words in keyword_map.items():
        if any(word in text for word in words):
            labels.append(lab_key)

    if "circuit_boards" not in labels and board_result.get("board_type"):
        labels.append("circuit_boards")

    labs = [RECOVERY_LABS[key] | {"key": key} for key in labels if key in RECOVERY_LABS]
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
