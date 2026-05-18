# routes/board_motherboard.py

def detect_motherboard_signals(features, visual):
    signals = {
        "cpu_socket": False,
        "ram_slots": False,
        "pci_slots": False,
        "rear_io_cluster": False,
        "dense_layout": False,
    }

  motherboard_signals, motherboard_score = detect_motherboard_signals(
    features,
    visual_data
)

features["motherboard_signals"] = motherboard_signals

   if motherboard_score >= 3:
      features["motherboard"] = True
      score += 12
    
    # temporary keyword helpers until stronger image vision is added
    name = features.get("_filename", "")

    if "motherboard" in name or "mainboard" in name or "laptop" in name:
        signals["cpu_socket"] = True
        signals["ram_slots"] = True
        signals["pci_slots"] = True
        signals["rear_io_cluster"] = True
        signals["dense_layout"] = True

    score = sum(1 for v in signals.values() if v)

    return signals, score
