# ecosystem.py

RADAR_FAMILY = {
    "family_name": "Radar Family",

    "core_apps": {
        "scrap_radar": {
            "name": "Scrap Radar",
            "role": "Market map and price intelligence",
            "feeds": [
                "local_scrap_yards",
                "metal_prices",
                "fuel_costs",
                "buyer_locations",
                "sponsor_ads"
            ]
        },

        "board_sense": {
            "name": "Board Sense",
            "role": "Board identification and grading intelligence",
            "feeds": [
                "board_images",
                "manual_labels",
                "chip_detection",
                "gold_finger_signals",
                "training_data"
            ]
        },

        "pay_dirt": {
            "name": "Pay_Dirt",
            "role": "Recovery decision and teardown guidance",
            "feeds": [
                "recoverable_materials",
                "gold_recovery",
                "silver_recovery",
                "rare_earth_signals",
                "yield_estimates"
            ]
        },

        "precious_metals": {
            "name": "Precious Metals",
            "role": "Gold, silver, platinum, and refinery-style value tracking",
            "feeds": [
                "spot_prices",
                "karat_testing",
                "silver_testing",
                "refinery_estimates"
            ]
        }
    },

    "shared_signals": {
        "green": "Strong recovery or value signal",
        "orange": "Medium recovery or value signal",
        "red": "Low or no recovery signal",
        "jackpot": "All major signals green. Board should be reviewed for recovery."
    },

    "sponsor_network": [
        {
            "name": "Cades Coin & Jewelry",
            "location": "1187 Wyoming Ave, Exeter, PA 18643",
            "phone": "570-762-1298",
            "connected_to": [
                "precious_metals",
                "scrap_radar",
                "board_sense"
            ],
            "notes": "Jim Dennis has been in the same location for over 50 years. Parker Lane Financial Group is connected through his grandson."
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
