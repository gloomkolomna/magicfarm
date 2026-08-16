from __future__ import annotations
import random

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Animal, BarnyardSlot, Field, FieldAnimal, Inventory, User
from routes.admin_catalog import AnimalOut, _animal_out
from services.achievements import check_and_award
from services.card_draw import calculate_norm, cards_to_json, draw_cards
from services.potion_bonuses import consume_potion, is_potion_active

router = APIRouter(prefix="/api/animals", tags=["animals"])

MAX_DIE = 6


def _roll_die(exclude: int | None = None) -> int:
    values = [v for v in range(1, MAX_DIE + 1) if v != exclude]
    return random.choice(values)


@router.get("", response_model=list[AnimalOut])
def list_available_animals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Животные, доступные игроку: привязанные к локациям «Скотный двор», иначе весь каталог."""
    bound = db.query(Animal).join(FieldAnimal, FieldAnimal.animal_id == Animal.id).join(
        Field, Field.id == FieldAnimal.field_id
    ).filter(Field.field_kind == "barnyard").distinct().all()
    if bound:
        return [_animal_out(a) for a in bound]
    return [_animal_out(a) for a in db.query(Animal).order_by(Animal.sort_order.asc(), Animal.id.asc()).all()]


class BarnyardOut(BaseModel):
    id: int
    animal_id: int | None
    animal_name: str | None
    animal_emoji: str | None
    status: str
    accumulated: int
    required: int
    last_die: int | None
    drawn_cards_json: str | None
    opening_order: int | None
    cell_id: int | None = None


def _slot_out(s: BarnyardSlot) -> BarnyardOut:
    return BarnyardOut(
        id=s.id, animal_id=s.animal_id,
        animal_name=s.animal.name if s.animal else None,
        animal_emoji=s.animal.emoji if s.animal else None,
        status=s.status, accumulated=s.accumulated,
        required=s.required, last_die=s.last_die,
        drawn_cards_json=s.drawn_cards_json,
        opening_order=s.opening_order,
        cell_id=s.cell_id,
    )


@router.get("/pens", response_model=list[BarnyardOut])
def list_pens(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    slots = db.query(BarnyardSlot).filter(BarnyardSlot.user_id == user.vk_id).order_by(BarnyardSlot.id.asc()).all()
    current_count = len(slots)
    target = user.unlocked_barnyard or 0
    if current_count < target:
        for _ in range(target - current_count):
            s = BarnyardSlot(user_id=user.vk_id, status="empty")
            db.add(s)
        db.commit()
        slots = db.query(BarnyardSlot).filter(BarnyardSlot.user_id == user.vk_id).order_by(BarnyardSlot.id.asc()).all()
    return [_slot_out(s) for s in slots]


class InstallRequest(BaseModel):
    animal_id: int


def _install_into_slot(db: Session, user: User, slot: BarnyardSlot, animal_id: int) -> BarnyardSlot:
    animal = db.query(Animal).filter(Animal.id == animal_id).first()
    if animal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Животное не найдено")

    existing = db.query(BarnyardSlot).filter(
        BarnyardSlot.user_id == user.vk_id, BarnyardSlot.animal_id == animal_id
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Это животное уже заселено")

    cards = draw_cards(db, 5, True)
    required = calculate_norm(db, user, cards)

    skip = is_potion_active(user.vk_id, "skip_animal_stitch", db)
    if skip:
        required = 0

    slot.animal_id = animal_id
    slot.status = "ready" if skip else "building"
    slot.required = required
    slot.accumulated = 0
    slot.drawn_cards_json = cards_to_json(cards)
    slot.opening_order = db.query(BarnyardSlot).filter(
        BarnyardSlot.user_id == user.vk_id,
        BarnyardSlot.animal_id.isnot(None),
    ).count() + 1

    if skip:
        consume_potion(user.vk_id, "skip_animal_stitch", db)

    db.commit()
    db.refresh(slot)

    check_and_award(user.vk_id, "animals_count", db)

    return slot


@router.post("/pens/{slot_id}/install", response_model=BarnyardOut)
def install_animal(
    slot_id: int,
    req: InstallRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    slot = db.query(BarnyardSlot).filter(
        BarnyardSlot.id == slot_id, BarnyardSlot.user_id == user.vk_id
    ).first()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Загон не найден")
    if slot.status != "empty":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Загон уже занят или строится")

    _install_into_slot(db, user, slot, req.animal_id)
    return _slot_out(slot)


@router.post("/cells/{cell_id}/install", response_model=BarnyardOut)
def install_animal_on_cell(
    cell_id: int,
    req: InstallRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from models import FieldCell
    cell = db.query(FieldCell).filter(FieldCell.id == cell_id).first()
    if cell is None or cell.kind != "barnyard":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Загон не найден")

    slot = db.query(BarnyardSlot).filter(
        BarnyardSlot.user_id == user.vk_id, BarnyardSlot.cell_id == cell.id
    ).first()
    if slot is None:
        slot = BarnyardSlot(user_id=user.vk_id, cell_id=cell.id, status="empty")
        db.add(slot)
        db.flush()
    if slot.animal_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Загон уже занят")

    occupied = db.query(BarnyardSlot).filter(
        BarnyardSlot.user_id == user.vk_id, BarnyardSlot.animal_id.isnot(None)
    ).count()
    if occupied >= (user.unlocked_barnyard or 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет открытых загонов. Повысьте уровень (прокачка «Животноводство»).",
        )

    _install_into_slot(db, user, slot, req.animal_id)
    return _slot_out(slot)


class InvestRequest(BaseModel):
    amount: int


@router.post("/pens/{slot_id}/invest", response_model=BarnyardOut)
def invest_pen(
    slot_id: int,
    req: InvestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    slot = db.query(BarnyardSlot).filter(
        BarnyardSlot.id == slot_id, BarnyardSlot.user_id == user.vk_id
    ).first()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Загон не найден")
    if slot.status != "building":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Загон не в стадии строительства")
    if req.amount < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Минимум 1 крестик")

    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    if (u.crosses_balance or 0) < req.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недостаточно крестиков")

    u.crosses_balance = (u.crosses_balance or 0) - req.amount
    slot.accumulated = (slot.accumulated or 0) + req.amount

    if slot.accumulated >= slot.required:
        slot.status = "ready"

    db.commit()
    db.refresh(slot)
    return _slot_out(slot)


@router.post("/pens/{slot_id}/produce", response_model=dict)
def produce(
    slot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    slot = db.query(BarnyardSlot).filter(
        BarnyardSlot.id == slot_id, BarnyardSlot.user_id == user.vk_id
    ).first()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Загон не найден")
    if slot.status != "ready":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Загон не готов к производству")

    die = _roll_die(slot.last_die)
    slot.last_die = die

    from routes.settings import get_dice_norm
    required = get_dice_norm(user) * die
    slot.required = required
    slot.accumulated = 0

    product_coins = (slot.opening_order or 1) * 5
    if is_potion_active(user.vk_id, "double_animal_product", db):
        product_coins = product_coins * 2
        consume_potion(user.vk_id, "double_animal_product", db)

    db.commit()
    db.refresh(slot)

    return {
        "slot_id": slot.id,
        "die": die,
        "required": required,
        "animal_name": slot.animal.name,
        "product_coins": product_coins,
    }
