from __future__ import annotations
from sqlalchemy.orm import Session


INSTANT_BONUSES = {
    "free_pet",
    "early_level_up",
    "extra_barnyard_slot",
    "unlock_garden_l3",
    "unlock_orchard_l3",
}

CONDITIONAL_BONUSES = {
    "double_garden_harvest",
    "double_orchard_harvest",
    "double_animal_product",
    "double_order_reward",
    "skip_plant_stitch",
    "skip_animal_stitch",
    "bonus_sewing_product",
    "bonus_workshop_product",
    "bonus_alchemy_product",
    "partial_order",
}

_PRODUCT_BONUS_BY_KIND = {
    "alchemy": "bonus_alchemy_product",
    "shatyor_zelevareniya": "bonus_alchemy_product",
    "sewing": "bonus_sewing_product",
    "shatyor_masterskaya": "bonus_sewing_product",
    "workshop": "bonus_workshop_product",
    "shatyor_masterskaya_3": "bonus_workshop_product",
}


def product_bonus_code(production_kind: str | None) -> str | None:
    if not production_kind:
        return None
    return _PRODUCT_BONUS_BY_KIND.get(production_kind)


def _armed_potion(user_id: int, code: str, db: Session):
    from models import UserPotion

    return db.query(UserPotion).filter(
        UserPotion.user_id == user_id,
        UserPotion.bonus_code == code,
        UserPotion.activated.is_(True),
        UserPotion.used.is_(False),
    ).first()


def is_potion_active(user_id: int, code: str, db: Session) -> bool:
    return _armed_potion(user_id, code, db) is not None


def consume_potion(user_id: int, code: str, db: Session) -> None:
    p = _armed_potion(user_id, code, db)
    if p is not None:
        p.used = True
