from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from db import get_db
from deps import require_role
from models import AllowedPlayer, Field, FieldCell, FieldPlant, Inventory, Plant, PlantBed, Plot, Production, StitchReport, Tent, TentBuild, User, UserDlcUnlock, UserPlantNorm
from services.uploads import remove_upload
from services.vk_names import resolve_vk_names
from services.production_names import production_display_name

router = APIRouter(prefix="/api/admin/players", tags=["admin-players"])

PLAYER_STATUSES = ("active", "blocked", "readonly")


class PlayerOut(BaseModel):
    vk_id: int
    first_name: str
    last_name: str
    role: str
    status: str
    hidden: bool
    crosses_balance: int
    crosses_total: int
    coins: int
    round: int
    reports_total: int
    created_at: str | None
    trial_until: str | None
    subscription_until: str | None
    subscription_dlc_codes: list[str]
    dlc_locations: list[str]
    is_donor: bool
    donor_exempt: bool


def _is_donor(db: Session, vk_id: int) -> bool:
    from services.donor import is_donor

    return is_donor(db, vk_id)


def _dlc_locations(db: Session, vk_id: int) -> list[str]:
    return sorted(
        r[0] for r in db.query(UserDlcUnlock.location_code)
        .filter(UserDlcUnlock.user_id == vk_id).all()
    )


def _player_out(u: User, reports_total: int, nm: dict, is_donor: bool = False, dlc_locations: list[str] | None = None) -> PlayerOut:
    return PlayerOut(
        vk_id=u.vk_id,
        first_name=nm.get("first_name", ""),
        last_name=nm.get("last_name", ""),
        role=u.role,
        status=u.status or "active",
        hidden=bool(u.hidden),
        crosses_balance=u.crosses_balance or 0,
        crosses_total=u.crosses_total or 0,
        coins=u.coins or 0,
        round=u.round or 1,
        reports_total=reports_total,
        created_at=u.created_at.isoformat() if u.created_at else None,
        trial_until=u.trial_until.isoformat() if u.trial_until else None,
        subscription_until=u.subscription_until.isoformat() if u.subscription_until else None,
        subscription_dlc_codes=[c for c in (u.subscription_dlc_codes or "").split(",") if c],
        dlc_locations=sorted(dlc_locations or []),
        is_donor=is_donor,
        donor_exempt=bool(u.donor_exempt),
    )


@router.get("", response_model=list[PlayerOut])
def list_players(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    users = db.query(User).order_by(User.created_at.desc()).limit(200).all()
    vk_ids = [u.vk_id for u in users]
    names = resolve_vk_names(vk_ids)

    from services.donor import donor_flags

    donor_map = donor_flags(db, vk_ids)

    report_counts = dict(
        db.query(StitchReport.user_id, func.count(StitchReport.id))
        .filter(StitchReport.user_id.in_(vk_ids))
        .group_by(StitchReport.user_id)
        .all()
    )

    dlc_map: dict[int, list[str]] = {}
    for uid, code in db.query(UserDlcUnlock.user_id, UserDlcUnlock.location_code).filter(
        UserDlcUnlock.user_id.in_(vk_ids)
    ).all():
        dlc_map.setdefault(uid, []).append(code)

    result = []
    for u in users:
        nm = names.get(u.vk_id, {})
        result.append(_player_out(u, report_counts.get(u.vk_id, 0), nm, donor_map.get(u.vk_id, False), dlc_map.get(u.vk_id)))
    return result


class PlayerReportOut(BaseModel):
    id: int
    user_id: int
    amount: int
    photo_after_url: str | None
    photo_before_url: str | None
    photo_after_thumb_url: str | None
    photo_before_thumb_url: str | None
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
    norm_per_unit: int | None = None
    crystal_color: str | None
    crystal_count: int | None
    cell_id: int | None
    created_at: str | None
    completed_at: str | None


class PlayerPlantNormOut(BaseModel):
    plant_id: int
    plant_name: str
    plant_emoji: str | None
    norm_per_unit: int


class PlayerBarnyardOut(BaseModel):
    id: int
    animal_id: int | None
    animal_name: str | None
    animal_emoji: str | None
    status: str
    accumulated: int
    required: int
    cell_id: int | None
    cell_col: int | None
    cell_row: int | None
    is_ghost: bool


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
    status: str
    hidden: bool
    crosses_balance: int
    crosses_total: int
    coins: int
    round: int
    reports_total: int
    created_at: str | None
    trial_until: str | None
    subscription_until: str | None
    subscription_dlc_codes: list[str]
    plots: list[PlayerPlotOut]
    productions: list[PlayerProductionOut]
    inventory: list[PlayerInventoryOut]
    plant_norms: list[PlayerPlantNormOut] = []
    dlc_locations: list[str] = []
    barnyard: list[PlayerBarnyardOut] = []
    is_donor: bool = False
    donor_exempt: bool = False


@router.post("/donor-sync")
def trigger_donor_sync(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    from services.donor import sync_all_users

    synced = sync_all_users(db)
    return {"synced": synced}


class DonorExemptRequest(BaseModel):
    enabled: bool


class PlayerHiddenRequest(BaseModel):
    hidden: bool


@router.post("/{vk_id}/donor-exempt", response_model=PlayerOut)
def set_player_donor_exempt(
    vk_id: int,
    req: DonorExemptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    target = db.query(User).filter(User.vk_id == vk_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    target.donor_exempt = bool(req.enabled)
    db.commit()
    db.refresh(target)
    reports_total = db.query(func.count(StitchReport.id)).filter(StitchReport.user_id == vk_id).scalar() or 0
    names = resolve_vk_names([target.vk_id])
    return _player_out(target, reports_total, names.get(target.vk_id, {}), _is_donor(db, vk_id), _dlc_locations(db, vk_id))


@router.post("/{vk_id}/hidden", response_model=PlayerOut)
def set_player_hidden(
    vk_id: int,
    req: PlayerHiddenRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    target = db.query(User).filter(User.vk_id == vk_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    target.hidden = bool(req.hidden)
    db.commit()
    db.refresh(target)
    reports_total = db.query(func.count(StitchReport.id)).filter(StitchReport.user_id == vk_id).scalar() or 0
    names = resolve_vk_names([target.vk_id])
    return _player_out(target, reports_total, names.get(target.vk_id, {}), _is_donor(db, vk_id), _dlc_locations(db, vk_id))


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
    plant_norms = (
        db.query(UserPlantNorm, Plant)
        .join(Plant, Plant.id == UserPlantNorm.plant_id)
        .filter(UserPlantNorm.user_id == vk_id)
        .order_by(Plant.name.asc())
        .all()
    )
    dlc_locations = sorted(
        r[0] for r in db.query(UserDlcUnlock.location_code)
        .filter(UserDlcUnlock.user_id == vk_id).all()
    )

    from models import Animal, BarnyardSlot
    barnyard_slots = (
        db.query(BarnyardSlot)
        .filter(BarnyardSlot.user_id == vk_id)
        .order_by(BarnyardSlot.id.asc())
        .all()
    )
    animals = {a.id: a for a in db.query(Animal).all()}
    cells = {
        c.id: c for c in db.query(FieldCell).filter(
            FieldCell.id.in_([s.cell_id for s in barnyard_slots if s.cell_id is not None])
        ).all()
    }
    fields_by_id = {f.id: f for f in db.query(Field).all()}
    barnyard_out = []
    for s in barnyard_slots:
        cell = cells.get(s.cell_id) if s.cell_id is not None else None
        animal = animals.get(s.animal_id) if s.animal_id is not None else None
        is_ghost = True
        if cell is not None and cell.kind == "barnyard":
            fld = fields_by_id.get(cell.field_id)
            if fld is not None and cell.col < fld.cols and cell.row < fld.rows:
                is_ghost = False
        barnyard_out.append(PlayerBarnyardOut(
            id=s.id, animal_id=s.animal_id,
            animal_name=animal.name if animal else None,
            animal_emoji=animal.emoji if animal else None,
            status=s.status, accumulated=s.accumulated or 0, required=s.required or 0,
            cell_id=s.cell_id, cell_col=cell.col if cell else None, cell_row=cell.row if cell else None,
            is_ghost=is_ghost,
        ))

    return PlayerDetailOut(
        vk_id=player.vk_id,
        first_name=nm.get("first_name", ""),
        last_name=nm.get("last_name", ""),
        role=player.role,
        status=player.status or "active",
        hidden=bool(player.hidden),
        crosses_balance=player.crosses_balance or 0,
        crosses_total=player.crosses_total or 0,
        coins=player.coins or 0,
        round=player.round or 1,
        reports_total=reports_total,
        created_at=player.created_at.isoformat() if player.created_at else None,
        trial_until=player.trial_until.isoformat() if player.trial_until else None,
        subscription_until=player.subscription_until.isoformat() if player.subscription_until else None,
        subscription_dlc_codes=[c for c in (player.subscription_dlc_codes or "").split(",") if c],
        plots=[
            PlayerPlotOut(
                id=p.id, plant_id=p.plant_id, plant_name=p.plant.name,
                plant_emoji=p.plant.emoji, qty=p.qty or 0, status=p.status,
                accumulated=p.accumulated or 0, required=p.required or 0,
                norm_per_unit=(round((p.required or 0) / p.qty) if p.qty else (p.required or 0)),
                crystal_color=p.crystal_color, crystal_count=p.crystal_count,
                cell_id=p.cell_id,
                created_at=p.created_at.isoformat() if p.created_at else None,
                completed_at=p.completed_at.isoformat() if p.completed_at else None,
            ) for p in plots
        ],
        productions=[
            PlayerProductionOut(
                id=pr.id, kind=pr.kind, name=production_display_name(db, pr.kind, pr.name), status=pr.status,
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
        plant_norms=[
            PlayerPlantNormOut(
                plant_id=n.plant_id, plant_name=pl.name,
                plant_emoji=pl.emoji,
                norm_per_unit=n.norm_per_unit or 0,
            ) for n, pl in plant_norms
        ],
        dlc_locations=dlc_locations,
        barnyard=barnyard_out,
        is_donor=_is_donor(db, vk_id),
        donor_exempt=bool(player.donor_exempt),
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
            photo_after_thumb_url=r.photo_after_thumb_url, photo_before_thumb_url=r.photo_before_thumb_url,
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
    field_kind: str | None = None
    created_at: str | None
    cells: list[AdminFieldCellOut]
    tents: list[AdminTentOut]
    pet_zones: list = []


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
        field_kind=f.field_kind,
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


class PlantNormSetRequest(BaseModel):
    norm_per_unit: int


class PlantNormSetOut(BaseModel):
    plant_id: int
    plant_name: str
    norm_per_unit: int
    plots: list[PlayerPlotOut]


@router.put("/{vk_id}/plant-norms/{plant_id}", response_model=PlantNormSetOut)
def set_player_plant_norm(
    vk_id: int,
    plant_id: int,
    req: PlantNormSetRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if req.norm_per_unit < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Цена не может быть отрицательной")
    player = db.query(User).filter(User.vk_id == vk_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    if plant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")

    cached = db.query(UserPlantNorm).filter(
        UserPlantNorm.user_id == vk_id, UserPlantNorm.plant_id == plant_id
    ).first()
    if cached is None:
        cached = UserPlantNorm(user_id=vk_id, plant_id=plant_id, norm_per_unit=req.norm_per_unit)
        db.add(cached)
    else:
        cached.norm_per_unit = req.norm_per_unit

    plots = db.query(Plot).filter(
        Plot.user_id == vk_id, Plot.plant_id == plant_id, Plot.status == "planted"
    ).all()
    for p in plots:
        p.required = req.norm_per_unit * (p.qty or 1)
        p.norm_revealed = True
        if (p.accumulated or 0) >= p.required:
            p.status = "grown"
            p.completed_at = datetime.datetime.utcnow()

    db.commit()

    return PlantNormSetOut(
        plant_id=plant.id,
        plant_name=plant.name,
        norm_per_unit=req.norm_per_unit,
        plots=[
            PlayerPlotOut(
                id=p.id, plant_id=p.plant_id, plant_name=p.plant.name,
                plant_emoji=p.plant.emoji, qty=p.qty or 0, status=p.status,
                accumulated=p.accumulated or 0, required=p.required or 0,
                norm_per_unit=(round((p.required or 0) / p.qty) if p.qty else (p.required or 0)),
                crystal_color=p.crystal_color, crystal_count=p.crystal_count,
                cell_id=p.cell_id,
                created_at=p.created_at.isoformat() if p.created_at else None,
                completed_at=p.completed_at.isoformat() if p.completed_at else None,
            ) for p in plots
        ],
    )


class DlcGrantRequest(BaseModel):
    location_code: str


@router.post("/{vk_id}/dlc", status_code=status.HTTP_201_CREATED)
def grant_player_dlc(
    vk_id: int,
    req: DlcGrantRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    from models import LOCATION_CODES

    if req.location_code not in LOCATION_CODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестная локация")
    player = db.query(User).filter(User.vk_id == vk_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    existing = db.query(UserDlcUnlock).filter(
        UserDlcUnlock.user_id == vk_id, UserDlcUnlock.location_code == req.location_code
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Дополнение уже выдано")
    db.add(UserDlcUnlock(user_id=vk_id, location_code=req.location_code))
    db.commit()
    return {"vk_id": vk_id, "location_code": req.location_code, "granted": True}


@router.delete("/{vk_id}/dlc/{location_code}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_player_dlc(
    vk_id: int,
    location_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    from models import LOCATION_CODES

    if location_code not in LOCATION_CODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестная локация")
    player = db.query(User).filter(User.vk_id == vk_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    row = db.query(UserDlcUnlock).filter(
        UserDlcUnlock.user_id == vk_id, UserDlcUnlock.location_code == location_code
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Дополнение не выдано")
    db.delete(row)
    db.commit()
    return None


class TrialExtendRequest(BaseModel):
    days: int


@router.post("/{vk_id}/trial", response_model=PlayerOut)
def extend_player_trial(
    vk_id: int,
    req: TrialExtendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    from services.subscription import set_trial_days

    target = db.query(User).filter(User.vk_id == vk_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    if not 1 <= req.days <= 3650:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Дней: от 1 до 3650")
    set_trial_days(db, target, req.days)
    db.refresh(target)
    nm = resolve_vk_names([target.vk_id])
    return _player_out(target, 0, nm, dlc_locations=_dlc_locations(db, vk_id))


class DateUntilRequest(BaseModel):
    until: str | None


def _parse_until(value: str | None) -> datetime.datetime | None:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        d = datetime.date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Дата должна быть в формате YYYY-MM-DD")
    return datetime.datetime.combine(d, datetime.time.max)


def _player_out_full(db: Session, target: User) -> PlayerOut:
    reports_total = db.query(func.count(StitchReport.id)).filter(StitchReport.user_id == target.vk_id).scalar() or 0
    names = resolve_vk_names([target.vk_id])
    return _player_out(target, reports_total, names.get(target.vk_id, {}), _is_donor(db, target.vk_id), _dlc_locations(db, target.vk_id))


@router.post("/{vk_id}/trial-until", response_model=PlayerOut)
def set_player_trial_until(
    vk_id: int,
    req: DateUntilRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    target = db.query(User).filter(User.vk_id == vk_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    target.trial_until = _parse_until(req.until)
    db.commit()
    db.refresh(target)
    return _player_out_full(db, target)


@router.post("/{vk_id}/subscription-until", response_model=PlayerOut)
def set_player_subscription_until(
    vk_id: int,
    req: DateUntilRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    target = db.query(User).filter(User.vk_id == vk_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    target.subscription_until = _parse_until(req.until)
    db.commit()
    db.refresh(target)
    return _player_out_full(db, target)


@router.post("/{vk_id}/restart", response_model=PlayerOut)
def restart_player(
    vk_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """РЕСТАРТ: полное обнуление прогресса игрока (как будто только пришёл в игру).

    Админское не затрагивается: каталоги и настройки (растения, товары, локации,
    заказы), приглашения (AllowedPlayer) и выданные админом DLC (UserDlcUnlock).
    Кросс-игровые сущности: открытые бартеры отменяются (предметы из холда возвращаются
    отправителю), неполученные подарки возвращаются отправителям, чат и уведомления игрока
    очищаются. Подарки, отправленные игроком другим, сохраняются — они уже у получателей.
    """
    from sqlalchemy import or_

    from models import (
        BarnyardSlot, BarnyardStorage, BarnyardWithdrawal, Cauldron, ChatMessage,
        CraftSession, Gift, HouseBuild, Inventory, Notification, PetActionLog,
        PetForestTask, Plot, Production, Shaker, StitchReport, TentBuild,
        TradeHold, TradeOffer, UserAchievement, UserCard, UserCrystalNorm,
        UserDlcStoryView, UserExamineLog, UserGatherLog,
        UserIngredient, UserOrder, UserPatientState, UserPet, UserPlantNorm,
        UserPotion, UserRecipe, UserRemedy, UserRemedyCard, UserRemedyDevice,
    )
    from routes.notifications import notify
    from routes.trades import _transfer

    target = db.query(User).filter(User.vk_id == vk_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")

    for r in db.query(StitchReport).filter(StitchReport.user_id == vk_id).all():
        remove_upload(r.photo_before_url)
        remove_upload(r.photo_after_url)
        remove_upload(r.photo_before_thumb_url)
        remove_upload(r.photo_after_thumb_url)

    db.query(ChatMessage).filter(
        or_(ChatMessage.from_user_id == vk_id, ChatMessage.to_user_id == vk_id)
    ).delete(synchronize_session=False)

    offers = db.query(TradeOffer).filter(
        or_(TradeOffer.from_user_id == vk_id, TradeOffer.to_user_id == vk_id)
    ).all()
    for offer in offers:
        if offer.status == "open":
            for hold in db.query(TradeHold).filter(TradeHold.offer_id == offer.id).all():
                _transfer(db, offer.from_user_id, hold.kind, hold.item_id, hold.qty)
                db.flush()
                db.delete(hold)
            partner = offer.to_user_id if offer.from_user_id == vk_id else offer.from_user_id
            notify(db, partner, "♻️ Игрок перезапущен администратором — предложение по бартеру отменено", peer_vk_id=vk_id)
        db.delete(offer)

    gifts = db.query(Gift).filter(
        or_(Gift.from_user_id == vk_id, Gift.to_user_id == vk_id)
    ).all()
    for g in gifts:
        if g.to_user_id == vk_id and g.claimed_at is None:
            _transfer(db, g.from_user_id, g.kind, g.item_id, g.qty)
            db.flush()
            notify(db, g.from_user_id, "♻️ Игрок перезапущен администратором — подарок возвращён", peer_vk_id=vk_id)
            db.delete(g)
        elif g.to_user_id == vk_id:
            db.delete(g)

    for model in (
        UserRemedyDevice, UserRemedyCard, UserRemedy, UserExamineLog, UserCard,
        UserPatientState, UserGatherLog, UserIngredient, PetActionLog, PetForestTask,
        UserDlcStoryView, Shaker, Notification,
        UserPlantNorm, UserCrystalNorm, UserAchievement, UserPotion, Cauldron,
        UserPet, BarnyardWithdrawal, BarnyardStorage, BarnyardSlot,
        CraftSession, UserRecipe, HouseBuild, TentBuild, UserOrder, Inventory,
        Production, Plot, StitchReport,
    ):
        db.query(model).filter(model.user_id == vk_id).delete(synchronize_session=False)

    db.query(FieldCell).filter(FieldCell.occupant_user_id == vk_id).update(
        {FieldCell.occupant_user_id: None}, synchronize_session=False
    )
    db.query(PlantBed).filter(PlantBed.occupant_user_id == vk_id).update(
        {PlantBed.occupant_user_id: None}, synchronize_session=False
    )
    db.query(Tent).filter(Tent.builder_user_id == vk_id).update(
        {Tent.builder_user_id: None}, synchronize_session=False
    )

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
    target.story_seen = False
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
    return _player_out(target, 0, nm, dlc_locations=_dlc_locations(db, vk_id))


class PlayerStatusRequest(BaseModel):
    status: str


@router.post("/{vk_id}/status", response_model=PlayerOut)
def set_player_status(
    vk_id: int,
    req: PlayerStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if req.status not in PLAYER_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Статус должен быть одним из: {', '.join(PLAYER_STATUSES)}",
        )
    target = db.query(User).filter(User.vk_id == vk_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    if target.role == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя менять статус администратора")

    target.status = req.status
    db.commit()
    db.refresh(target)

    reports_total = db.query(func.count(StitchReport.id)).filter(StitchReport.user_id == vk_id).scalar() or 0
    names = resolve_vk_names([target.vk_id])
    nm = names.get(target.vk_id, {})
    return _player_out(target, reports_total, nm, dlc_locations=_dlc_locations(db, vk_id))


@router.delete("/{vk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_player(
    vk_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    from models import (
        BarnyardSlot, BarnyardStorage, BarnyardWithdrawal, Cauldron,
        CraftSession, HouseBuild, PetActionLog, PetForestTask, Plot, Production,
        StitchReport, TentBuild, UserAchievement, UserCard, UserCrystalNorm,
        UserDlcUnlock, UserExamineLog, UserGatherLog, UserIngredient, UserOrder,
        UserPatientState, UserPet, UserPlantNorm, UserPotion, UserRecipe,
        UserRemedy, UserRemedyCard, UserRemedyDevice,
    )

    target = db.query(User).filter(User.vk_id == vk_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    if target.role == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя удалить администратора")

    reports = db.query(StitchReport).filter(StitchReport.user_id == vk_id).all()
    for r in reports:
        remove_upload(r.photo_before_url)
        remove_upload(r.photo_after_url)
        remove_upload(r.photo_before_thumb_url)
        remove_upload(r.photo_after_thumb_url)

    for model in (
        UserRemedyDevice, UserRemedyCard, UserRemedy, UserExamineLog, UserCard,
        UserPatientState, UserGatherLog, UserIngredient, PetActionLog, PetForestTask,
        UserDlcUnlock, UserPlantNorm, UserCrystalNorm, UserAchievement, UserPotion,
        Cauldron, UserPet, BarnyardWithdrawal, BarnyardStorage, BarnyardSlot,
        CraftSession, UserRecipe, HouseBuild, TentBuild, UserOrder, Inventory,
        Production, Plot, StitchReport,
    ):
        db.query(model).filter(model.user_id == vk_id).delete(synchronize_session=False)

    db.query(FieldCell).filter(FieldCell.occupant_user_id == vk_id).update(
        {FieldCell.occupant_user_id: None}, synchronize_session=False
    )
    db.query(PlantBed).filter(PlantBed.occupant_user_id == vk_id).update(
        {PlantBed.occupant_user_id: None}, synchronize_session=False
    )
    db.query(Tent).filter(Tent.builder_user_id == vk_id).update(
        {Tent.builder_user_id: None}, synchronize_session=False
    )
    db.query(AllowedPlayer).filter(AllowedPlayer.vk_id == vk_id).delete(synchronize_session=False)

    db.delete(target)
    db.commit()
    return None


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


@router.delete("/{vk_id}/barnyard/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_player_barnyard_slot(
    vk_id: int,
    slot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    from models import BarnyardSlot

    slot = db.query(BarnyardSlot).filter(
        BarnyardSlot.id == slot_id, BarnyardSlot.user_id == vk_id
    ).first()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Загон не найден")

    db.delete(slot)
    db.commit()
    return None
