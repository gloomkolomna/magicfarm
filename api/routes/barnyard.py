from __future__ import annotations
import datetime
import random

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import (
    Animal, BarnyardSlot, BarnyardStorage, BarnyardWithdrawal,
    Field, FieldAnimal, FieldCell, Inventory, Product, User,
    UserAnimalOpening,
)
from routes.admin_catalog import AnimalOut, _animal_out
from routes.settings import get_animal_product_norm
from services.achievements import check_and_award
from services.card_draw import calculate_norm, cards_to_json, draw_cards
from services.pet_bonuses import apply_pet_bonus_animal_product
from services.potion_bonuses import consume_potion, is_potion_active

router = APIRouter(prefix="/api/animals", tags=["animals"])

MAX_DIE = 6


def _roll_die() -> int:
    return random.randint(1, MAX_DIE)


def _slot_is_ghost(s: BarnyardSlot, db: Session) -> bool:
    if s.cell_id is None:
        return True
    cell = db.query(FieldCell).filter(FieldCell.id == s.cell_id).first()
    if cell is None or cell.kind != "barnyard":
        return True
    field = cell.field
    return field is None or cell.col >= field.cols or cell.row >= field.rows


def purge_ghost_slots(db: Session, user: User) -> int:
    """Удаляет загоны-призраки игрока: слоты без клетки, с перекрашенной/удалённой
    клеткой или клеткой за пределами сетки поля. Такие слоты не видны в игре,
    но занимают лимит загонов и блокируют повторное заселение животного."""
    removed = 0
    for s in db.query(BarnyardSlot).filter(BarnyardSlot.user_id == user.vk_id).all():
        if _slot_is_ghost(s, db):
            db.delete(s)
            removed += 1
    if removed:
        db.commit()
    return removed


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
    drawn_cards_json: str | None
    opening_order: int | None
    cell_id: int | None = None
    image_pen_url: str | None = None
    image_empty_pen_url: str | None = None


def _slot_out(s: BarnyardSlot) -> BarnyardOut:
    return BarnyardOut(
        id=s.id, animal_id=s.animal_id,
        animal_name=s.animal.name if s.animal else None,
        animal_emoji=s.animal.emoji if s.animal else None,
        status=s.status, accumulated=s.accumulated,
        required=s.required,
        drawn_cards_json=s.drawn_cards_json,
        opening_order=s.opening_order,
        cell_id=s.cell_id,
        image_pen_url=s.animal.image_pen_url if s.animal else None,
        image_empty_pen_url=s.animal.image_empty_pen_url if s.animal else None,
    )


class InstallRequest(BaseModel):
    animal_id: int


def _check_barnyard_limit(db: Session, user: User) -> None:
    occupied = db.query(BarnyardSlot).filter(
        BarnyardSlot.user_id == user.vk_id, BarnyardSlot.animal_id.isnot(None)
    ).count()
    if occupied >= (user.unlocked_barnyard or 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет открытых загонов. Повысьте уровень (прокачка «Животноводство»).",
        )


@router.post("/cells/{cell_id}/install", response_model=BarnyardOut)
def install_animal_on_cell(
    cell_id: int,
    req: InstallRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cell = db.query(FieldCell).filter(FieldCell.id == cell_id).first()
    if cell is None or cell.kind != "barnyard":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Загон не найден")

    purge_ghost_slots(db, user)

    slot = db.query(BarnyardSlot).filter(
        BarnyardSlot.user_id == user.vk_id, BarnyardSlot.cell_id == cell.id
    ).first()
    if slot is None:
        slot = BarnyardSlot(user_id=user.vk_id, cell_id=cell.id, status="empty")
        db.add(slot)
        db.flush()
    if slot.animal_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Загон уже занят")

    animal = db.query(Animal).filter(Animal.id == req.animal_id).first()
    if animal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Животное не найдено")
    existing = db.query(BarnyardSlot).filter(
        BarnyardSlot.user_id == user.vk_id, BarnyardSlot.animal_id == animal.id
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Это животное уже заселено")

    _check_barnyard_limit(db, user)

    opening = db.query(UserAnimalOpening).filter(
        UserAnimalOpening.user_id == user.vk_id,
        UserAnimalOpening.animal_id == animal.id,
    ).first()
    if opening is None:
        max_order = db.query(func.max(UserAnimalOpening.opening_order)).filter(
            UserAnimalOpening.user_id == user.vk_id
        ).scalar() or 0
        opening = UserAnimalOpening(
            user_id=user.vk_id, animal_id=animal.id, opening_order=max_order + 1
        )
        db.add(opening)
        db.flush()

    slot.animal_id = animal.id
    slot.status = "placed"
    slot.required = 0
    slot.accumulated = 0
    slot.drawn_cards_json = None
    slot.opening_order = opening.opening_order

    db.commit()
    db.refresh(slot)
    return _slot_out(slot)


@router.post("/pens/{slot_id}/prepare", response_model=BarnyardOut)
def prepare_pen(
    slot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    slot = db.query(BarnyardSlot).filter(
        BarnyardSlot.id == slot_id, BarnyardSlot.user_id == user.vk_id
    ).first()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Загон не найден")
    if slot.status != "placed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Загон не ждёт подготовки")

    cards = draw_cards(db, 5, True)
    required = calculate_norm(db, user, cards)

    skip = is_potion_active(user.vk_id, "skip_animal_stitch", db)
    if skip:
        required = 0

    slot.required = required
    slot.accumulated = 0
    slot.drawn_cards_json = cards_to_json(cards)
    slot.status = "ready" if skip else "building"

    if skip:
        consume_potion(user.vk_id, "skip_animal_stitch", db)

    db.commit()
    db.refresh(slot)

    check_and_award(user.vk_id, "animals_count", db)

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

    product = db.query(Product).filter(Product.animal_id == slot.animal_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="У животного нет продукции")

    die = _roll_die()
    qty = die + apply_pet_bonus_animal_product(user.vk_id, db)
    if is_potion_active(user.vk_id, "double_animal_product", db):
        qty = qty * 2
        consume_potion(user.vk_id, "double_animal_product", db)

    storage = db.query(BarnyardStorage).filter(
        BarnyardStorage.user_id == user.vk_id, BarnyardStorage.product_id == product.id
    ).first()
    if storage is None:
        storage = BarnyardStorage(user_id=user.vk_id, product_id=product.id, qty=0)
        db.add(storage)
    storage.qty = (storage.qty or 0) + qty

    db.commit()

    return {
        "slot_id": slot.id,
        "die": die,
        "qty_added": qty,
        "product_id": product.id,
        "product_name": product.name,
        "storage_qty": storage.qty,
    }


@router.delete("/pens/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def release_pen(
    slot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Выселить животное: загон освобождается полностью, прогресс теряется."""
    slot = db.query(BarnyardSlot).filter(
        BarnyardSlot.id == slot_id, BarnyardSlot.user_id == user.vk_id
    ).first()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Загон не найден")
    db.delete(slot)
    db.commit()
    return None


class StorageItemOut(BaseModel):
    product_id: int
    product_name: str
    product_emoji: str | None
    product_image_url: str | None = None
    qty: int
    price_per_unit: int | None = None


class WithdrawalOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    product_emoji: str | None
    qty: int
    required: int
    status: str
    created_at: datetime.datetime | None


def _wd_out(w: BarnyardWithdrawal) -> WithdrawalOut:
    return WithdrawalOut(
        id=w.id, product_id=w.product_id,
        product_name=w.product.name if w.product else "?",
        product_emoji=w.product.emoji if w.product else None,
        qty=w.qty, required=w.required, status=w.status,
        created_at=w.created_at,
    )


@router.get("/tents/storage")
def tent_storage(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = db.query(BarnyardStorage).filter(
        BarnyardStorage.user_id == user.vk_id, BarnyardStorage.qty > 0
    ).all()
    pending = db.query(BarnyardWithdrawal).filter(
        BarnyardWithdrawal.user_id == user.vk_id, BarnyardWithdrawal.status == "pending"
    ).order_by(BarnyardWithdrawal.id.asc()).all()
    from services.pricing import animal_product_unit_price
    return {
        "items": [
            StorageItemOut(
                product_id=i.product_id,
                product_name=i.product.name if i.product else "?",
                product_emoji=i.product.emoji if i.product else None,
                product_image_url=i.product.image_url if i.product else None,
                qty=i.qty,
                price_per_unit=animal_product_unit_price(
                    db, user.vk_id, i.product.animal_id if i.product else None,
                    i.product.production_kind if i.product else None,
                ),
            ).model_dump()
            for i in items
        ],
        "pending": [_wd_out(w).model_dump() for w in pending],
        "norm_per_unit": get_animal_product_norm(user),
    }


class WithdrawRequest(BaseModel):
    product_id: int
    qty: int


@router.post("/tents/withdraw", response_model=WithdrawalOut)
def withdraw_from_tent(
    req: WithdrawRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.qty < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Количество должно быть от 1")

    storage = db.query(BarnyardStorage).filter(
        BarnyardStorage.user_id == user.vk_id, BarnyardStorage.product_id == req.product_id
    ).first()
    pending_qty = db.query(BarnyardWithdrawal).filter(
        BarnyardWithdrawal.user_id == user.vk_id,
        BarnyardWithdrawal.product_id == req.product_id,
        BarnyardWithdrawal.status == "pending",
    ).all()
    reserved = sum(w.qty for w in pending_qty)

    available = (storage.qty if storage else 0) - reserved
    if available < req.qty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недостаточно продукции на складе шатра: доступно {max(0, available)}",
        )

    required = get_animal_product_norm(user) * req.qty
    w = BarnyardWithdrawal(
        user_id=user.vk_id, product_id=req.product_id,
        qty=req.qty, required=required, status="pending",
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return _wd_out(w)


def complete_withdrawal(user_id: int, withdrawal_id: int, db: Session) -> None:
    w = db.query(BarnyardWithdrawal).filter(
        BarnyardWithdrawal.id == withdrawal_id, BarnyardWithdrawal.user_id == user_id
    ).first()
    if w is None or w.status != "pending":
        return
    storage = db.query(BarnyardStorage).filter(
        BarnyardStorage.user_id == user_id, BarnyardStorage.product_id == w.product_id
    ).first()
    if storage is not None:
        storage.qty = (storage.qty or 0) - w.qty
        if storage.qty <= 0:
            db.delete(storage)
    inv = db.query(Inventory).filter(
        Inventory.user_id == user_id, Inventory.product_id == w.product_id
    ).first()
    if inv is None:
        inv = Inventory(user_id=user_id, product_id=w.product_id, qty=0)
        db.add(inv)
    inv.qty = (inv.qty or 0) + w.qty
    w.status = "done"
    db.commit()
