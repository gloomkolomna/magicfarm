from __future__ import annotations
import datetime
import random

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_onboarding
from models import BarnyardSlot, Field, FieldCell, FieldPlant, PlantBed, Plot, Production, PRODUCTION_NAMES, ProductionTemplate, Tent, TentBuild, User, UserPet, MAX_PLOT_QTY, CARD_DRAW_RULES
from routes.admin_fields import (
    CellOut, FieldOut, PlantOut, TentOut,
    _field_to_out, _get_field_or_404, _plant_to_out,
)
from routes.farm import PlotOut, _plot_to_out
from routes.settings import CRYSTAL_COLORS, crystal_norm, get_production_required
from services.achievements import check_and_award
from services.card_draw import calculate_norm, cards_to_json, draw_cards
from services.pet_bonuses import apply_pet_bonus_harvest

router = APIRouter(prefix="/api/fields", tags=["fields"])


class FieldListItem(FieldOut):
    pass


class BarnyardCellOut(BaseModel):
    slot_id: int
    animal_id: int | None
    animal_name: str | None
    animal_emoji: str | None
    status: str
    accumulated: int
    required: int
    last_die: int | None
    image_pen_url: str | None = None
    image_harvested_url: str | None = None


class PetCellOut(BaseModel):
    pet_id: int
    pet_name: str
    pet_emoji: str | None
    bonus_description: str | None


class CellDetailOut(CellOut):
    plant_name: str | None
    plant_emoji: str | None
    plant_image_young: str | None
    plant_image_grown: str | None
    plant_image_harvested: str | None = None
    plot: PlotOut | None
    tent_name: str | None
    tent_image: str | None
    occupant_name: str | None
    barnyard: BarnyardCellOut | None = None
    pet: PetCellOut | None = None


class PlantBedDetailOut(BaseModel):
    id: int
    field_id: int
    col1: int
    row1: int
    col2: int
    row2: int
    plant_category: str | None
    plant_id: int | None
    occupant_user_id: int | None
    plant_name: str | None
    plant_emoji: str | None
    plant_image_young: str | None
    plant_image_grown: str | None
    plant_image_harvested: str | None = None
    plot: PlotOut | None


class FieldDetailPublic(FieldOut):
    cells: list[CellDetailOut]
    plants: list[PlantOut]
    tents: list[TentOut]
    plant_beds: list[PlantBedDetailOut]


@router.get("", response_model=list[FieldListItem])
def list_fields(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Field).order_by(Field.id.asc()).all()
    return [_field_to_out(f) for f in rows]


def _cell_detail(c: FieldCell, db: Session, user: User, plot: Plot | None = None) -> CellDetailOut:
    plant_name = None
    plant_emoji = None
    plant_image_young = None
    plant_image_grown = None
    plant_image_harvested = None
    occupant_user_id = None
    plant_id = None
    plot_out = None
    if c.kind == "bed":
        if plot is None:
            plot = db.query(Plot).filter(Plot.cell_id == c.id, Plot.user_id == user.vk_id).first()
        if plot is not None:
            occupant_user_id = user.vk_id
            plant_id = plot.plant_id
            plant = plot.plant
            if plant is not None:
                plant_name = plant.name
                plant_emoji = plant.emoji
                plant_image_young = plant.image_young_url
                plant_image_grown = plant.image_grown_url
                plant_image_harvested = plant.image_harvested_url
            plot_out = _plot_to_out(plot)
    tent_name = None
    tent_image = None
    if c.tent_id is not None and c.kind == "tent":
        t = db.query(Tent).filter(Tent.id == c.tent_id).first()
        if t is not None:
            tent_name = t.name
            tent_image = t.image_url
    barnyard = None
    if c.kind == "barnyard":
        slot = db.query(BarnyardSlot).filter(
            BarnyardSlot.user_id == user.vk_id, BarnyardSlot.cell_id == c.id
        ).first()
        if slot is not None:
            barnyard = BarnyardCellOut(
                slot_id=slot.id, animal_id=slot.animal_id,
                animal_name=slot.animal.name if slot.animal else None,
                animal_emoji=slot.animal.emoji if slot.animal else None,
                status=slot.status, accumulated=slot.accumulated,
                required=slot.required, last_die=slot.last_die,
                image_pen_url=slot.animal.image_pen_url if slot.animal else None,
                image_harvested_url=slot.animal.image_harvested_url if slot.animal else None,
            )
    pet = None
    if c.kind == "pet":
        up = db.query(UserPet).filter(
            UserPet.user_id == user.vk_id, UserPet.cell_id == c.id
        ).first()
        if up is not None and up.pet is not None:
            pet = PetCellOut(
                pet_id=up.pet_id, pet_name=up.pet.name,
                pet_emoji=up.pet.emoji, bonus_description=up.pet.bonus_description,
            )
    occupant_name = None
    return CellDetailOut(
        id=c.id, col=c.col, row=c.row, kind=c.kind,
        plant_id=plant_id, occupant_user_id=occupant_user_id, tent_id=c.tent_id,
        plant_name=plant_name, plant_emoji=plant_emoji,
        plant_image_young=plant_image_young, plant_image_grown=plant_image_grown,
        plant_image_harvested=plant_image_harvested,
        plot=plot_out, tent_name=tent_name, tent_image=tent_image, occupant_name=occupant_name,
        barnyard=barnyard, pet=pet,
    )


def _plant_bed_detail(pb: PlantBed, db: Session, user: User, plot: Plot | None = None) -> PlantBedDetailOut:
    plant_name = None
    plant_emoji = None
    plant_image_young = None
    plant_image_grown = None
    plant_image_harvested = None
    occupant_user_id = None
    plant_id = None
    plot_out = None
    if plot is None:
        plot = db.query(Plot).filter(
            Plot.plant_bed_id == pb.id, Plot.user_id == user.vk_id
        ).first()
    if plot is not None:
        occupant_user_id = user.vk_id
        plant_id = plot.plant_id
        plant = plot.plant
        if plant is not None:
            plant_name = plant.name
            plant_emoji = plant.emoji
            plant_image_young = plant.image_young_url
            plant_image_grown = plant.image_grown_url
            plant_image_harvested = plant.image_harvested_url
        plot_out = _plot_to_out(plot)
    return PlantBedDetailOut(
        id=pb.id, field_id=pb.field_id, col1=pb.col1, row1=pb.row1,
        col2=pb.col2, row2=pb.row2, plant_category=pb.plant_category,
        plant_id=plant_id, occupant_user_id=occupant_user_id,
        plant_name=plant_name, plant_emoji=plant_emoji,
        plant_image_young=plant_image_young, plant_image_grown=plant_image_grown,
        plant_image_harvested=plant_image_harvested,
        plot=plot_out,
    )


def _tent_to_out_for_user(t: Tent, tb: TentBuild | None) -> TentOut:
    if tb is not None:
        return TentOut(
            id=t.id, name=t.name, image_url=t.image_url, kind=t.kind,
            col1=t.col1, row1=t.row1, col2=t.col2, row2=t.row2,
            builder_user_id=tb.user_id, build_status=tb.build_status,
            accumulated=tb.accumulated or 0, required=tb.required or 0,
            crystal_color=tb.crystal_color, crystal_count=tb.crystal_count,
            drawn_cards_json=tb.drawn_cards_json,
            norm_revealed=tb.norm_revealed,
        )
    return TentOut(
        id=t.id, name=t.name, image_url=t.image_url, kind=t.kind,
        col1=t.col1, row1=t.row1, col2=t.col2, row2=t.row2,
        builder_user_id=None, build_status="slot",
        accumulated=0, required=t.required or 0,
        crystal_color=None, crystal_count=None, drawn_cards_json=None,
    )


@router.get("/{field_id}", response_model=FieldDetailPublic)
def get_field(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = _get_field_or_404(field_id, db)

    cell_ids = [c.id for c in f.cells if c.kind == "bed"]
    cell_plots: dict[int, Plot] = {}
    if cell_ids:
        cell_plots = {
            p.cell_id: p
            for p in db.query(Plot).filter(
                Plot.user_id == user.vk_id, Plot.cell_id.in_(cell_ids)
            ).all()
        }
    bed_plot_ids = [pb.id for pb in f.plant_beds]
    bed_plots: dict[int, Plot] = {}
    if bed_plot_ids:
        bed_plots = {
            p.plant_bed_id: p
            for p in db.query(Plot).filter(
                Plot.user_id == user.vk_id, Plot.plant_bed_id.in_(bed_plot_ids)
            ).all()
        }
    tent_ids = [t.id for t in f.tents]
    builds: dict[int, TentBuild] = {}
    if tent_ids:
        builds = {
            tb.tent_id: tb
            for tb in db.query(TentBuild).filter(
                TentBuild.user_id == user.vk_id, TentBuild.tent_id.in_(tent_ids)
            ).all()
        }

    cells = [_cell_detail(c, db, user, cell_plots.get(c.id)) for c in f.cells]
    plants = [_plant_to_out(fp.plant) for fp in f.plants]
    tents = [_tent_to_out_for_user(t, builds.get(t.id)) for t in f.tents]
    plant_beds = [_plant_bed_detail(pb, db, user, bed_plots.get(pb.id)) for pb in f.plant_beds]
    return FieldDetailPublic(
        id=f.id, code=f.code, name=f.name, map_url=f.map_url,
        cols=f.cols, rows=f.rows, grid_color=f.grid_color,
        plant_category=f.plant_category, min_level=f.min_level,
        field_kind=f.field_kind,
        created_at=f.created_at,
        cells=cells, plants=plants, tents=tents, plant_beds=plant_beds,
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
    if f.plant_category == "orchard":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В саду деревья сажают в слоты, а не на отдельные клетки",
        )
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
    own_on_cell = db.query(Plot).filter(
        Plot.user_id == user.vk_id, Plot.cell_id == cell.id
    ).first()
    if own_on_cell is not None:
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

    existing = db.query(Plot).join(
        FieldCell, Plot.cell_id == FieldCell.id
    ).filter(
        Plot.user_id == user.vk_id,
        Plot.plant_id == req.plant_id,
        FieldCell.field_id == f.id,
        FieldCell.kind == "bed",
        Plot.cell_id != cell.id,
    ).first()
    if existing is not None:
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

    return _cell_detail(cell, db, user, plot)


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

    return _cell_detail(cell, db, user, plot)


# ===== Садовые слоты-деревья =====

def _get_bed_on_field(pb_id: int, field_id: int, db: Session) -> PlantBed:
    pb = db.query(PlantBed).filter(PlantBed.id == pb_id, PlantBed.field_id == field_id).first()
    if pb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Слот дерева не найден")
    return pb


class PlantBedPlantRequest(BaseModel):
    plant_id: int
    qty: int = 1


@router.post("/{field_id}/plant-beds/{pb_id}/plant", response_model=PlantBedDetailOut, status_code=status.HTTP_201_CREATED)
def plant_on_bed(
    field_id: int,
    pb_id: int,
    req: PlantBedPlantRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_onboarding),
):
    f = _get_field_or_404(field_id, db)
    pb = _get_bed_on_field(pb_id, f.id, db)
    if f.plant_category != "orchard":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Слоты деревьев доступны только в саду",
        )
    own_in_bed = db.query(Plot).filter(
        Plot.user_id == user.vk_id, Plot.plant_bed_id == pb.id
    ).first()
    if own_in_bed is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот слот уже занят деревом",
        )

    if f.min_level is not None and (user.level or 0) < f.min_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Эта локация пока недоступна",
        )

    allowed = {fp.plant_id for fp in f.plants}
    if req.plant_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Это растение недоступно в данной локации",
        )

    from models import Plant as PlantModel
    plant_obj = db.query(PlantModel).filter(PlantModel.id == req.plant_id).first()
    if plant_obj is None or plant_obj.category != "orchard":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В слот сада можно сажать только садовые растения",
        )

    if plant_obj.level > (user.unlocked_garden_level or 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Сады {plant_obj.level} уровня пока недоступны. Повысьте уровень.",
        )

    if req.qty < 1 or req.qty > MAX_PLOT_QTY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Количество растений должно быть от 1 до {MAX_PLOT_QTY}",
        )

    existing = db.query(Plot).join(
        PlantBed, Plot.plant_bed_id == PlantBed.id
    ).filter(
        Plot.user_id == user.vk_id,
        Plot.plant_id == req.plant_id,
        PlantBed.field_id == f.id,
        Plot.plant_bed_id != pb.id,
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Это растение уже посажено в другом месте",
        )

    level_key = f"plant_{plant_obj.level}"
    num_cards, allow_treasure = CARD_DRAW_RULES.get(level_key, (1, False))
    cards = draw_cards(db, num_cards, allow_treasure)
    required = calculate_norm(db, user, cards) * req.qty

    plot = Plot(
        user_id=user.vk_id, plant_id=req.plant_id, qty=req.qty,
        status="planted", accumulated=0, required=required,
        drawn_cards_json=cards_to_json(cards), plant_bed_id=pb.id,
    )
    db.add(plot)
    db.flush()

    db.commit()
    db.refresh(pb)

    check_and_award(user.vk_id, "first_plant", db)

    from models import OrderReq as OrderModel, OrderTemplate
    templates = db.query(OrderTemplate).filter(
        OrderTemplate.source_kind == "plant", OrderTemplate.source_id == req.plant_id
    ).all()
    for t in templates:
        existing_order = db.query(OrderModel).filter(
            OrderModel.user_id == user.vk_id,
            OrderModel.product_id == t.product_id,
            OrderModel.status == "open",
        ).first()
        if existing_order is None:
            db.add(OrderModel(
                user_id=user.vk_id, product_id=t.product_id, qty=t.qty,
                reward_coins=t.reward_coins, customer=t.customer,
                status="open", name=t.name, image_url=t.image_url,
            ))
    db.commit()

    return _plant_bed_detail(pb, db, user, plot)


@router.post("/{field_id}/plant-beds/{pb_id}/harvest", response_model=PlantBedDetailOut)
def harvest_bed(
    field_id: int,
    pb_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = _get_field_or_404(field_id, db)
    pb = _get_bed_on_field(pb_id, f.id, db)

    plot = db.query(Plot).filter(
        Plot.plant_bed_id == pb.id, Plot.user_id == user.vk_id
    ).first()
    if plot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="В слоте нет дерева")
    if plot.status != "grown":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дерево ещё не выросло",
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
    db.refresh(pb)

    check_and_award(user.vk_id, "plots_count", db)

    return _plant_bed_detail(pb, db, user, plot)


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

    tb = db.query(TentBuild).filter(
        TentBuild.user_id == user.vk_id, TentBuild.tent_id == t.id
    ).first()
    if tb is not None and tb.build_status in ("planted", "built"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот шатёр уже строят или построен",
        )

    tmpl = db.query(ProductionTemplate).filter(ProductionTemplate.code == t.kind).first()
    num_cards = tmpl.cards_to_draw if tmpl else 3
    cards = draw_cards(db, num_cards, True)
    required = calculate_norm(db, user, cards)

    if tb is None:
        tb = TentBuild(user_id=user.vk_id, tent_id=t.id)
        db.add(tb)
    tb.build_status = "planted"
    tb.required = required
    tb.accumulated = 0
    tb.drawn_cards_json = cards_to_json(cards)
    tb.crystal_color = None
    tb.crystal_count = None

    db.commit()
    db.refresh(tb)
    return _tent_to_out_for_user(t, tb)


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
    tb = db.query(TentBuild).filter(
        TentBuild.user_id == user.vk_id, TentBuild.tent_id == t.id
    ).first()
    if tb is None or tb.build_status != "planted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Шатёр не в стадии постройки",
        )
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
    tb.accumulated = (tb.accumulated or 0) + req.amount

    if tb.accumulated >= tb.required:
        tb.build_status = "built"
        pr = Production(
            user_id=user.vk_id, kind=t.kind, name=PRODUCTION_NAMES.get(t.kind, t.kind),
            status="installed", accumulated=0, required=get_production_required(db),
            tent_id=t.id,
        )
        db.add(pr)

    db.commit()
    db.refresh(tb)

    check_and_award(user.vk_id, "tents_count", db)

    return _tent_to_out_for_user(t, tb)


@router.post("/{field_id}/tents/{tent_id}/reveal-norm", response_model=TentOut)
def reveal_tent_norm(
    field_id: int,
    tent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Показывает вытянутые карты и норму вышивки для постройки шатра."""
    _get_field_or_404(field_id, db)
    t = _get_tent_on_field(tent_id, field_id, db)
    tb = db.query(TentBuild).filter(
        TentBuild.user_id == user.vk_id, TentBuild.tent_id == t.id
    ).first()
    if tb is None or tb.build_status != "planted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Шатёр не в стадии постройки",
        )
    tb.norm_revealed = True
    db.commit()
    db.refresh(tb)
    return _tent_to_out_for_user(t, tb)
