from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Field, FieldPet, FOREST_PET_CODES, Pet, PetActionLog, User, UserPet
from routes.admin_catalog import PetOut, _pet_out
from services.card_draw import calculate_norm, cards_to_json, draw_cards
from services.msk_time import next_midnight_msk, now_msk

router = APIRouter(prefix="/api/pets", tags=["pets"])

FOREST_FREE_ACTION = "forest_free"
FOREST_PAID_ACTION = "forest_paid"
FOREST_PAID_COST = 200


def _is_forest_pet(pet: Pet) -> bool:
    return (pet.code or "").lower() in FOREST_PET_CODES


def grant_forest_pet_if_absent(user_id: int, db: Session) -> bool:
    """Выдаёт питомца-выдру (шестого волшебного) и заселяет в свободную клетку Лужайки."""
    from models import FieldCell

    pet = db.query(Pet).filter(Pet.code.in_(FOREST_PET_CODES)).first()
    if pet is None:
        pet = db.query(Pet).filter(Pet.name.ilike("%выдр%")).first()
    if pet is None:
        return False
    exists = db.query(UserPet).filter(
        UserPet.user_id == user_id, UserPet.pet_id == pet.id
    ).first()
    if exists is not None:
        return False

    u = db.query(User).filter(User.vk_id == user_id).first()
    if u is not None:
        u.unlocked_pets = max(u.unlocked_pets or 0, 6)

    ups = db.query(UserPet).filter(UserPet.user_id == user_id).all()
    occupied = {up.cell_id for up in ups if up.cell_id is not None}
    free_cell = next(
        (
            c.id for c in db.query(FieldCell).join(Field, Field.id == FieldCell.field_id)
            .filter(Field.field_kind == "lawn", FieldCell.kind == "pet")
            .order_by(FieldCell.id.asc()).all()
            if c.id not in occupied
        ),
        None,
    )
    db.add(UserPet(user_id=user_id, pet_id=pet.id, cell_id=free_cell))
    db.flush()
    return True


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


class ForestActionsOut(BaseModel):
    free_used_today: bool = False
    paid_used_today: bool = False
    sleeping: bool = False
    wake_at: str | None = None


class UserPetOut(BaseModel):
    id: int
    pet_id: int
    pet_name: str
    pet_emoji: str | None
    bonus_description: str | None
    acquired_at: str | None
    cell_id: int | None = None
    code: str | None = None
    forest: ForestActionsOut | None = None


def _forest_actions_out(user_id: int, pet: Pet, db: Session) -> ForestActionsOut:
    today = now_msk().date().isoformat()
    logs = {
        log.action for log in db.query(PetActionLog).filter(
            PetActionLog.user_id == user_id,
            PetActionLog.pet_id == pet.id,
            PetActionLog.date == today,
        ).all()
    }
    free_used = FOREST_FREE_ACTION in logs
    paid_used = FOREST_PAID_ACTION in logs
    sleeping = free_used and paid_used
    return ForestActionsOut(
        free_used_today=free_used,
        paid_used_today=paid_used,
        sleeping=sleeping,
        wake_at=(next_midnight_msk().isoformat() if sleeping else None),
    )


def _up_out(up: UserPet, db: Session | None = None) -> UserPetOut:
    return UserPetOut(
        id=up.id, pet_id=up.pet_id,
        pet_name=up.pet.name, pet_emoji=up.pet.emoji,
        bonus_description=up.pet.bonus_description,
        acquired_at=up.acquired_at.isoformat() if up.acquired_at else None,
        cell_id=up.cell_id,
        code=up.pet.code,
        forest=(_forest_actions_out(up.user_id, up.pet, db) if db is not None and _is_forest_pet(up.pet) else None),
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
    return [_up_out(up, db) for up in rows]


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


class ForestRequest(BaseModel):
    paid: bool = False


class ForestResult(BaseModel):
    pet_id: int
    ingredient_id: int
    ingredient_name: str
    apothecary_qty: int
    paid: bool
    sleeping: bool
    wake_at: str | None


def _meadow_ingredient_pool(db: Session) -> list[int]:
    from models import GatherCell, GatherCellIngredient

    rows = (
        db.query(GatherCellIngredient.ingredient_id)
        .join(GatherCell, GatherCell.id == GatherCellIngredient.gather_cell_id)
        .join(Field, Field.id == GatherCell.field_id)
        .filter(Field.field_kind == "meadow")
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


@router.post("/{pet_id}/forest", response_model=ForestResult)
def send_pet_to_forest(
    pet_id: int,
    req: ForestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import random

    from models import Ingredient, UserIngredient

    up = db.query(UserPet).filter(
        UserPet.user_id == user.vk_id, UserPet.pet_id == pet_id
    ).first()
    if up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Питомец не найден")
    if not _is_forest_pet(up.pet):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот питомец не ходит в лес")

    today = now_msk().date().isoformat()
    logs = {
        log.action for log in db.query(PetActionLog).filter(
            PetActionLog.user_id == user.vk_id,
            PetActionLog.pet_id == pet_id,
            PetActionLog.date == today,
        ).all()
    }
    free_used = FOREST_FREE_ACTION in logs
    paid_used = FOREST_PAID_ACTION in logs
    if free_used and paid_used:
        wake_at = next_midnight_msk()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Питомец спит. Проснётся в {wake_at.strftime('%H:%M')} МСК",
        )

    if not req.paid:
        if free_used:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Бесплатный поход в лес сегодня уже использован. Можно послать повторно за 200 крестиков.",
            )
        action = FOREST_FREE_ACTION
    else:
        if paid_used:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Платный поход в лес сегодня уже использован.",
            )
        if not free_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Сначала отправьте питомца в лес бесплатно",
            )
        if (user.crosses_balance or 0) < FOREST_PAID_COST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно крестиков (нужно {FOREST_PAID_COST})",
            )
        user.crosses_balance = (user.crosses_balance or 0) - FOREST_PAID_COST
        action = FOREST_PAID_ACTION

    pool = _meadow_ingredient_pool(db)
    if not pool:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="В Лесной поляне нет ингредиентов")

    picked_id = random.choice(pool)
    row = db.query(UserIngredient).filter(
        UserIngredient.user_id == user.vk_id, UserIngredient.ingredient_id == picked_id
    ).first()
    if row is None:
        row = UserIngredient(user_id=user.vk_id, ingredient_id=picked_id, qty=0)
        db.add(row)
    row.qty = (row.qty or 0) + 1

    db.add(PetActionLog(user_id=user.vk_id, pet_id=pet_id, action=action, date=today))
    db.commit()

    ingredient = db.query(Ingredient).filter(Ingredient.id == picked_id).first()
    logs.add(action)
    sleeping = FOREST_FREE_ACTION in logs and FOREST_PAID_ACTION in logs
    return ForestResult(
        pet_id=pet_id,
        ingredient_id=picked_id,
        ingredient_name=ingredient.name if ingredient else "?",
        apothecary_qty=row.qty or 0,
        paid=req.paid,
        sleeping=sleeping,
        wake_at=(next_midnight_msk().isoformat() if sleeping else None),
    )
