from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Field, FieldPet, FOREST_PET_CODES, Pet, PetActionLog, PetForestTask, User, UserPet
from routes.admin_catalog import PetOut, _pet_out
from services.card_draw import pet_settle_norm
from services.msk_time import next_midnight_msk, now_msk

router = APIRouter(prefix="/api/pets", tags=["pets"])

FOREST_FREE_ACTION = "forest_free"
FOREST_PAID_ACTION = "forest_paid"
FOREST_PAID_COST = 200


def _is_forest_pet(pet: Pet) -> bool:
    return (pet.code or "").lower() in FOREST_PET_CODES


def _ensure_forest_pet_catalog(db: Session) -> Pet | None:
    """Находит или создаёт питомца-выдру и привязывает его к Лужайке питомцев."""
    from models import Field, FieldPet

    pet = db.query(Pet).filter(Pet.code.in_(FOREST_PET_CODES)).first()
    if pet is None:
        pet = db.query(Pet).filter(Pet.name.ilike("%выдр%")).first()
    if pet is None:
        pet = Pet(code="vydra", name="Выдра", emoji="🦦")
        db.add(pet)
        db.flush()
    lawn = db.query(Field).filter(Field.field_kind == "lawn").order_by(Field.id.asc()).first()
    if lawn is not None:
        bound = db.query(FieldPet).filter(
            FieldPet.field_id == lawn.id, FieldPet.pet_id == pet.id
        ).first()
        if bound is None:
            db.add(FieldPet(field_id=lawn.id, pet_id=pet.id))
    return pet


def _free_lawn_pet_cell(user_id: int, db: Session) -> int | None:
    from models import FieldCell

    occupied = {
        up.cell_id
        for up in db.query(UserPet).filter(UserPet.user_id == user_id, UserPet.cell_id.isnot(None)).all()
    }
    return next(
        (
            c.id
            for c in db.query(FieldCell).join(Field, Field.id == FieldCell.field_id)
            .filter(Field.field_kind == "lawn", FieldCell.kind == "pet")
            .order_by(FieldCell.id.asc()).all()
            if c.id not in occupied
        ),
        None,
    )


def grant_forest_pet_if_absent(user_id: int, db: Session) -> bool:
    """Выдаёт питомца-выдру (шестого волшебного) и заселяет в свободную клетку Лужайки."""
    pet = _ensure_forest_pet_catalog(db)
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

    db.add(UserPet(user_id=user_id, pet_id=pet.id, cell_id=_free_lawn_pet_cell(user_id, db)))
    db.flush()
    return True


def backfill_forest_pets(db: Session) -> int:
    """Выдаёт выдру игрокам, уже вылечившим выдру до внедрения фичи."""
    from models import ClinicAnimalType, PatientAnimal, UserPatientState

    pet = _ensure_forest_pet_catalog(db)
    if pet is None:
        return 0
    rows = (
        db.query(UserPatientState.user_id, PatientAnimal.name, ClinicAnimalType.name)
        .join(PatientAnimal, PatientAnimal.id == UserPatientState.patient_id)
        .outerjoin(ClinicAnimalType, ClinicAnimalType.id == PatientAnimal.animal_type_id)
        .filter(UserPatientState.status.in_(["treated", "released"]))
        .all()
    )
    user_ids = {
        uid
        for uid, patient_name, type_name in rows
        if "выдр" in (patient_name or "").lower() or "выдр" in (type_name or "").lower()
    }
    granted = 0
    for uid in user_ids:
        exists = db.query(UserPet).filter(
            UserPet.user_id == uid, UserPet.pet_id == pet.id
        ).first()
        if exists is not None:
            continue
        u = db.query(User).filter(User.vk_id == uid).first()
        if u is not None:
            u.unlocked_pets = max(u.unlocked_pets or 0, 6)
        db.add(UserPet(user_id=uid, pet_id=pet.id, cell_id=_free_lawn_pet_cell(uid, db)))
        granted += 1
    db.flush()
    return granted


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


class IngredientOption(BaseModel):
    id: int
    name: str


class ForestActionsOut(BaseModel):
    free_used_today: bool = False
    paid_used_today: bool = False
    sleeping: bool = False
    wake_at: str | None = None
    paid_pending: bool = False
    paid_required: int = 200
    paid_accumulated: int = 0
    paid_task_id: int | None = None
    ingredient_id: int | None = None
    ingredient_name: str | None = None
    pool: list[IngredientOption] = []


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
    task = db.query(PetForestTask).filter(
        PetForestTask.user_id == user_id,
        PetForestTask.pet_id == pet.id,
        PetForestTask.date == today,
        PetForestTask.status == "pending",
    ).first()
    chosen_id = task.ingredient_id if task is not None else None
    chosen_name = None
    if chosen_id is not None:
        from models import Ingredient

        ing = db.query(Ingredient).filter(Ingredient.id == chosen_id).first()
        chosen_name = ing.name if ing is not None else None
    return ForestActionsOut(
        free_used_today=free_used,
        paid_used_today=paid_used,
        sleeping=sleeping,
        wake_at=(next_midnight_msk().isoformat() if sleeping else None),
        paid_pending=task is not None,
        paid_required=task.required if task else FOREST_PAID_COST,
        paid_accumulated=task.accumulated if task else 0,
        paid_task_id=task.id if task else None,
        ingredient_id=chosen_id,
        ingredient_name=chosen_name,
        pool=[IngredientOption(**opt) for opt in _meadow_ingredient_options(db)],
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
    backfill_forest_pets(db)
    _repair_pet_cells(user, db)
    db.commit()
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

    required, cards = pet_settle_norm(db, user, pet_id)
    db.commit()
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
    ingredient_id: int | None = None


class ForestResult(BaseModel):
    pet_id: int
    ingredient_id: int | None = None
    ingredient_name: str | None = None
    apothecary_qty: int | None = None
    paid: bool
    sleeping: bool
    wake_at: str | None = None
    task_id: int | None = None
    required: int | None = None
    paid_pending: bool = False


def _meadow_ingredient_options(db: Session) -> list[dict]:
    from models import GatherCell, GatherCellIngredient, Ingredient

    rows = (
        db.query(Ingredient.id, Ingredient.name)
        .join(GatherCellIngredient, GatherCellIngredient.ingredient_id == Ingredient.id)
        .join(GatherCell, GatherCell.id == GatherCellIngredient.gather_cell_id)
        .join(Field, Field.id == GatherCell.field_id)
        .filter(Field.field_kind == "meadow")
        .distinct()
        .order_by(Ingredient.sort_order.asc(), Ingredient.id.asc())
        .all()
    )
    return [{"id": r[0], "name": r[1]} for r in rows]


def _meadow_ingredient_pool(db: Session) -> list[int]:
    return [opt["id"] for opt in _meadow_ingredient_options(db)]


def _pick_forest_ingredient(db: Session) -> int | None:
    import random

    pool = _meadow_ingredient_pool(db)
    if not pool:
        return None
    return random.choice(pool)


def _grant_forest_ingredient(user_id: int, ingredient_id: int, db: Session) -> int:
    from models import UserIngredient

    row = db.query(UserIngredient).filter(
        UserIngredient.user_id == user_id, UserIngredient.ingredient_id == ingredient_id
    ).first()
    if row is None:
        row = UserIngredient(user_id=user_id, ingredient_id=ingredient_id, qty=0)
        db.add(row)
    row.qty = (row.qty or 0) + 1
    return row.qty or 0


@router.post("/{pet_id}/forest", response_model=ForestResult)
def send_pet_to_forest(
    pet_id: int,
    req: ForestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from models import Ingredient

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

    if not req.paid:
        if free_used:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Бесплатный поход в лес сегодня уже использован. Можно послать повторно за 200 крестиков.",
            )
        picked_id = _pick_forest_ingredient(db)
        if picked_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="В Лесной поляне нет ингредиентов")
        qty = _grant_forest_ingredient(user.vk_id, picked_id, db)
        db.add(PetActionLog(user_id=user.vk_id, pet_id=pet_id, action=FOREST_FREE_ACTION, date=today))
        db.commit()
        ingredient = db.query(Ingredient).filter(Ingredient.id == picked_id).first()
        return ForestResult(
            pet_id=pet_id,
            ingredient_id=picked_id,
            ingredient_name=ingredient.name if ingredient else "?",
            apothecary_qty=qty,
            paid=False,
            sleeping=False,
        )

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

    options = _meadow_ingredient_options(db)
    if not options:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="В Лесной поляне нет ингредиентов")

    chosen_id = req.ingredient_id
    if chosen_id is None:
        if len(options) == 1:
            chosen_id = options[0]["id"]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Выберите ингредиент, который принесёт выдра",
            )
    else:
        if chosen_id not in [opt["id"] for opt in options]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ингредиент не доступен в Лесной поляне",
            )

    task = db.query(PetForestTask).filter(
        PetForestTask.user_id == user.vk_id,
        PetForestTask.pet_id == pet_id,
        PetForestTask.date == today,
    ).first()
    if task is None:
        task = PetForestTask(
            user_id=user.vk_id, pet_id=pet_id, date=today,
            required=FOREST_PAID_COST, accumulated=0, status="pending",
            ingredient_id=chosen_id,
        )
        db.add(task)
    elif task.ingredient_id is None:
        task.ingredient_id = chosen_id
    db.commit()
    chosen_name = next((opt["name"] for opt in options if opt["id"] == chosen_id), "?")
    return ForestResult(
        pet_id=pet_id,
        ingredient_id=chosen_id,
        ingredient_name=chosen_name,
        paid=True,
        sleeping=False,
        task_id=task.id,
        required=task.required or FOREST_PAID_COST,
        paid_pending=True,
    )


def complete_forest_paid(user_id: int, task_id: int, amount: int, db: Session) -> None:
    """Выполняет платный поход выдры после фото-отчёта на норму крестиков."""
    task = db.query(PetForestTask).filter(
        PetForestTask.id == task_id, PetForestTask.user_id == user_id
    ).first()
    if task is None or task.status != "pending":
        return
    task.accumulated = (task.accumulated or 0) + amount
    if task.accumulated < (task.required or 0):
        db.commit()
        return
    task.status = "done"
    today = now_msk().date().isoformat()
    paid_used = db.query(PetActionLog).filter(
        PetActionLog.user_id == user_id,
        PetActionLog.pet_id == task.pet_id,
        PetActionLog.action == FOREST_PAID_ACTION,
        PetActionLog.date == today,
    ).first()
    if paid_used is None:
        picked_id = task.ingredient_id or _pick_forest_ingredient(db)
        if picked_id is not None:
            _grant_forest_ingredient(user_id, picked_id, db)
        db.add(PetActionLog(user_id=user_id, pet_id=task.pet_id, action=FOREST_PAID_ACTION, date=today))
    db.commit()
