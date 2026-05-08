# ecosystem.py

RADAR_FAMILY = {
    "family_name": "Radar Family",

    "core_apps": {
        "scrap_radar": {
            "name": "Scrap Radar",
            "role": "Market map, price intelligence, and local buyer radar",
            "feeds": [
                "local_scrap_yards",
                "metal_prices",
                "fuel_costs",
                "buyer_locations",
                "sponsor_ads",
                "market_alerts"
            ],
            "status": "planned"
        },

        "board_sense": {
            "name": "Board Sense",
            "role": "Circuit board identification, grading, and recovery signal scanning",
            "feeds": [
                "board_images",
                "manual_labels",
                "chip_detection",
                "gold_finger_signals",
                "training_data",
                "board_reference_sheets"
            ],
            "status": "active"
        },

        "pay_dirt": {
            "name": "Pay_Dirt",
            "role": "Recovery decision engine and teardown guidance",
            "feeds": [
                "recoverable_materials",
                "gold_recovery",
                "silver_recovery",
                "rare_earth_signals",
                "yield_estimates",
                "recovery_steps"
            ],
            "status": "planned"
        },

        "precious_metals": {
            "name": "Precious Metals",
            "role": "Gold, silver, platinum, karat testing, and refinery-style value tracking",
            "feeds": [
                "spot_prices",
                "karat_testing",
                "silver_testing",
                "refinery_estimates",
                "coin_shop_sponsors"
            ],
            "status": "planned"
        }
    },

    "shared_signals": {
        "green": "Strong recovery or value signal",
        "orange": "Moderate signal. Inspect further.",
        "red": "Weak or no value signal",
        "jackpot": "Major signals green. Board should be reviewed for recovery in Pay_Dirt."
    },

    "sponsor_network": [
        {
            "name": "Cades Coin & Jewelry",
            "owner": "Jim Dennis",
            "location": "1187 Wyoming Ave, Exeter, PA 18643",
            "phone": "570-762-1298",
            "tagline": "Over 50 years in the same Exeter location.",
            "description": (
                "A trusted local coin and jewelry shop with a warm community feel. "
                "Known for coins, jewelry, gold, silver, and honest service."
            ),
            "connected_to": [
                "precious_metals",
                "scrap_radar",
                "board_sense"
            ],
            "notes": (
                "Jim Dennis has been in the same location for over 50 years. "
                "Parker Lane Financial Group is connected through his grandson."
            ),
            "map_query": "Cades Coin and Jewelry 1187 Wyoming Ave Exeter PA 18643",
            "reviews": [
                "A trusted local shop with a family feel.",
                "Walk in like a customer, leave feeling like family."
            ]
        }
    ]
}


def get_ecosystem():
    return RADAR_FAMILY


def get_app_info(app_key: str):
    return RADAR_FAMILY["core_apps"].get(app_key)


def get_sponsors():
    return RADAR_FAMILY["sponsor_network"]


def get_shared_signals():
    return RADAR_FAMILY["shared_signals"]
