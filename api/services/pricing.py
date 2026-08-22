from __future__ import annotations
from sqlalchemy.orm import Session

PLANT_BASE_PRICES = {1: 5, 2: 10, 3: 15}


def calculate_product_price(plant_level: int, production_kind: str, qty: int, db: Session) -> int:
    from models import ProductionTemplate
    base = PLANT_BASE_PRICES.get(plant_level, 5)
    tmpl = db.query(ProductionTemplate).filter(ProductionTemplate.code == production_kind).first()
    surcharge = tmpl.surcharge if tmpl else 30
    return (base + surcharge) * qty


ANIMAL_OPENING_PRICE_STEP = 5


def animal_opening_bonus(opening_order: int | None, qty: int) -> int:
    """Надбавка к цене продажи продукции животноводства: +5 монет за каждое последующее открытое животное."""
    if not opening_order or opening_order < 2:
        return 0
    return ANIMAL_OPENING_PRICE_STEP * (opening_order - 1) * qty


def get_animal_opening_order(db: Session, user_id: int, animal_id: int) -> int | None:
    from models import UserAnimalOpening
    row = db.query(UserAnimalOpening).filter(
        UserAnimalOpening.user_id == user_id,
        UserAnimalOpening.animal_id == animal_id,
    ).first()
    return row.opening_order if row else None


def animal_product_unit_price(db: Session, user_id: int, animal_id: int | None, production_kind: str | None) -> int | None:
    """Цена продажи 1 ед. продукции животноводства (текущая формула + надбавка за порядок открытия); None — не продукция животного."""
    if animal_id is None:
        return None
    from routes.settings import get_sale_price_ratio
    base = calculate_product_price(1, production_kind or "alchemy", 1, db)
    order = get_animal_opening_order(db, user_id, animal_id)
    return int(base * get_sale_price_ratio(db)) + animal_opening_bonus(order, 1)
