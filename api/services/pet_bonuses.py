from sqlalchemy.orm import Session


def apply_pet_bonus_harvest(user_id: int, plant_category: str, qty: int, db: Session) -> int:
    from models import Pet, UserPet
    if plant_category == "orchard":
        pet_code = "fox"
    else:
        pet_code = "iguana"
    pet = db.query(Pet).filter(Pet.code == pet_code).first()
    if pet is None:
        return 0
    up = db.query(UserPet).filter(UserPet.user_id == user_id, UserPet.pet_id == pet.id).first()
    if up is not None:
        return 1
    return 0


def apply_pet_bonus_fulfill(user_id: int, db: Session) -> int:
    from models import Pet, UserPet
    pet = db.query(Pet).filter(Pet.code == "dragon").first()
    if pet is None:
        return 0
    up = db.query(UserPet).filter(UserPet.user_id == user_id, UserPet.pet_id == pet.id).first()
    if up is not None:
        return 5
    return 0


def apply_pet_bonus_craft(user_id: int, db: Session) -> int:
    from models import Pet, UserPet
    pet = db.query(Pet).filter(Pet.code == "raven").first()
    if pet is None:
        return 0
    up = db.query(UserPet).filter(UserPet.user_id == user_id, UserPet.pet_id == pet.id).first()
    if up is not None:
        return 1
    return 0


def apply_pet_bonus_animal_product(user_id: int, db: Session) -> int:
    from models import Pet, UserPet
    pet = db.query(Pet).filter(Pet.code == "cat").first()
    if pet is None:
        return 0
    up = db.query(UserPet).filter(UserPet.user_id == user_id, UserPet.pet_id == pet.id).first()
    if up is not None:
        return 1
    return 0
