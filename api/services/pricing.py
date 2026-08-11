PLANT_BASE_PRICES = {1: 5, 2: 10, 3: 15}
TENT_SURCHARGES = {"sewing": 30, "workshop": 35, "alchemy": 40}


def calculate_product_price(plant_level: int, production_kind: str, qty: int) -> int:
    base = PLANT_BASE_PRICES.get(plant_level, 5)
    surcharge = TENT_SURCHARGES.get(production_kind, 30)
    return (base + surcharge) * qty
