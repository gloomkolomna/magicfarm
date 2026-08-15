from __future__ import annotations
import json
import random

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_onboarding
from models import (
    HouseBuild, Tent, User,
    HOUSE_CARDS_TO_DRAW, HOUSE_MATERIALS, WITCH_HOUSE_KIND,
)
from routes.admin_fields import _get_field_or_404
from routes.settings import get_dice_norm
from services.achievements import check_and_award
from services.card_draw import calculate_norm, cards_to_json, draw_cards

router = APIRouter(prefix="/api/fields", tags=["house"])

MAX_DIE = 6


def _roll_die(exclude: int | None = None) -> int:
    values = [v for v in range(1, MAX_DIE + 1) if v != exclude]
    return random.choice(values)


class HouseStateOut(BaseModel):
    id: int | None
    tent_id: int
    phase: str
    current_material: str | None
    current_die: int | None
    current_required: int | None
    collected: list[str]
    cards_json: str | None
    required: int


def _get_house_tent_or_404(field_id: int, tent_id: int, db: Session) -> Tent:
    _get_field_or_404(field_id, db)
    t = db.query(Tent).filter(Tent.id == tent_id, Tent.field_id == field_id).first()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Дом не найден")
    if t.kind != WITCH_HOUSE_KIND:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Это не дом ведьмы")
    return t


def _collected_list(hb: HouseBuild) -> list[str]:
    try:
        raw = json.loads(hb.collected_json or "[]")
    except (TypeError, ValueError):
        return []
    return [m for m in raw if m in HOUSE_MATERIALS]


def _state_out(hb: HouseBuild | None, tent_id: int) -> HouseStateOut:
    if hb is None:
        return HouseStateOut(
            id=None, tent_id=tent_id, phase="materials",
            current_material=None, current_die=None, current_required=None,
            collected=[], cards_json=None, required=0,
        )
    return HouseStateOut(
        id=hb.id, tent_id=hb.tent_id, phase=hb.phase,
        current_material=hb.current_material, current_die=hb.current_die,
        current_required=hb.current_required,
        collected=_collected_list(hb), cards_json=hb.cards_json,
        required=hb.required or 0,
    )


def _get_house_build(tent_id: int, user_id: int, db: Session) -> HouseBuild | None:
    return db.query(HouseBuild).filter(
        HouseBuild.user_id == user_id, HouseBuild.tent_id == tent_id
    ).first()


@router.get("/{field_id}/house/{tent_id}", response_model=HouseStateOut)
def house_state(
    field_id: int,
    tent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = _get_house_tent_or_404(field_id, tent_id, db)
    hb = _get_house_build(t.id, user.vk_id, db)
    return _state_out(hb, t.id)


@router.post("/{field_id}/house/{tent_id}/request-material", response_model=HouseStateOut)
def request_material(
    field_id: int,
    tent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_onboarding),
):
    """Бросок кубика: случайный материал из несобранных + норма (база × грань)."""
    t = _get_house_tent_or_404(field_id, tent_id, db)
    hb = _get_house_build(t.id, user.vk_id, db)
    if hb is None:
        hb = HouseBuild(user_id=user.vk_id, tent_id=t.id)
        db.add(hb)
        db.flush()
    if hb.phase == "built":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Дом уже построен")
    if hb.current_material is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала вышейте норму текущего материала",
        )
    collected = _collected_list(hb)
    if len(collected) >= len(HOUSE_MATERIALS):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Все материалы собраны — постройте дом",
        )

    remaining = [m for m in HOUSE_MATERIALS if m not in collected]
    hb.current_material = random.choice(remaining)
    hb.current_die = _roll_die(hb.last_die)
    hb.last_die = hb.current_die
    hb.current_required = get_dice_norm(user) * hb.current_die

    db.commit()
    db.refresh(hb)
    return _state_out(hb, t.id)


@router.post("/{field_id}/house/{tent_id}/build", response_model=HouseStateOut)
def build_house(
    field_id: int,
    tent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_onboarding),
):
    """Назначает норму на дом: 5 случайных карт кристалликов."""
    t = _get_house_tent_or_404(field_id, tent_id, db)
    hb = _get_house_build(t.id, user.vk_id, db)
    if hb is None or hb.phase != "materials":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Дом уже построен")
    if hb.required > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Норма на дом уже назначена",
        )
    if hb.current_material is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала вышейте норму текущего материала",
        )
    if len(_collected_list(hb)) < len(HOUSE_MATERIALS):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Соберите все стройматериалы",
        )

    cards = draw_cards(db, HOUSE_CARDS_TO_DRAW, True)
    hb.cards_json = cards_to_json(cards)
    hb.required = calculate_norm(db, user, cards)

    db.commit()
    db.refresh(hb)
    return _state_out(hb, t.id)


def complete_material(user_id: int, house_build_id: int, db: Session) -> None:
    hb = db.query(HouseBuild).filter(
        HouseBuild.id == house_build_id, HouseBuild.user_id == user_id
    ).first()
    if hb is None or hb.phase != "materials" or hb.current_material is None:
        return
    collected = _collected_list(hb)
    if hb.current_material not in collected:
        collected.append(hb.current_material)
    hb.collected_json = json.dumps(collected, ensure_ascii=False)
    hb.current_material = None
    hb.current_die = None
    hb.current_required = None
    db.commit()


def complete_build(user_id: int, house_build_id: int, db: Session) -> None:
    hb = db.query(HouseBuild).filter(
        HouseBuild.id == house_build_id, HouseBuild.user_id == user_id
    ).first()
    if hb is None or hb.phase != "materials" or (hb.required or 0) <= 0:
        return
    hb.phase = "built"
    db.commit()
    _grant_gifts(user_id, db)
    check_and_award(user_id, "house_built", db)


def _grant_gifts(user_id: int, db: Session) -> None:
    from models import Inventory, Plant, Product, Recipe

    plants = db.query(Plant).filter(Plant.level == 1).all()
    if plants:
        plant = random.choice(plants)
        inv = db.query(Inventory).filter(
            Inventory.user_id == user_id, Inventory.plant_id == plant.id
        ).first()
        if inv is None:
            inv = Inventory(user_id=user_id, plant_id=plant.id, qty=0)
            db.add(inv)
        inv.qty = (inv.qty or 0) + 5

    level1_products = [
        r.product_id for r in
        db.query(Recipe).filter(Recipe.level == 1, Recipe.product_id.isnot(None)).all()
    ]
    if level1_products:
        products = db.query(Product).filter(Product.id.in_(level1_products)).all()
    else:
        products = db.query(Product).all()
    if products:
        product = random.choice(products)
        inv = db.query(Inventory).filter(
            Inventory.user_id == user_id, Inventory.product_id == product.id
        ).first()
        if inv is None:
            inv = Inventory(user_id=user_id, product_id=product.id, qty=0)
            db.add(inv)
        inv.qty = (inv.qty or 0) + 5

    db.commit()
