from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import (
    Field, Inventory, PatientAnimal, Remedy, User, UserCard, UserIngredient,
    UserPatientState, UserRemedyCard,
)
from routes.admin_fields import _get_field_or_404
from routes.ingredients import ApothecaryItemOut, _apothecary_item_out

router = APIRouter(prefix="/api", tags=["remedy-lab"])


def _check_field_gate(f: Field, user: User) -> None:
    if f.min_level is not None and (user.level or 0) < f.min_level:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Эта локация пока недоступна")


class RecipeItemOut(BaseModel):
    ingredient_id: int | None
    ingredient_name: str | None
    plant_id: int | None
    plant_name: str | None
    qty: int


class RemedyCardOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_level: int
    remedy_id: int
    remedy_name: str
    remedy_image_url: str | None
    recipe_items: list[RecipeItemOut]


class RemedyLabOut(BaseModel):
    field_id: int
    name: str
    map_url: str | None
    cols: int
    rows: int
    remedy_cards: list[RemedyCardOut]
    apothecary: list[ApothecaryItemOut]


def _remedy_card_out(card: UserRemedyCard) -> RemedyCardOut:
    remedy = card.remedy
    patient = card.patient
    return RemedyCardOut(
        id=card.id,
        patient_id=card.patient_id,
        patient_name=patient.name if patient else "",
        patient_level=patient.level if patient else 0,
        remedy_id=card.remedy_id,
        remedy_name=remedy.name if remedy else "",
        remedy_image_url=remedy.image_url if remedy else None,
        recipe_items=[
            RecipeItemOut(
                ingredient_id=item.ingredient_id,
                ingredient_name=item.ingredient.name if item.ingredient else None,
                plant_id=item.plant_id,
                plant_name=item.plant.name if item.plant else None,
                qty=item.qty,
            )
            for item in (remedy.recipe_items if remedy else [])
        ],
    )


@router.get("/remedy-lab/{field_id}", response_model=RemedyLabOut)
def get_remedy_lab(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = _get_field_or_404(field_id, db)
    if f.field_kind != "remedy_lab":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Это не лаборатория снадобий")
    _check_field_gate(f, user)

    cards = db.query(UserRemedyCard).filter(
        UserRemedyCard.user_id == user.vk_id
    ).order_by(UserRemedyCard.id.asc()).all()
    apo = db.query(UserIngredient).filter(
        UserIngredient.user_id == user.vk_id, UserIngredient.qty > 0
    ).all()
    return RemedyLabOut(
        field_id=f.id, name=f.name, map_url=f.map_url, cols=f.cols, rows=f.rows,
        remedy_cards=[_remedy_card_out(c) for c in cards],
        apothecary=[_apothecary_item_out(ui) for ui in apo],
    )


class BrewResult(BaseModel):
    card_id: int
    patient_id: int
    patient_name: str
    remedy_name: str
    status: str


@router.post("/remedy-cards/{card_id}/brew", response_model=BrewResult)
def brew_remedy(
    card_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    card = db.query(UserRemedyCard).filter(
        UserRemedyCard.id == card_id, UserRemedyCard.user_id == user.vk_id
    ).first()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Карточка рецепта не найдена")

    patient = card.patient
    if patient is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пациент не найден")

    state = db.query(UserPatientState).filter(
        UserPatientState.user_id == user.vk_id, UserPatientState.patient_id == patient.id
    ).first()
    if state is not None and state.status in ("treated", "released"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пациент уже вылечен")

    remedy = card.remedy
    if remedy is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Мазь не найдена")

    def _source(item) -> tuple[int, str]:
        if item.ingredient_id is not None:
            row = db.query(UserIngredient).filter(
                UserIngredient.user_id == user.vk_id,
                UserIngredient.ingredient_id == item.ingredient_id,
            ).first()
            return (row.qty if row else 0), (item.ingredient.name if item.ingredient else "ингредиент")
        row = db.query(Inventory).filter(
            Inventory.user_id == user.vk_id, Inventory.plant_id == item.plant_id
        ).first()
        return (row.qty if row else 0), (item.plant.name if item.plant else "растение")

    for item in remedy.recipe_items:
        have, name = _source(item)
        if have < item.qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно «{name}» (нужно {item.qty}, есть {have})",
            )

    for item in remedy.recipe_items:
        if item.ingredient_id is not None:
            row = db.query(UserIngredient).filter(
                UserIngredient.user_id == user.vk_id,
                UserIngredient.ingredient_id == item.ingredient_id,
            ).first()
            row.qty = (row.qty or 0) - item.qty
        else:
            row = db.query(Inventory).filter(
                Inventory.user_id == user.vk_id, Inventory.plant_id == item.plant_id
            ).first()
            row.qty = (row.qty or 0) - item.qty

    if state is None:
        state = UserPatientState(user_id=user.vk_id, patient_id=patient.id, status="treated", healed_at=datetime.datetime.utcnow())
        db.add(state)
    else:
        state.status = "treated"
        state.healed_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(state)

    return BrewResult(
        card_id=card.id,
        patient_id=patient.id,
        patient_name=patient.name,
        remedy_name=remedy.name,
        status="treated",
    )


class CollectionCardOut(BaseModel):
    patient_id: int
    patient_name: str
    level: int
    card_image_url: str | None
    earned: bool


class CollectionLevelOut(BaseModel):
    level: int
    earned_count: int
    total_count: int
    cards: list[CollectionCardOut]


class CollectionOut(BaseModel):
    levels: list[CollectionLevelOut]


@router.get("/collection", response_model=CollectionOut)
def get_collection(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patients = db.query(PatientAnimal).order_by(
        PatientAnimal.level.asc(), PatientAnimal.id.asc()
    ).all()
    earned = {
        c.patient_id for c in db.query(UserCard).filter(UserCard.user_id == user.vk_id).all()
    }
    by_level: dict[int, list[PatientAnimal]] = {}
    for p in patients:
        by_level.setdefault(p.level, []).append(p)

    levels = []
    for level in (1, 2, 3):
        items = by_level.get(level, [])
        cards = [
            CollectionCardOut(
                patient_id=p.id, patient_name=p.name, level=p.level,
                card_image_url=p.card_image_url, earned=p.id in earned,
            )
            for p in items
        ]
        levels.append(CollectionLevelOut(
            level=level,
            earned_count=sum(1 for c in cards if c.earned),
            total_count=len(cards),
            cards=cards,
        ))
    return CollectionOut(levels=levels)
