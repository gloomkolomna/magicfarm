from __future__ import annotations
import datetime
import json
import random

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_location
from models import (
    Field, Inventory, PatientAnimal, Remedy, RemedyDeviceCell, RemedyDeviceRemedy,
    User, UserCard, UserIngredient, UserPatientState, UserRemedy, UserRemedyCard,
    UserRemedyDevice,
)
from routes.admin_fields import InfirmaryZoneOut, _get_field_or_404
from routes.ingredients import ApothecaryItemOut, _apothecary_item_out
from services.card_draw import calculate_norm, cards_to_json, draw_cards

router = APIRouter(prefix="/api", tags=["remedy-lab"], dependencies=[Depends(require_location("infirmary"))])


def _check_field_gate(f: Field, user: User) -> None:
    if f.min_level is not None and (user.level or 0) < f.min_level:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Эта локация пока недоступна")


class RecipeItemOut(BaseModel):
    ingredient_id: int | None
    ingredient_name: str | None
    plant_id: int | None
    plant_name: str | None
    qty: int
    have: int = 0


class RemedyCardOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_level: int
    remedy_id: int
    remedy_name: str
    remedy_image_url: str | None
    recipe_items: list[RecipeItemOut]


class DeviceRemedyOut(BaseModel):
    remedy_id: int
    remedy_name: str
    remedy_image_url: str | None


class DeviceStateOut(BaseModel):
    id: int
    build_status: str
    accumulated: int
    required: int
    drawn_cards_json: str | None
    brew_card_id: int | None
    brew_patient_name: str | None
    brew_remedy_name: str | None
    brew_required: int | None
    brew_accumulated: int
    brew_dice: list[int]


class DeviceCellOut(BaseModel):
    id: int
    col: int
    row: int
    install_cards: int
    remedies: list[DeviceRemedyOut]
    device: DeviceStateOut | None


class RemedyStockOut(BaseModel):
    remedy_id: int
    remedy_name: str
    remedy_image_url: str | None
    qty: int


class RemedyLabOut(BaseModel):
    field_id: int
    name: str
    map_url: str | None
    cols: int
    rows: int
    remedy_cards: list[RemedyCardOut]
    apothecary: list[ApothecaryItemOut]
    device_cells: list[DeviceCellOut] = []
    remedies_stock: list[RemedyStockOut] = []
    infirmary_zones: list[InfirmaryZoneOut] = []


def _have_qty(user_id: int, item, db: Session) -> int:
    if item.ingredient_id is not None:
        row = db.query(UserIngredient).filter(
            UserIngredient.user_id == user_id,
            UserIngredient.ingredient_id == item.ingredient_id,
        ).first()
        return row.qty if row else 0
    row = db.query(Inventory).filter(
        Inventory.user_id == user_id, Inventory.plant_id == item.plant_id
    ).first()
    return row.qty if row else 0


def _remedy_card_out(card: UserRemedyCard, user_id: int, db: Session) -> RemedyCardOut:
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
                have=_have_qty(user_id, item, db),
            )
            for item in (remedy.recipe_items if remedy else [])
        ],
    )


def _device_state_out(dev: UserRemedyDevice) -> DeviceStateOut:
    dice = []
    if dev.brew_dice_json:
        try:
            dice = [int(x) for x in json.loads(dev.brew_dice_json)]
        except (ValueError, TypeError):
            dice = []
    return DeviceStateOut(
        id=dev.id,
        build_status=dev.build_status,
        accumulated=dev.accumulated or 0,
        required=dev.required or 0,
        drawn_cards_json=dev.drawn_cards_json,
        brew_card_id=dev.brew_card_id,
        brew_patient_name=(dev.brew_card.patient.name if dev.brew_card and dev.brew_card.patient else None),
        brew_remedy_name=(dev.brew_card.remedy.name if dev.brew_card and dev.brew_card.remedy else None),
        brew_required=dev.brew_required,
        brew_accumulated=dev.brew_accumulated or 0,
        brew_dice=dice,
    )


def _device_cell_out(cell: RemedyDeviceCell, user_id: int, db: Session) -> DeviceCellOut:
    dev = db.query(UserRemedyDevice).filter(
        UserRemedyDevice.user_id == user_id, UserRemedyDevice.cell_id == cell.id
    ).first()
    return DeviceCellOut(
        id=cell.id,
        col=cell.col,
        row=cell.row,
        install_cards=cell.install_cards or 10,
        remedies=[
            DeviceRemedyOut(
                remedy_id=r.remedy_id,
                remedy_name=r.remedy.name if r.remedy else "?",
                remedy_image_url=r.remedy.image_url if r.remedy else None,
            )
            for r in cell.remedies
        ],
        device=(_device_state_out(dev) if dev is not None else None),
    )


@router.get("/remedy-lab/{field_id}", response_model=RemedyLabOut)
def get_remedy_lab(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = _get_field_or_404(field_id, db)
    if f.field_kind != "remedy_lab":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Это не лесная аптека")
    _check_field_gate(f, user)

    states = {
        s.patient_id: s.status for s in db.query(UserPatientState).filter(
            UserPatientState.user_id == user.vk_id
        ).all()
    }
    cards = db.query(UserRemedyCard).filter(
        UserRemedyCard.user_id == user.vk_id
    ).order_by(UserRemedyCard.id.asc()).all()
    active_cards = [c for c in cards if states.get(c.patient_id, "sick") in ("sick", "diagnosed")]

    apo = db.query(UserIngredient).filter(
        UserIngredient.user_id == user.vk_id, UserIngredient.qty > 0
    ).all()
    cells = db.query(RemedyDeviceCell).filter(
        RemedyDeviceCell.field_id == f.id
    ).order_by(RemedyDeviceCell.row.asc(), RemedyDeviceCell.col.asc()).all()
    stock = db.query(UserRemedy).filter(
        UserRemedy.user_id == user.vk_id, UserRemedy.qty > 0
    ).all()

    return RemedyLabOut(
        field_id=f.id, name=f.name, map_url=f.map_url, cols=f.cols, rows=f.rows,
        remedy_cards=[_remedy_card_out(c, user.vk_id, db) for c in active_cards],
        apothecary=[_apothecary_item_out(ui) for ui in apo],
        device_cells=[_device_cell_out(c, user.vk_id, db) for c in cells],
        remedies_stock=[
            RemedyStockOut(
                remedy_id=s.remedy_id,
                remedy_name=s.remedy.name if s.remedy else "?",
                remedy_image_url=s.remedy.image_url if s.remedy else None,
                qty=s.qty or 0,
            )
            for s in stock
        ],
        infirmary_zones=[
            InfirmaryZoneOut(
                id=z.id, field_id=z.field_id, zone_kind=z.zone_kind,
                col1=z.col1, row1=z.row1, col2=z.col2, row2=z.row2,
            )
            for z in f.infirmary_zones
        ],
    )


class InstallResult(BaseModel):
    device: DeviceStateOut
    cards: list[dict]
    required: int


@router.post("/remedy-lab/cells/{cell_id}/install", response_model=InstallResult)
def install_device(
    cell_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cell = db.query(RemedyDeviceCell).filter(RemedyDeviceCell.id == cell_id).first()
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клетка прибора не найдена")

    existing = db.query(UserRemedyDevice).filter(
        UserRemedyDevice.user_id == user.vk_id, UserRemedyDevice.cell_id == cell.id
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Прибор на этой клетке уже устанавливается или установлен",
        )

    cards = draw_cards(db, cell.install_cards or 10, True)
    required = calculate_norm(db, user, cards)

    dev = UserRemedyDevice(
        user_id=user.vk_id, cell_id=cell.id,
        build_status="building", accumulated=0, required=required,
        drawn_cards_json=cards_to_json(cards),
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return InstallResult(device=_device_state_out(dev), cards=cards, required=required)


class BrewRequest(BaseModel):
    cell_id: int


class BrewResult(BaseModel):
    device: DeviceStateOut
    dice: list[int]
    required: int
    remedy_name: str
    patient_name: str


@router.post("/remedy-cards/{card_id}/brew", response_model=BrewResult)
def brew_remedy(
    card_id: int,
    req: BrewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from routes.settings import get_dice_norm

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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Лекарство не найдено")

    cell = db.query(RemedyDeviceCell).filter(RemedyDeviceCell.id == req.cell_id).first()
    if cell is None or cell.field is None or cell.field.field_kind != "remedy_lab":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клетка прибора не найдена")

    allowed = db.query(RemedyDeviceRemedy).filter(
        RemedyDeviceRemedy.cell_id == cell.id, RemedyDeviceRemedy.remedy_id == remedy.id
    ).first()
    if allowed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Это лекарство производится на другом приборе",
        )

    dev = db.query(UserRemedyDevice).filter(
        UserRemedyDevice.user_id == user.vk_id, UserRemedyDevice.cell_id == cell.id
    ).first()
    if dev is None or dev.build_status != "built":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сначала установите прибор на этой клетке",
        )
    if dev.brew_card_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Прибор уже варит лекарство — сначала завершите варку",
        )

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

    dice = [random.randint(1, 6), random.randint(1, 6)]
    required = get_dice_norm(user) * (dice[0] + dice[1])

    dev.brew_card_id = card.id
    dev.brew_required = required
    dev.brew_accumulated = 0
    dev.brew_dice_json = json.dumps(dice)

    db.commit()
    db.refresh(dev)
    return BrewResult(
        device=_device_state_out(dev),
        dice=dice,
        required=required,
        remedy_name=remedy.name,
        patient_name=patient.name,
    )


def complete_brew(user_id: int, device_id: int, db: Session) -> UserRemedy | None:
    dev = db.query(UserRemedyDevice).filter(
        UserRemedyDevice.id == device_id, UserRemedyDevice.user_id == user_id
    ).first()
    if dev is None or dev.brew_card_id is None:
        return None
    card = db.query(UserRemedyCard).filter(UserRemedyCard.id == dev.brew_card_id).first()
    if card is None:
        dev.brew_card_id = None
        dev.brew_required = None
        dev.brew_accumulated = 0
        dev.brew_dice_json = None
        db.commit()
        return None

    stock = db.query(UserRemedy).filter(
        UserRemedy.user_id == user_id, UserRemedy.remedy_id == card.remedy_id
    ).first()
    if stock is None:
        stock = UserRemedy(user_id=user_id, remedy_id=card.remedy_id, qty=0)
        db.add(stock)
    stock.qty = (stock.qty or 0) + 1

    dev.brew_card_id = None
    dev.brew_required = None
    dev.brew_accumulated = 0
    dev.brew_dice_json = None
    db.commit()
    return stock


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
