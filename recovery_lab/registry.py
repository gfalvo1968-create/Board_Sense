"""Recovery Lab routing registry.

Each lab owns its material/component-specific knowledge while shared logic lives
under recovery_lab/core.
"""

RECOVERY_LABS = {
    "copper": {"label": "Copper Lab", "path": "recovery_lab/copper", "focus": ["bare copper", "wire", "bus bar", "windings"]},
    "gold": {"label": "Gold Lab", "path": "recovery_lab/gold", "focus": ["gold fingers", "plated contacts", "processors", "connectors"]},
    "silver": {"label": "Silver Lab", "path": "recovery_lab/silver", "focus": ["contacts", "relays", "switchgear", "plated parts"]},
    "aluminum": {"label": "Aluminum Lab", "path": "recovery_lab/aluminum", "focus": ["heat sinks", "frames", "cast aluminum"]},
    "brass": {"label": "Brass Lab", "path": "recovery_lab/brass", "focus": ["connectors", "terminals", "hardware"]},
    "transformers": {"label": "Transformer Lab", "path": "recovery_lab/transformers", "focus": ["copper windings", "steel core", "power components"]},
    "relays_contacts": {"label": "Relay & Contact Lab", "path": "recovery_lab/relays_contacts", "focus": ["silver contacts", "copper", "brass", "relay blocks"]},
    "gold_fingers": {"label": "Gold Finger Lab", "path": "recovery_lab/gold_fingers", "focus": ["edge connectors", "finger cards", "RAM fingers"]},
    "processors": {"label": "Processor Lab", "path": "recovery_lab/processors", "focus": ["CPUs", "BGAs", "ceramic packages"]},
    "ram": {"label": "RAM Lab", "path": "recovery_lab/ram", "focus": ["memory modules", "gold fingers", "IC population"]},
    "circuit_boards": {"label": "Circuit Board Lab", "path": "recovery_lab/circuit_boards", "focus": ["whole-board sale", "depopulation", "sorting", "grade comparison"]},
    "speakers": {"label": "Speaker / Audio Driver Lab", "path": "recovery_lab/speakers", "focus": ["voice-coil copper", "steel basket and frame", "magnet assembly", "terminals and lead wire"]},
}


def get_lab(key):
    return RECOVERY_LABS.get(key)
