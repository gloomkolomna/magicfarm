from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from db import get_db
from deps import require_role
from models import Field, FieldCell, FieldPlant, Inventory, Plot, Production, StitchReport, Tent, TentBuild, User
from services.vk_names import resolve_vk_names

router = APIRouter(prefix="/api/admin/players", tags=["admin-players"])


class PlayerOut(BaseModel):
    vk_id: int
    first_name: str
    last_name: str
    role: str
    crosses_balance: int
    crosses_total: int
    coins: int
    round: int
    reports_total: int
    created_at: str | None


@router.get("", response_model=list[PlayerOut])
def list_players(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    users = db.query(User).order_by(User.created_at.desc()).limit(200).all()
    vk_ids = [u.vk_id for u in users]
    names = resolve_vk_names(vk_ids)

    report_counts = dict(
        db.query(StitchReport.user_id, func.count(StitchReport.id))
        .filter(StitchReport.user_id.in_(vk_ids))
        .group_by(StitchReport.user_id)
        .all()
    )

    result = []
    for u in users:
        nm = names.get(u.vk_id, {})
        result.append(PlayerOut(
            vk_id=u.vk_id,
            first_name=nm.get("first_name", ""),
            last_name=nm.get("last_name", ""),
            role=u.role,
            crosses_balance=u.crosses_balance or 0,
            crosses_total=u.crosses_total or 0,
            coins=u.coins or 0,
            round=u.round or 1,
            reports_total=report_counts.get(u.vk_id, 0),
            created_at=u.created_at.isoformat() if u.created_at else None,
        ))
    return result


class PlayerReportOut(BaseModel):
    id: int
    user_id: int
    amount: int
    photo_after_url: str | None
    photo_before_url: str | None
    note: str | None
    status: str
    context_type: str | None
    context_id: int | None
    reviewer_id: int | None
    reviewed_at: str | None
    created_at: str | None


class PlayerPlotOut(BaseModel):
    id: int
    plant_id: int
    plant_name: str
    plant_emoji: str | None
    qty: int
    status: str
    accumulated: int
    required: int
    crystal_color: str | None
    crystal_count: int | None
    cell_id: int | None
    created_at: str | None
    completed_at: str | None


class PlayerProductionOut(BaseModel):
    id: int
    kind: str
    name: str
    status: str
    accumulated: int
    required: int
    created_at: str | None


class PlayerInventoryOut(BaseModel):
    product_id: int
    product_code: str
    product_name: str
    product_emoji: str | None
    qty: int


class PlayerDetailOut(BaseModel):
    vk_id: int
    first_name: str
    last_name: str
    role: str
    crosses_balance: int
    crosses_total: int
    coins: int
    round: int
    reports_total: int
    created_at: str | None
    plots: list[PlayerPlotOut]
    productions: list[PlayerProductionOut]
    inventory: list[PlayerInventoryOut]


@router.get("/{vk_id}", response_model=PlayerDetailOut)
def get_player_detail(
    vk_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    player = db.query(User).filter(User.vk_id == vk_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")

    names = resolve_vk_names([vk_id])
    nm = names.get(vk_id, {})

    reports_total = db.query(func.count(StitchReport.id)).filter(StitchReport.user_id == vk_id).scalar() or 0

    plots = db.query(Plot).filter(Plot.user_id == vk_id).order_by(Plot.created_at.desc()).all()
    productions = db.query(Production).filter(Production.user_id == vk_id).order_by(Production.created_at.desc()).all()
    inventory = db.query(Inventory).filter(Inventory.user_id == vk_id, Inventory.product_id.isnot(None)).all()

    return PlayerDetailOut(
        vk_id=player.vk_id,
        first_name=nm.get("first_name", ""),
        last_name=nm.get("last_name", ""),
        role=player.role,
        crosses_balance=player.crosses_balance or 0,
        crosses_total=player.crosses_total or 0,
        coins=player.coins or 0,
        round=player.round or 1,
        reports_total=reports_total,
        created_at=player.created_at.isoformat() if player.created_at else None,
        plots=[
            PlayerPlotOut(
                id=p.id, plant_id=p.plant_id, plant_name=p.plant.name,
                plant_emoji=p.plant.emoji, qty=p.qty or 0, status=p.status,
                accumulated=p.accumulated or 0, required=p.required or 0,
                crystal_color=p.crystal_color, crystal_count=p.crystal_count,
                cell_id=p.cell_id,
                created_at=p.created_at.isoformat() if p.created_at else None,
                completed_at=p.completed_at.isoformat() if p.completed_at else None,
            ) for p in plots
        ],
        productions=[
            PlayerProductionOut(
                id=pr.id, kind=pr.kind, name=pr.name, status=pr.status,
                accumulated=pr.accumulated or 0, required=pr.required or 0,
                created_at=pr.created_at.isoformat() if pr.created_at else None,
            ) for pr in productions
        ],
        inventory=[
            PlayerInventoryOut(
                product_id=inv.product_id, product_code=inv.product.code,
                product_name=inv.product.name, product_emoji=inv.product.emoji,
                qty=inv.qty or 0,
            ) for inv in inventory
        ],
    )


@router.get("/{vk_id}/reports", response_model=list[PlayerReportOut])
def get_player_reports(
    vk_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    player = db.query(User).filter(User.vk_id == vk_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    reports = (
        db.query(StitchReport)
        .filter(StitchReport.user_id == vk_id)
        .order_by(StitchReport.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        PlayerReportOut(
            id=r.id, user_id=r.user_id, amount=r.amount,
            photo_after_url=r.photo_after_url, photo_before_url=r.photo_before_url,
            note=r.note, status=r.status,
            context_type=r.context_type, context_id=r.context_id,
            reviewer_id=r.reviewer_id,
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in reports
    ]


# ── Просмотр полей игрока ──

class AdminFieldCellOut(BaseModel):
    id: int
    col: int
    row: int
    kind: str
    plant_id: int | None
    plant_name: str | None
    plant_emoji: str | None
    plant_image_young: str | None
    plant_image_grown: str | None
    plant_image_harvested: str | None = None
    occupant_user_id: int | None
    tent_id: int | None
    tent_name: str | None
    tent_image: str | None
    plot: PlayerPlotOut | None


class AdminFieldDetailOut(BaseModel):
    id: int
    code: str
    name: str
    map_url: str | None
    cols: int
    rows: int
    grid_color: str
    created_at: str | None
    cells: list[AdminFieldCellOut]
    tents: list[AdminTentOut]


class AdminTentOut(BaseModel):
    id: int
    name: str
    image_url: str | None
    kind: str
    col1: int
    row1: int
    col2: int
    row2: int
    build_status: str
    accumulated: int
    required: int


@router.get("/{vk_id}/fields/{field_id}", response_model=AdminFieldDetailOut)
def get_player_field(
    vk_id: int,
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    player = db.query(User).filter(User.vk_id == vk_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    f = db.query(Field).filter(Field.id == field_id).first()
    if f is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Поле не найдено")

    cell_ids = [c.id for c in f.cells if c.kind == "bed"]
    plots_by_cell: dict[int, Plot] = {}
    if cell_ids:
        plots_by_cell = {
            p.cell_id: p
            for p in db.query(Plot).filter(
                Plot.user_id == vk_id, Plot.cell_id.in_(cell_ids)
            ).all()
        }
    tent_ids = [t.id for t in f.tents]
    builds_by_tent: dict[int, TentBuild] = {}
    if tent_ids:
        builds_by_tent = {
            tb.tent_id: tb
            for tb in db.query(TentBuild).filter(
                TentBuild.user_id == vk_id, TentBuild.tent_id.in_(tent_ids)
            ).all()
        }

    cells_out = []
    for c in f.cells:
        plant_name = None
        plant_emoji = None
        plant_image_young = None
        plant_image_grown = None
        plant_image_harvested = None
        plant_id = None
        occupant_user_id = None
        plot_out = None
        p = plots_by_cell.get(c.id) if c.kind == "bed" else None
        if p is not None:
            occupant_user_id = vk_id
            plant_id = p.plant_id
            plant_name = p.plant.name
            plant_emoji = p.plant.emoji
            plant_image_young = p.plant.image_young_url
            plant_image_grown = p.plant.image_grown_url
            plant_image_harvested = p.plant.image_harvested_url
            plot_out = PlayerPlotOut(
                id=p.id, plant_id=p.plant_id, plant_name=p.plant.name,
                plant_emoji=p.plant.emoji, qty=p.qty or 0, status=p.status,
                accumulated=p.accumulated or 0, required=p.required or 0,
                crystal_color=p.crystal_color, crystal_count=p.crystal_count,
                cell_id=p.cell_id,
                created_at=p.created_at.isoformat() if p.created_at else None,
                completed_at=p.completed_at.isoformat() if p.completed_at else None,
            )
        tent_name = None
        tent_image = None
        if c.tent_id is not None and c.kind == "tent":
            t = db.query(Tent).filter(Tent.id == c.tent_id).first()
            if t is not None:
                tent_name = t.name
                tent_image = t.image_url
        cells_out.append(AdminFieldCellOut(
            id=c.id, col=c.col, row=c.row, kind=c.kind,
            plant_id=plant_id, occupant_user_id=occupant_user_id, tent_id=c.tent_id,
            plant_name=plant_name, plant_emoji=plant_emoji,
            plant_image_young=plant_image_young, plant_image_grown=plant_image_grown,
            plant_image_harvested=plant_image_harvested,
            plot=plot_out, tent_name=tent_name, tent_image=tent_image,
        ))

    def _tent_out(t: Tent) -> AdminTentOut:
        tb = builds_by_tent.get(t.id)
        return AdminTentOut(
            id=t.id, name=t.name, image_url=t.image_url, kind=t.kind,
            col1=t.col1, row1=t.row1, col2=t.col2, row2=t.row2,
            build_status=tb.build_status if tb is not None else "slot",
            accumulated=(tb.accumulated or 0) if tb is not None else 0,
            required=(tb.required or 0) if tb is not None else (t.required or 0),
        )

    return AdminFieldDetailOut(
        id=f.id, code=f.code, name=f.name, map_url=f.map_url,
        cols=f.cols, rows=f.rows, grid_color=f.grid_color,
        created_at=f.created_at.isoformat() if f.created_at else None,
        cells=cells_out,
        tents=[_tent_out(t) for t in f.tents],
    )


@router.post("/{vk_id}/plots/{plot_id}/reset-norm")
def reset_plot_norm(
    vk_id: int,
    plot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    plot = db.query(Plot).filter(Plot.id == plot_id, Plot.user_id == vk_id).first()
    if plot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Грядка не найдена")

    from services.card_draw import draw_cards, cards_to_json, calculate_norm
    from models import CARD_DRAW_RULES, Plant as PlantModel, UserPlantNorm

    plant_obj = db.query(PlantModel).filter(PlantModel.id == plot.plant_id).first()
    if plant_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")

    level_key = f"plant_{plant_obj.level}"
    num_cards, allow_treasure = CARD_DRAW_RULES.get(level_key, (1, False))
    cards = draw_cards(db, num_cards, allow_treasure)
    plot_user = db.query(User).filter(User.vk_id == vk_id).first()
    unit = calculate_norm(db, plot_user, cards)
    required = unit * plot.qty

    cached = db.query(UserPlantNorm).filter(
        UserPlantNorm.user_id == vk_id, UserPlantNorm.plant_id == plant_obj.id
    ).first()
    if cached is None:
        cached = UserPlantNorm(user_id=vk_id, plant_id=plant_obj.id)
        db.add(cached)
    cached.norm_per_unit = unit

    plot.drawn_cards_json = cards_to_json(cards)
    plot.required = required
    plot.accumulated = 0
    plot.norm_revealed = False
    db.commit()

    from routes.farm import _plot_to_out
    return _plot_to_out(plot)


@router.post("/{vk_id}/restart", response_model=PlayerOut)
def restart_player(
    vk_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """РЕСТАРТ: полное обнуление прогресса игрока (как будто только пришёл в игру)."""
    from models import (
        BarnyardSlot, Cauldron, CraftSession, HouseBuild, Inventory,
        Plot, Production, StitchReport, TentBuild, UserAchievement, UserCrystalNorm,
        UserOrder, UserPet, UserPlantNorm, UserPotion, UserRecipe,
    )

    target = db.query(User).filter(User.vk_id == vk_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")

    for model in (
        UserPlantNorm, UserCrystalNorm, UserAchievement, UserPotion, Cauldron,
        UserPet, BarnyardSlot, CraftSession, UserRecipe, HouseBuild, TentBuild,
        UserOrder, Inventory, Production, Plot, StitchReport,
    ):
        db.query(model).filter(model.user_id == vk_id).delete(synchronize_session=False)

    target.crosses_balance = 0
    target.crosses_total = 0
    target.coins = 0
    target.round = 1
    target.level = 0
    target.unlocked_barnyard = 0
    target.unlocked_pets = 0
    target.unlocked_plot_level = 1
    target.unlocked_garden_level = 0
    target.onboarding_done = False
    target.dice_norm = None
    target.animal_product_norm = None
    target.study_norm_l1 = None
    target.study_norm_l2 = None
    target.study_norm_l3 = None
    target.production_norm_l1 = None
    target.production_norm_l2 = None
    target.production_norm_l3 = None

    db.commit()
    db.refresh(target)

    names = resolve_vk_names([target.vk_id])
    nm = names.get(target.vk_id, {})
    return PlayerOut(
        vk_id=target.vk_id,
        first_name=nm.get("first_name", ""),
        last_name=nm.get("last_name", ""),
        role=target.role,
        crosses_balance=0,
        crosses_total=0,
        coins=0,
        round=1,
        reports_total=0,
        created_at=target.created_at.isoformat() if target.created_at else None,
    )


@router.delete("/{vk_id}/plots/{plot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_player_plot(
    vk_id: int,
    plot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    plot = db.query(Plot).filter(Plot.id == plot_id, Plot.user_id == vk_id).first()
    if plot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Грядка не найдена")

    if plot.cell_id is not None:
        cell = db.query(FieldCell).filter(FieldCell.id == plot.cell_id).first()
        if cell is not None:
            cell.occupant_user_id = None

    db.delete(plot)
    db.commit()
    return None
