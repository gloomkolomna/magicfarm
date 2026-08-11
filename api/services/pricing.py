from sqlalchemy.orm import Session

PLANT_BASE_PRICES = {1: 5, 2: 10, 3: 15}


def calculate_product_price(plant_level: int, production_kind: str, qty: int, db: Session) -> int:
    from models import ProductionTemplate
    base = PLANT_BASE_PRICES.get(plant_level, 5)
    tmpl = db.query(ProductionTemplate).filter(ProductionTemplate.code == production_kind).first()
    surcharge = tmpl.surcharge if tmpl else 30
    return (base + surcharge) * qty
