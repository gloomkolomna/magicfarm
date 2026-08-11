from sqlalchemy.orm import Session


def _get_bonus(user_id: int, bonus_kind: str, bonus_amount: int, db: Session) -> int:
    from models import Pet, UserPet
    pet = db.query(Pet).filter(Pet.bonus_kind == bonus_kind).first()
    if pet is None:
        return 0
    up = db.query(UserPet).filter(UserPet.user_id == user_id, UserPet.pet_id == pet.id).first()
    if up is not None:
        return bonus_amount
    return 0


def apply_pet_bonus_harvest(user_id: int, plant_category: str, qty: int, db: Session) -> int:
    if plant_category == "orchard":
        return _get_bonus(user_id, "harvest_orchard", 1, db)
    else:
        return _get_bonus(user_id, "harvest_plot", 1, db)


def apply_pet_bonus_fulfill(user_id: int, db: Session) -> int:
    return _get_bonus(user_id, "order_coins", 5, db)


def apply_pet_bonus_craft(user_id: int, db: Session) -> int:
    return _get_bonus(user_id, "craft_bonus", 1, db)


def apply_pet_bonus_animal_product(user_id: int, db: Session) -> int:
    return _get_bonus(user_id, "animal_product", 1, db)
