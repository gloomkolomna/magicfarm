from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import (
    BarnyardSlot, Field, FieldCell, Inventory, PlantBed, Plot, Production, Tent,
    TentBuild, User, UserAchievement, UserIngredient, UserPatientState, UserPet,
)
from routes.admin_players import (
    AdminFieldCellOut, AdminFieldDetailOut, AdminTentOut, PlayerPlotOut,
)

router = APIRouter(prefix="/api/players", tags=["players"])

SEARCH_CANDIDATE_LIMIT = 500


class PlayerSearchOut(BaseModel):
    vk_id: int
    display_name: str
    level: int
    coins: int
    crosses_total: int


class FarmPlotOut(BaseModel):
    plant_name: str | None
    plant_emoji: str | None
    status: str
    accumulated: int
    required: int


class FarmProductionOut(BaseModel):
    kind: str
    name: str
    status: str
    accumulated: int
    required: int


class FarmItemOut(BaseModel):
    item_id: int
    name: str
    emoji: str | None
    qty: int


class FarmPetOut(BaseModel):
    name: str
    emoji: str | None


class FarmFieldOut(BaseModel):
    id: int
    code: str
    name: str
    cols: int
    rows: int
    map_url: str | None


class FarmOut(BaseModel):
    vk_id: int
    display_name: str
    level: int
    coins: int
    crosses_total: int
    round: int
    achievements_total: int
    fields: list[FarmFieldOut]
    plots: list[FarmPlotOut]
    productions: list[FarmProductionOut]
    plants: list[FarmItemOut]
    products: list[FarmItemOut]
    ingredients: list[FarmItemOut]
    pets: list[FarmPetOut]


def _player_field_ids(db: Session, vk_id: int) -> set[int]:
    """Поля, где у игрока есть хоть какая-то активность: грядки, шатры, загоны, питомцы, грядки-гнезда."""
    ids: set[int] = set()

    cell_ids = [
        r[0] for r in db.query(Plot.cell_id).filter(
            Plot.user_id == vk_id, Plot.cell_id.isnot(None)
        ).all()
    ]
    if cell_ids:
        ids.update(
            r[0] for r in db.query(FieldCell.field_id).filter(FieldCell.id.in_(cell_ids)).all()
        )

    tent_ids = [
        r[0] for r in db.query(TentBuild.tent_id).filter(
            TentBuild.user_id == vk_id, TentBuild.tent_id.isnot(None)
        ).all()
    ]
    if tent_ids:
        ids.update(
            r[0] for r in db.query(Tent.field_id).filter(Tent.id.in_(tent_ids)).all()
        )

    bs_cell_ids = [
        r[0] for r in db.query(BarnyardSlot.cell_id).filter(
            BarnyardSlot.user_id == vk_id, BarnyardSlot.cell_id.isnot(None)
        ).all()
    ]
    if bs_cell_ids:
        ids.update(
            r[0] for r in db.query(FieldCell.field_id).filter(FieldCell.id.in_(bs_cell_ids)).all()
        )

    up_cell_ids = [
        r[0] for r in db.query(UserPet.cell_id).filter(
            UserPet.user_id == vk_id, UserPet.cell_id.isnot(None)
        ).all()
    ]
    if up_cell_ids:
        ids.update(
            r[0] for r in db.query(FieldCell.field_id).filter(FieldCell.id.in_(up_cell_ids)).all()
        )

    ids.update(
        r[0] for r in db.query(PlantBed.field_id).filter(PlantBed.occupant_user_id == vk_id).all()
    )

    active_patient = (
        db.query(UserPatientState)
        .filter(UserPatientState.user_id == vk_id, UserPatientState.status != "released")
        .order_by(UserPatientState.patient_id.asc())
        .first()
    )
    if active_patient is not None and active_patient.current_field_id is not None:
        ids.add(active_patient.current_field_id)
    return ids


def _resolve_names(db: Session, users: list[User]) -> dict[int, dict]:
    ids = [u.vk_id for u in users if not u.display_name]
    if not ids:
        return {}
    from services.vk_names import resolve_vk_names
    return resolve_vk_names(ids)


def _display_name(user: User, names: dict[int, dict]) -> str:
    if user.display_name:
        return user.display_name
    nm = names.get(user.vk_id, {})
    full = f"{nm.get('first_name', '')} {nm.get('last_name', '')}".strip()
    return full or f"Игрок {user.vk_id}"


@router.get("/search", response_model=list[PlayerSearchOut])
def search_players(
    q: str = "",
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    users = (
        db.query(User)
        .filter(User.status != "blocked")
        .order_by(User.level.desc(), User.crosses_total.desc())
        .limit(SEARCH_CANDIDATE_LIMIT)
        .all()
    )
    q = (q or "").strip()
    if q.isdigit():
        users = [u for u in users if str(u.vk_id) == q]
    elif q:
        needle = q.casefold()
        names = _resolve_names(db, users)
        users = [u for u in users if needle in _display_name(u, names).casefold()]

    result = []
    names = _resolve_names(db, users)
    for u in users[:max(1, min(limit, 100))]:
        result.append(PlayerSearchOut(
            vk_id=u.vk_id,
            display_name=_display_name(u, names),
            level=u.level or 0,
            coins=u.coins or 0,
            crosses_total=u.crosses_total or 0,
        ))
    return result


@router.get("/{vk_id}/farm", response_model=FarmOut)
def get_player_farm(
    vk_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    player = db.query(User).filter(User.vk_id == vk_id).first()
    if player is None or (player.status or "active") == "blocked":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")

    names = _resolve_names(db, [player])

    plots = db.query(Plot).filter(
        Plot.user_id == vk_id, Plot.plant_id.isnot(None)
    ).order_by(Plot.created_at.desc()).limit(100).all()
    productions = db.query(Production).filter(
        Production.user_id == vk_id
    ).order_by(Production.created_at.desc()).limit(100).all()
    plants = db.query(Inventory).filter(
        Inventory.user_id == vk_id, Inventory.plant_id.isnot(None), Inventory.qty > 0
    ).order_by(Inventory.qty.desc()).limit(100).all()
    products = db.query(Inventory).filter(
        Inventory.user_id == vk_id, Inventory.product_id.isnot(None), Inventory.qty > 0
    ).order_by(Inventory.qty.desc()).limit(100).all()
    ingredients = db.query(UserIngredient).filter(
        UserIngredient.user_id == vk_id, UserIngredient.qty > 0
    ).order_by(UserIngredient.qty.desc()).limit(100).all()
    user_pets = db.query(UserPet).filter(UserPet.user_id == vk_id).all()
    achievements_total = (
        db.query(func.count(UserAchievement.id))
        .filter(UserAchievement.user_id == vk_id).scalar() or 0
    )

    field_ids = _player_field_ids(db, vk_id)
    fields: list[FarmFieldOut] = []
    if field_ids:
        for f in db.query(Field).filter(Field.id.in_(field_ids)).order_by(Field.id.asc()).all():
            fields.append(FarmFieldOut(
                id=f.id, code=f.code, name=f.name,
                cols=f.cols or 0, rows=f.rows or 0, map_url=f.map_url,
            ))

    return FarmOut(
        vk_id=player.vk_id,
        display_name=_display_name(player, names),
        level=player.level or 0,
        coins=player.coins or 0,
        crosses_total=player.crosses_total or 0,
        round=player.round or 1,
        achievements_total=achievements_total,
        fields=fields,
        plots=[
            FarmPlotOut(
                plant_name=p.plant.name if p.plant else None,
                plant_emoji=p.plant.emoji if p.plant else None,
                status=p.status or "planted",
                accumulated=p.accumulated or 0,
                required=p.required or 0,
            )
            for p in plots
        ],
        productions=[
            FarmProductionOut(
                kind=pr.kind or "", name=pr.name or pr.kind or "", status=pr.status or "",
                accumulated=pr.accumulated or 0, required=pr.required or 0,
            )
            for pr in productions
        ],
        plants=[
            FarmItemOut(item_id=i.plant.id, name=i.plant.name, emoji=i.plant.emoji, qty=i.qty or 0)
            for i in plants
        ],
        products=[
            FarmItemOut(item_id=i.product.id, name=i.product.name, emoji=i.product.emoji, qty=i.qty or 0)
            for i in products
        ],
        ingredients=[
            FarmItemOut(item_id=i.ingredient.id, name=i.ingredient.name, emoji=None, qty=i.qty or 0)
            for i in ingredients
        ],
        pets=[
            FarmPetOut(name=up.pet.name, emoji=up.pet.emoji)
            for up in user_pets
        ],
    )


@router.get("/{vk_id}/fields/{field_id}", response_model=AdminFieldDetailOut)
def get_player_field(
    vk_id: int,
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    player = db.query(User).filter(User.vk_id == vk_id).first()
    if player is None or (player.status or "active") == "blocked":
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
        plot_out = None
        occupant_user_id = None
        plant_id = None
        plant_name = plant_emoji = None
        plant_image_young = plant_image_grown = plant_image_harvested = None
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
        tent_name = tent_image = None
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

    pet_zone_cells: dict[int, list[FieldCell]] = {}
    for pz in f.pet_zones:
        pet_zone_cells[pz.id] = [
            c for c in f.cells
            if c.kind == "pet"
            and pz.col1 <= c.col <= pz.col2 and pz.row1 <= c.row <= pz.row2
        ]
    pet_zone_pets: dict[int, UserPet] = {}
    all_pet_cell_ids = [c.id for cells_in_zone in pet_zone_cells.values() for c in cells_in_zone]
    if all_pet_cell_ids:
        for up in db.query(UserPet).filter(
            UserPet.user_id == vk_id, UserPet.cell_id.in_(all_pet_cell_ids)
        ).all():
            for zid, cells_in_zone in pet_zone_cells.items():
                if any(c.id == up.cell_id for c in cells_in_zone):
                    pet_zone_pets[zid] = up
                    break
    pet_zones = []
    for pz in f.pet_zones:
        up = pet_zone_pets.get(pz.id)
        pet = up.pet if up is not None and up.pet is not None else None
        pet_zones.append({
            "id": pz.id, "col1": pz.col1, "row1": pz.row1, "col2": pz.col2, "row2": pz.row2,
            "pet_id": up.pet_id if up is not None else None,
            "pet_name": pet.name if pet else None,
            "pet_emoji": pet.emoji if pet else None,
            "pet_image_url": pet.image_url if pet else None,
            "bonus_description": pet.bonus_description if pet else None,
        })

    return AdminFieldDetailOut(
        id=f.id, code=f.code, name=f.name, map_url=f.map_url,
        cols=f.cols, rows=f.rows, grid_color=f.grid_color,
        created_at=f.created_at.isoformat() if f.created_at else None,
        cells=cells_out,
        tents=[_tent_out(t) for t in f.tents],
        pet_zones=pet_zones,
    )
