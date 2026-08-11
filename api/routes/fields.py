import datetime
import random

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_onboarding
from models import Field, FieldCell, FieldPlant, Plot, Production, PRODUCTION_NAMES, ProductionTemplate, Tent, User, MAX_PLOT_QTY, CARD_DRAW_RULES
from routes.admin_fields import (
    CellOut, FieldOut, PlantOut, TentOut,
    _cell_to_out, _field_to_out, _get_field_or_404, _plant_to_out, _tent_to_out,
)
from routes.farm import PlotOut, _plot_to_out
from routes.settings import CRYSTAL_COLORS, crystal_norm, get_production_required
from services.achievements import check_and_award
from services.card_draw import calculate_norm, cards_to_json, draw_cards
from services.pet_bonuses import apply_pet_bonus_harvest

router = APIRouter(prefix="/api/fields", tags=["fields"])


class FieldListItem(FieldOut):
    pass


class CellDetailOut(CellOut):
    plant_name: str | None
    plant_emoji: str | None
    plant_image_young: str | None
    plant_image_grown: str | None
    plot: PlotOut | None
    tent_name: str | None
    tent_image: str | None
    occupant_name: str | None


class FieldDetailPublic(FieldOut):
    cells: list[CellDetailOut]
    plants: list[PlantOut]
    tents: list[TentOut]


@router.get("", response_model=list[FieldListItem])
def list_fields(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Field).order_by(Field.id.asc()).all()
    return [_field_to_out(f) for f in rows]


def _cell_detail(c: FieldCell, db: Session) -> CellDetailOut:
    plot = None
    plant_name = None
    plant_emoji = None
    plant_image_young = None
    plant_image_grown = None
    if c.plant_id is not None and c.plant is not None:
        plant_name = c.plant.name
        plant_emoji = c.plant.emoji
        plant_image_young = c.plant.image_young_url
        plant_image_grown = c.plant.image_grown_url
    if c.kind == "bed" and c.occupant_user_id is not None:
        # Найдём Plot игрока, привязанный к этой клетке.
        p = db.query(Plot).filter(Plot.cell_id == c.id, Plot.user_id == c.occupant_user_id).first()
        if p is not None:
            plot = _plot_to_out(p)
    tent_name = None
    tent_image = None
    if c.tent_id is not None and c.kind == "tent":
        from models import Tent
        t = db.query(Tent).filter(Tent.id == c.tent_id).first()
        if t is not None:
            tent_name = t.name
            tent_image = t.image_url
    occupant_name = None
    return CellDetailOut(
        id=c.id, col=c.col, row=c.row, kind=c.kind,
        plant_id=c.plant_id, occupant_user_id=c.occupant_user_id, tent_id=c.tent_id,
        plant_name=plant_name, plant_emoji=plant_emoji,
        plant_image_young=plant_image_young, plant_image_grown=plant_image_grown,
        plot=plot, tent_name=tent_name, tent_image=tent_image, occupant_name=occupant_name,
    )


@router.get("/{field_id}", response_model=FieldDetailPublic)
def get_field(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = _get_field_or_404(field_id, db)
    cells = [_cell_detail(c, db) for c in f.cells]
    plants = [_plant_to_out(fp.plant) for fp in f.plants]
    tents = [_tent_to_out(t) for t in f.tents]
    return FieldDetailPublic(
        id=f.id, code=f.code, name=f.name, map_url=f.map_url,
        cols=f.cols, rows=f.rows, grid_color=f.grid_color,
        plant_category=f.plant_category, min_level=f.min_level,
        field_kind=f.field_kind,
        created_at=f.created_at,
        cells=cells, plants=plants, tents=tents,
    )


class PlantCellRequest(BaseModel):
    plant_id: int
    qty: int = 1


@router.post("/{field_id}/cells/{col}/{row}/plant", response_model=CellDetailOut, status_code=status.HTTP_201_CREATED)
def plant_on_cell(
    field_id: int,
    col: int,
    row: int,
    req: PlantCellRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_onboarding),
):
    f = _get_field_or_404(field_id, db)
    cell = db.query(FieldCell).filter(
        FieldCell.field_id == f.id, FieldCell.col == col, FieldCell.row == row
    ).first()
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клетка не найдена")
    if cell.kind != "bed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="На этой клетке нельзя сажать",
        )
    if cell.occupant_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Клетка уже занята",
        )

    allowed = {fp.plant_id for fp in f.plants}
    if req.plant_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Это растение недоступно в данной локации",
        )

    if f.min_level is not None and (user.level or 0) < f.min_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Эта локация пока недоступна",
        )

    from models import Plant as PlantModel
    plant_obj = db.query(PlantModel).filter(PlantModel.id == req.plant_id).first()
    if f.plant_category is not None and plant_obj.category != f.plant_category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"В этой локации можно сажать только растения категории '{f.plant_category}'",
        )

    if plant_obj.category == "garden_beds" and plant_obj.level > (user.unlocked_plot_level or 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Грядки {plant_obj.level} уровня пока недоступны. Повысьте уровень.",
        )
    if plant_obj.category == "orchard" and plant_obj.level > (user.unlocked_garden_level or 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Сады {plant_obj.level} уровня пока недоступны. Повысьте уровень.",
        )

    if req.qty < 1 or req.qty > MAX_PLOT_QTY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Количество растений должно быть от 1 до {MAX_PLOT_QTY}",
        )

    existing = db.query(Plot).filter(
        Plot.user_id == user.vk_id, Plot.plant_id == req.plant_id, Plot.cell_id.isnot(None)
    ).first()
    if existing is not None and existing.cell_id != cell.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Это растение уже посажено на другой грядке",
        )

    level_key = f"plant_{plant_obj.level}"
    num_cards, allow_treasure = CARD_DRAW_RULES.get(level_key, (1, False))
    cards = draw_cards(db, num_cards, allow_treasure)
    required = calculate_norm(db, user, cards) * req.qty

    plot = Plot(
        user_id=user.vk_id, plant_id=req.plant_id, qty=req.qty,
        status="planted", accumulated=0, required=required,
        drawn_cards_json=cards_to_json(cards), cell_id=cell.id,
    )
    db.add(plot)
    db.flush()

    cell.plant_id = req.plant_id
    cell.occupant_user_id = user.vk_id

    db.commit()
    db.refresh(cell)

    check_and_award(user.vk_id, "first_plant", db)

    from models import OrderReq as OrderModel, OrderTemplate
    templates = db.query(OrderTemplate).filter(
        OrderTemplate.source_kind == "plant", OrderTemplate.source_id == req.plant_id
    ).all()
    for t in templates:
        existing = db.query(OrderModel).filter(
            OrderModel.user_id == user.vk_id,
            OrderModel.product_id == t.product_id,
            OrderModel.status == "open",
        ).first()
        if existing is None:
            db.add(OrderModel(
                user_id=user.vk_id, product_id=t.product_id, qty=t.qty,
                reward_coins=t.reward_coins, customer=t.customer,
                status="open", name=t.name, image_url=t.image_url,
            ))
    db.commit()

    return _cell_detail(cell, db)


@router.post("/{field_id}/cells/{col}/{row}/harvest", response_model=CellDetailOut)
def harvest_cell(
    field_id: int,
    col: int,
    row: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = _get_field_or_404(field_id, db)
    cell = db.query(FieldCell).filter(
        FieldCell.field_id == f.id, FieldCell.col == col, FieldCell.row == row
    ).first()
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клетка не найдена")
    if cell.occupant_user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="На клетке нет растения")
    if cell.occupant_user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша грядка")

    plot = db.query(Plot).filter(Plot.cell_id == cell.id, Plot.user_id == user.vk_id).first()
    if plot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="На клетке нет растения")
    if plot.status != "grown":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Растение ещё не выросло",
        )

    plot.status = "planted"
    plot.accumulated = 0
    plot.norm_revealed = False
    plot.completed_at = plot.completed_at or datetime.datetime.utcnow()

    from models import Inventory
    inv = db.query(Inventory).filter(
        Inventory.user_id == user.vk_id, Inventory.plant_id == plot.plant_id
    ).first()
    if inv is None:
        inv = Inventory(user_id=user.vk_id, plant_id=plot.plant_id, qty=0)
        db.add(inv)
    inv.qty = (inv.qty or 0) + plot.qty

    plant_obj = plot.plant
    bonus = apply_pet_bonus_harvest(user.vk_id, plant_obj.category, plot.qty, db)
    if bonus > 0:
        inv.qty = (inv.qty or 0) + bonus

    num_cards, allow_treasure = CARD_DRAW_RULES.get(f"plant_{plant_obj.level}", (1, False))
    cards = draw_cards(db, num_cards, allow_treasure)
    plot.required = calculate_norm(db, user, cards) * plot.qty
    plot.drawn_cards_json = cards_to_json(cards)
    plot.crystal_color = None
    plot.crystal_count = None

    db.commit()
    db.refresh(cell)

    check_and_award(user.vk_id, "plots_count", db)

    return _cell_detail(cell, db)


# ===== Строительство шатров =====

MIN_BUILD_INVEST = 1


def _get_tent_on_field(tent_id: int, field_id: int, db: Session) -> Tent:
    t = db.query(Tent).filter(Tent.id == tent_id, Tent.field_id == field_id).first()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шатёр не найден")
    return t


@router.post("/{field_id}/tents/{tent_id}/start-build", response_model=TentOut)
def start_tent_build(
    field_id: int,
    tent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_onboarding),
):
    _get_field_or_404(field_id, db)
    t = _get_tent_on_field(tent_id, field_id, db)
    if t.build_status != "slot":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот шатёр уже строят или построен",
        )

    kind_key = f"tent_{t.kind}"
    tmpl = db.query(ProductionTemplate).filter(ProductionTemplate.code == t.kind).first()
    num_cards = tmpl.cards_to_draw if tmpl else 3
    cards = draw_cards(db, num_cards, True)
    required = calculate_norm(db, user, cards)

    t.builder_user_id = user.vk_id
    t.build_status = "planted"
    t.required = required
    t.accumulated = 0
    t.drawn_cards_json = cards_to_json(cards)
    t.crystal_color = None
    t.crystal_count = None

    db.commit()
    db.refresh(t)
    return _tent_to_out(t)


class BuildInvestRequest(BaseModel):
    amount: int


@router.post("/{field_id}/tents/{tent_id}/build-invest", response_model=TentOut)
def invest_tent_build(
    field_id: int,
    tent_id: int,
    req: BuildInvestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Вложить крестики с баланса в постройку шатра; при накоплении нормы — построить."""
    _get_field_or_404(field_id, db)
    t = _get_tent_on_field(tent_id, field_id, db)
    if t.build_status != "planted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Шатёр не в стадии постройки",
        )
    if t.builder_user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша стройка")
    if req.amount < MIN_BUILD_INVEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Минимум {MIN_BUILD_INVEST} крестиков",
        )

    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    if (u.crosses_balance or 0) < req.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно крестиков на балансе",
        )

    u.crosses_balance = (u.crosses_balance or 0) - req.amount
    t.accumulated = (t.accumulated or 0) + req.amount

    if t.accumulated >= t.required:
        t.build_status = "built"
        pr = Production(
            user_id=user.vk_id, kind=t.kind, name=PRODUCTION_NAMES.get(t.kind, t.kind),
            status="installed", accumulated=0, required=get_production_required(db),
            tent_id=t.id,
        )
        db.add(pr)

    db.commit()
    db.refresh(t)

    check_and_award(user.vk_id, "tents_count", db)

    return _tent_to_out(t)
