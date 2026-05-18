# routes/board_motherboard.py

def detect_motherboard(features, visual):
    signals = {
        "cpu_socket": False,
        "ram_slots": False,
        "pci_slots": False,
        "rear_io_cluster": False,
        "dense_layout": False,
    }

    motherboard_score = 0

    if features.get("motherboard"):
        signals["cpu_socket"] = True
        signals["ram_slots"] = True
        signals["pci_slots"] = True
        signals["rear_io_cluster"] = True
        signals["dense_layout"] = True
        motherboard_score = 5

    return signals, motherboard_score
