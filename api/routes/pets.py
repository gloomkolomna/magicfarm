from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Field, FieldPet, Pet, User, UserPet
from routes.admin_catalog import PetOut, _pet_out
from services.card_draw import calculate_norm, cards_to_json, draw_cards

router = APIRouter(prefix="/api/pets", tags=["pets"])


@router.get("/catalog", response_model=list[PetOut])
def list_available_pets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Питомцы, доступные игроку: привязанные к локациям «Лужайка», иначе весь каталог."""
    bound = db.query(Pet).join(FieldPet, FieldPet.pet_id == Pet.id).join(
        Field, Field.id == FieldPet.field_id
    ).filter(Field.field_kind == "lawn").distinct().all()
    if bound:
        return [_pet_out(p) for p in bound]
    return [_pet_out(p) for p in db.query(Pet).order_by(Pet.id.asc()).all()]


class UserPetOut(BaseModel):
    id: int
    pet_id: int
    pet_name: str
    pet_emoji: str | None
    bonus_description: str | None
    acquired_at: str | None
    cell_id: int | None = None


def _up_out(up: UserPet) -> UserPetOut:
    return UserPetOut(
        id=up.id, pet_id=up.pet_id,
        pet_name=up.pet.name, pet_emoji=up.pet.emoji,
        bonus_description=up.pet.bonus_description,
        acquired_at=up.acquired_at.isoformat() if up.acquired_at else None,
        cell_id=up.cell_id,
    )


def _repair_pet_cells(user: User, db: Session) -> None:
    """Чинит битые привязки user_pets.cell_id после переразметки pet-клеток.

    Клетка, которая не является pet-клеткой (или не существует), сбрасывается;
    питомцы без клетки автоматически заселяются в первую свободную pet-клетку Лужаек.
    """
    from models import Field, FieldCell

    ups = db.query(UserPet).filter(UserPet.user_id == user.vk_id).all()
    if not ups:
        return

    changed = False
    for up in ups:
        if up.cell_id is not None:
            cell = db.query(FieldCell).filter(FieldCell.id == up.cell_id).first()
            if cell is None or cell.kind != "pet":
                up.cell_id = None
                changed = True

    occupied = {up.cell_id for up in ups if up.cell_id is not None}
    free_cells = [
        c.id for c in db.query(FieldCell).join(Field, Field.id == FieldCell.field_id)
        .filter(Field.field_kind == "lawn", FieldCell.kind == "pet")
        .order_by(FieldCell.id.asc()).all()
        if c.id not in occupied
    ]

    for up in ups:
        if up.cell_id is None and free_cells:
            up.cell_id = free_cells.pop(0)
            changed = True

    if changed:
        db.commit()


@router.get("", response_model=list[UserPetOut])
def list_pets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _repair_pet_cells(user, db)
    rows = db.query(UserPet).filter(UserPet.user_id == user.vk_id).all()
    return [_up_out(up) for up in rows]


class SettleRequest(BaseModel):
    pet_id: int


def _draw_settle(db: Session, user: User, pet_id: int):
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Питомец не найден")

    existing = db.query(UserPet).filter(
        UserPet.user_id == user.vk_id, UserPet.pet_id == pet_id
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот питомец уже заселён")

    current_count = db.query(UserPet).filter(UserPet.user_id == user.vk_id).count()
    if current_count >= (user.unlocked_pets or 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет свободных слотов для питомцев. Повысьте уровень, чтобы открыть новые.",
        )

    cards = draw_cards(db, 10, False)
    required = calculate_norm(db, user, cards)
    return pet, cards, required


@router.post("/settle", response_model=dict, status_code=status.HTTP_201_CREATED)
def settle_pet(
    req: SettleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pet, cards, required = _draw_settle(db, user, req.pet_id)
    return {
        "pet_id": req.pet_id,
        "pet_name": pet.name,
        "drawn_cards": cards,
        "required": required,
    }


@router.post("/cells/{cell_id}/settle", response_model=dict, status_code=status.HTTP_201_CREATED)
def settle_pet_on_cell(
    cell_id: int,
    req: SettleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from models import FieldCell
    cell = db.query(FieldCell).filter(FieldCell.id == cell_id).first()
    if cell is None or cell.kind != "pet":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клетка питомца не найдена")

    occupied = db.query(UserPet).filter(
        UserPet.user_id == user.vk_id, UserPet.cell_id == cell.id
    ).first()
    if occupied is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Эта клетка уже занята питомцем")

    pet, cards, required = _draw_settle(db, user, req.pet_id)

    return {
        "pet_id": req.pet_id,
        "pet_name": pet.name,
        "drawn_cards": cards,
        "required": required,
        "cell_id": cell.id,
    }
