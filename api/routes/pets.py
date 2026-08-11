from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Pet, User, UserPet
from services.card_draw import calculate_norm, cards_to_json, draw_cards

router = APIRouter(prefix="/api/pets", tags=["pets"])


class UserPetOut(BaseModel):
    id: int
    pet_id: int
    pet_name: str
    pet_emoji: str | None
    bonus_description: str | None
    acquired_at: str | None


def _up_out(up: UserPet) -> UserPetOut:
    return UserPetOut(
        id=up.id, pet_id=up.pet_id,
        pet_name=up.pet.name, pet_emoji=up.pet.emoji,
        bonus_description=up.pet.bonus_description,
        acquired_at=up.acquired_at.isoformat() if up.acquired_at else None,
    )


@router.get("", response_model=list[UserPetOut])
def list_pets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(UserPet).filter(UserPet.user_id == user.vk_id).all()
    return [_up_out(up) for up in rows]


class SettleRequest(BaseModel):
    pet_id: int


@router.post("/settle", response_model=dict, status_code=status.HTTP_201_CREATED)
def settle_pet(
    req: SettleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pet = db.query(Pet).filter(Pet.id == req.pet_id).first()
    if pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Питомец не найден")

    existing = db.query(UserPet).filter(
        UserPet.user_id == user.vk_id, UserPet.pet_id == req.pet_id
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот питомец уже заселён")

    cards = draw_cards(db, 10, False)
    required = calculate_norm(db, user, cards)

    return {
        "pet_id": req.pet_id,
        "pet_name": pet.name,
        "drawn_cards": cards,
        "required": required,
    }
