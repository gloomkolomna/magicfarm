from __future__ import annotations
import datetime
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import require_role
from models import (
    BAR_ZONE_KINDS, BREWERY_MAX_INGREDIENT_CELLS, BREWERY_ZONE_KINDS, INFIRMARY_ZONE_KINDS,
    Animal, BarZone, BreweryZone,
    ClinicPartCell, CocktailRecipe, Field, FieldAnimal, FieldCell, FieldCocktailRecipe, FieldPet,
    FieldPlant, FieldPotionRecipe,
    GATHER_WINDOW_KINDS, GatherCell, GatherCellIngredient, Ingredient, InfirmaryZone, KASSA_KIND,
    Pet, PetZone, Plant, PlantBed, PotionRecipe, ProductionTemplate, REMEDY_DEVICE_LIMIT,
    Remedy, RemedyDeviceCell, RemedyDeviceRemedy, Tent, TradeCell,
    TradeCellIngredient, User, WITCH_HOUSE_KIND,
)
from services.uploads import remove_upload, save_upload
from routes.potions import _recipe_out

router = APIRouter(prefix="/api/admin/fields", tags=["admin-fields"])

MIN_DIM = 1
MAX_DIM = 30
MAX_COORD = 999
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
BRUSH_KINDS = {"bed", "pet", "barnyard"}


def _get_field_or_404(field_id: int, db: Session) -> Field:
    f = db.query(Field).filter(Field.id == field_id).first()
    if f is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Локация не найдена")
    return f


def _validate_dim(value: int, name: str) -> int:
    if value < MIN_DIM or value > MAX_DIM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{name} должна быть от {MIN_DIM} до {MAX_DIM}",
        )
    return value


def _normalize_rect(col1: int, row1: int, col2: int, row2: int):
    """Приводит прямоугольник к canon-виду (col1<=col2, row1<=row2)."""
    return (
        min(col1, col2), min(row1, row2),
        max(col1, col2), max(row1, row2),
    )


def _reset_cell_to_empty(field_id: int, col: int, row: int, db: Session) -> None:
    cell = db.query(FieldCell).filter(
        FieldCell.field_id == field_id, FieldCell.col == col, FieldCell.row == row
    ).first()
    if cell is not None:
        cell.kind = "empty"
        cell.plant_id = None
        cell.occupant_user_id = None
        cell.tent_id = None


def _trim_out_of_bounds(f: Field, db: Session) -> None:
    """Удаляет зоны/прямоугольники, вышедшие за новые границы сетки, и освобождает их клетки."""
    cols, rows = f.cols, f.rows
    for t in list(f.tents):
        if t.col2 >= cols or t.row2 >= rows:
            for cell in db.query(FieldCell).filter(FieldCell.tent_id == t.id).all():
                cell.kind = "empty"
                cell.tent_id = None
            remove_upload(t.image_url)
            db.delete(t)
    for pb in list(f.plant_beds):
        if pb.col2 >= cols or pb.row2 >= rows:
            for r in range(pb.row1, pb.row2 + 1):
                for c in range(pb.col1, pb.col2 + 1):
                    _reset_cell_to_empty(f.id, c, r, db)
            db.delete(pb)
    for pz in list(f.pet_zones):
        if pz.col2 >= cols or pz.row2 >= rows:
            for r in range(pz.row1, pz.row2 + 1):
                for c in range(pz.col1, pz.col2 + 1):
                    _reset_cell_to_empty(f.id, c, r, db)
            db.delete(pz)
    for z in list(f.brewery_zones):
        if z.col2 >= cols or z.row2 >= rows:
            remove_upload(z.image_url)
            db.delete(z)
    for z in list(f.bar_zones):
        if z.col2 >= cols or z.row2 >= rows:
            remove_upload(z.image_url)
            db.delete(z)
    for gc in db.query(GatherCell).filter(GatherCell.field_id == f.id).all():
        if gc.col >= cols or gc.row >= rows:
            _reset_cell_to_empty(f.id, gc.col, gc.row, db)
            db.delete(gc)
    for tc in db.query(TradeCell).filter(TradeCell.field_id == f.id).all():
        if tc.col >= cols or tc.row >= rows:
            _reset_cell_to_empty(f.id, tc.col, tc.row, db)
            db.delete(tc)
    for pc in db.query(ClinicPartCell).filter(ClinicPartCell.field_id == f.id).all():
        if pc.col >= cols or pc.row >= rows:
            _reset_cell_to_empty(f.id, pc.col, pc.row, db)
            db.delete(pc)


def _ensure_grid(f: Field, db: Session) -> None:
    """Гарантирует, что для поля есть все клетки cols×rows (kind=empty по умолчанию).
    Лишние клетки (вышедшие за пределы при уменьшении размеров) удаляются."""
    existing = {(c.col, c.row): c for c in db.query(FieldCell).filter(FieldCell.field_id == f.id).all()}
    for r in range(f.rows):
        for c in range(f.cols):
            if (c, r) not in existing:
                db.add(FieldCell(field_id=f.id, col=c, row=r, kind="empty"))
    _trim_out_of_bounds(f, db)
    db.flush()
    for cell in db.query(FieldCell).filter(FieldCell.field_id == f.id).all():
        if cell.col >= f.cols or cell.row >= f.rows:
            db.delete(cell)


def _make_code(name: str, db: Session) -> str:
    """Генерирует уникальный code локации. Из кириллицы делаем field_N, чтобы
    не тянуть зависимость транслитерации."""
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "field"
    if not base[0].isalpha():
        base = "field_" + base
    code = base
    n = 2
    while db.query(Field).filter(Field.code == code).first() is not None:
        code = f"{base}_{n}"
        n += 1
    return code


class FieldCreate(BaseModel):
    name: str
    cols: int = 6
    rows: int = 4
    plant_category: str | None = None
    min_level: int = 0
    field_kind: str | None = None


class FieldUpdate(BaseModel):
    name: str | None = None
    cols: int | None = None
    rows: int | None = None
    grid_color: str | None = None
    plant_category: str | None = None
    min_level: int | None = None
    field_kind: str | None = None
    cols: int | None = None
    rows: int | None = None
    grid_color: str | None = None


class CellOut(BaseModel):
    id: int
    col: int
    row: int
    kind: str
    plant_id: int | None
    occupant_user_id: int | None
    tent_id: int | None


class TentOut(BaseModel):
    id: int
    name: str
    image_url: str | None
    kind: str
    col1: int
    row1: int
    col2: int
    row2: int
    builder_user_id: int | None
    build_status: str
    accumulated: int
    required: int
    crystal_color: str | None
    crystal_count: int | None
    drawn_cards_json: str | None
    norm_revealed: bool = False


class PlantBedOut(BaseModel):
    id: int
    field_id: int
    col1: int
    row1: int
    col2: int
    row2: int
    plant_category: str | None
    plant_id: int | None
    occupant_user_id: int | None


class PetZoneOut(BaseModel):
    id: int
    field_id: int
    col1: int
    row1: int
    col2: int
    row2: int


class BreweryZoneOut(BaseModel):
    id: int
    field_id: int
    zone_kind: str
    col1: int
    row1: int
    col2: int
    row2: int
    image_url: str | None
    recipe_id: int | None


class InfirmaryZoneOut(BaseModel):
    id: int
    field_id: int
    zone_kind: str
    col1: int
    row1: int
    col2: int
    row2: int


class BarZoneOut(BaseModel):
    id: int
    field_id: int
    zone_kind: str
    col1: int
    row1: int
    col2: int
    row2: int
    image_url: str | None
    cocktail_recipe_id: int | None
    cocktail_recipe_name: str | None = None


class GatherCellOut(BaseModel):
    id: int
    field_id: int
    col: int
    row: int
    window: str
    ingredient_ids: list[int] = []
    ingredient_names: list[str] = []


class TradeCellOut(BaseModel):
    id: int
    field_id: int
    col: int
    row: int
    ingredient_ids: list[int] = []
    ingredient_names: list[str] = []


class ClinicPartCellOut(BaseModel):
    id: int
    field_id: int
    col: int
    row: int
    part_code: str


class PlantOut(BaseModel):
    id: int
    code: str
    name: str
    emoji: str | None
    category: str
    level: int
    norm_per_crystal: int
    description: str | None
    stitch_condition: str | None
    image_url: str | None
    image_young_url: str | None
    image_grown_url: str | None
    image_harvested_url: str | None


class FieldOut(BaseModel):
    id: int
    code: str
    name: str
    map_url: str | None
    cols: int
    rows: int
    grid_color: str
    plant_category: str | None
    min_level: int = 0
    field_kind: str | None
    created_at: datetime.datetime | None


class FieldDetailOut(FieldOut):
    cells: list[CellOut]
    tents: list[TentOut]
    plants: list[PlantOut]
    plant_beds: list[PlantBedOut] = []
    pet_zones: list[PetZoneOut] = []
    animal_ids: list[int] = []
    pet_ids: list[int] = []
    brewery_zones: list[BreweryZoneOut] = []
    bar_zones: list[BarZoneOut] = []
    gather_cells: list[GatherCellOut] = []
    trade_cells: list[TradeCellOut] = []
    part_cells: list[ClinicPartCellOut] = []
    infirmary_zones: list[InfirmaryZoneOut] = []
    device_cells: list[RemedyDeviceCellOut] = []
    potion_recipes: list = []
    potion_recipe_ids: list[int] = []
    cocktail_recipes: list = []
    cocktail_recipe_ids: list[int] = []


def _field_to_out(f: Field) -> FieldOut:
    return FieldOut(
        id=f.id, code=f.code, name=f.name, map_url=f.map_url,
        cols=f.cols, rows=f.rows, grid_color=f.grid_color,
        plant_category=f.plant_category, min_level=f.min_level,
        field_kind=f.field_kind,
        created_at=f.created_at,
    )


def _cell_to_out(c: FieldCell) -> CellOut:
    return CellOut(
        id=c.id, col=c.col, row=c.row, kind=c.kind,
        plant_id=c.plant_id, occupant_user_id=c.occupant_user_id, tent_id=c.tent_id,
    )


def _tent_to_out(t: Tent) -> TentOut:
    return TentOut(
        id=t.id, name=t.name, image_url=t.image_url, kind=t.kind,
        col1=t.col1, row1=t.row1, col2=t.col2, row2=t.row2,
        builder_user_id=t.builder_user_id, build_status=t.build_status,
        accumulated=t.accumulated, required=t.required,
        crystal_color=t.crystal_color, crystal_count=t.crystal_count,
        drawn_cards_json=t.drawn_cards_json,
    )


def _plant_to_out(p: Plant) -> PlantOut:
    return PlantOut(
        id=p.id, code=p.code, name=p.name, emoji=p.emoji,
        category=p.category, level=p.level, norm_per_crystal=p.norm_per_crystal,
        description=p.description, stitch_condition=p.stitch_condition,
        image_url=p.image_url, image_young_url=p.image_young_url, image_grown_url=p.image_grown_url,
        image_harvested_url=p.image_harvested_url,
    )


@router.get("", response_model=list[FieldOut])
def list_fields(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(Field).order_by(Field.id.asc()).all()
    return [_field_to_out(f) for f in rows]


@router.post("", response_model=FieldOut, status_code=status.HTTP_201_CREATED)
def create_field(
    req: FieldCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    cols = _validate_dim(req.cols, "Ширина")
    rows = _validate_dim(req.rows, "Высота")
    code = _make_code(name, db)
    f = Field(code=code, name=name, cols=cols, rows=rows,
              plant_category=req.plant_category, min_level=req.min_level,
              field_kind=req.field_kind)
    db.add(f)
    db.commit()
    db.refresh(f)
    _ensure_grid(f, db)
    db.commit()
    db.refresh(f)
    return _field_to_out(f)


@router.put("/{field_id}", response_model=FieldDetailOut)
def update_field(
    field_id: int,
    req: FieldUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        f.name = name
    if req.cols is not None:
        f.cols = _validate_dim(req.cols, "Ширина")
    if req.rows is not None:
        f.rows = _validate_dim(req.rows, "Высота")
    if req.grid_color is not None:
        if not HEX_COLOR_RE.match(req.grid_color):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Цвет должен быть #RRGGBB")
        f.grid_color = req.grid_color
    if req.plant_category is not None:
        f.plant_category = req.plant_category
    if req.min_level is not None:
        f.min_level = req.min_level
    if req.field_kind is not None:
        f.field_kind = req.field_kind
    if req.cols is not None or req.rows is not None:
        _ensure_grid(f, db)
    db.commit()
    db.refresh(f)
    return _detail(f, db)


@router.put("/{field_id}/map", response_model=FieldOut)
def upload_map(
    field_id: int,
    map_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    new_url = save_upload(map_image, f"field_{f.id}", max_size=1600)
    remove_upload(f.map_url)
    f.map_url = new_url
    db.commit()
    db.refresh(f)
    return _field_to_out(f)


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    remove_upload(f.map_url)
    for t in f.tents:
        remove_upload(t.image_url)
    for z in f.brewery_zones:
        remove_upload(z.image_url)
    db.delete(f)
    db.commit()
    return None


class SetCellsRequest(BaseModel):
    cells: list[dict]
    kind: str = "bed"


@router.put("/{field_id}/cells/blocked", response_model=FieldDetailOut)
def set_blocked_cells(
    field_id: int,
    req: SetCellsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """Задаёт клетки указанного kind. Клетки из списка → kind,
    все остальные не-tent клетки → bed. plant_id/occupant сбрасываются."""
    if req.kind not in BRUSH_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый тип клетки: {req.kind}. Допустимые: {', '.join(sorted(BRUSH_KINDS))}",
        )
    f = _get_field_or_404(field_id, db)
    wanted = set()
    for item in req.cells:
        try:
            c = int(item["col"]); r = int(item["row"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверные координаты клетки")
        if c < 0 or r < 0 or c >= f.cols or r >= f.rows:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Клетка вне поля")
        wanted.add((c, r))
    from models import BarnyardSlot
    occupied_cells = {
        row[0] for row in db.query(BarnyardSlot.cell_id).filter(
            BarnyardSlot.cell_id.isnot(None), BarnyardSlot.animal_id.isnot(None)
        ).all()
    }
    for cell in f.cells:
        if cell.kind == "tent":
            continue
        leaves_barnyard = (
            cell.kind == "barnyard"
            and ((cell.col, cell.row) in wanted and req.kind != "barnyard"
                 or (cell.col, cell.row) not in wanted and req.kind == "barnyard")
        )
        if leaves_barnyard and cell.id in occupied_cells:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Загон ({cell.col}, {cell.row}) занят животным — сначала выселите его",
            )
    for cell in f.cells:
        if cell.kind == "tent":
            continue
        if (cell.col, cell.row) in wanted:
            cell.kind = req.kind
            cell.plant_id = None
            cell.occupant_user_id = None
        elif cell.kind == req.kind:
            cell.kind = "empty"
    db.commit()
    db.refresh(f)
    return _detail(f, db)


class CellKindRequest(BaseModel):
    kind: str


@router.put("/{field_id}/cell/{col}/{row}", response_model=CellOut)
def set_cell_kind(
    field_id: int,
    col: int,
    row: int,
    req: CellKindRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """Точечно меняет kind одной клетки. Если клетка уже этого kind → empty (тоггл).
    Шатры (tent) иммунитетны. kind ∈ {bed, pet, barnyard}."""
    if req.kind not in BRUSH_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый тип клетки: {req.kind}. Допустимые: {', '.join(sorted(BRUSH_KINDS))}",
        )
    f = _get_field_or_404(field_id, db)
    if col < 0 or row < 0 or col >= f.cols or row >= f.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Клетка вне поля")
    cell = db.query(FieldCell).filter(
        FieldCell.field_id == f.id, FieldCell.col == col, FieldCell.row == row
    ).first()
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клетка не найдена")
    if cell.kind == "tent":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Клетка занята шатром")

    new_kind = "empty" if cell.kind == req.kind else req.kind
    if cell.kind == "barnyard" and new_kind != "barnyard":
        from models import BarnyardSlot
        occupied = db.query(BarnyardSlot).filter(
            BarnyardSlot.cell_id == cell.id, BarnyardSlot.animal_id.isnot(None)
        ).first()
        if occupied is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Загон занят животным — сначала выселите его",
            )

    cell.kind = new_kind
    if cell.kind == "empty":
        cell.plant_id = None
        cell.occupant_user_id = None
    db.commit()
    db.refresh(cell)
    return _cell_to_out(cell)


class FieldPlantsRequest(BaseModel):
    plant_ids: list[int]


@router.put("/{field_id}/plants", response_model=list[PlantOut])
def set_field_plants(
    field_id: int,
    req: FieldPlantsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    valid_ids = {p.id for p in db.query(Plant).filter(Plant.id.in_(req.plant_ids)).all()}
    db.query(FieldPlant).filter(FieldPlant.field_id == f.id).delete()
    for pid in req.plant_ids:
        if pid in valid_ids:
            db.add(FieldPlant(field_id=f.id, plant_id=pid))
    db.commit()
    db.refresh(f)
    return [_plant_to_out(fp.plant) for fp in f.plants]


class FieldAnimalsRequest(BaseModel):
    animal_ids: list[int]


class FieldPetsRequest(BaseModel):
    pet_ids: list[int]


@router.put("/{field_id}/animals", response_model=list[int])
def set_field_animals(
    field_id: int,
    req: FieldAnimalsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    valid_ids = {a.id for a in db.query(Animal).filter(Animal.id.in_(req.animal_ids)).all()}
    db.query(FieldAnimal).filter(FieldAnimal.field_id == f.id).delete()
    for aid in req.animal_ids:
        if aid in valid_ids:
            db.add(FieldAnimal(field_id=f.id, animal_id=aid))
    db.commit()
    db.refresh(f)
    return [fa.animal_id for fa in f.animals]


@router.put("/{field_id}/pets", response_model=list[int])
def set_field_pets(
    field_id: int,
    req: FieldPetsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    valid_ids = {p.id for p in db.query(Pet).filter(Pet.id.in_(req.pet_ids)).all()}
    db.query(FieldPet).filter(FieldPet.field_id == f.id).delete()
    for pid in req.pet_ids:
        if pid in valid_ids:
            db.add(FieldPet(field_id=f.id, pet_id=pid))
    db.commit()
    db.refresh(f)
    return [fp.pet_id for fp in f.pets]


class TentCreate(BaseModel):
    name: str
    kind: str = "alchemy"
    col1: int
    row1: int
    col2: int
    row2: int


@router.post("/{field_id}/tents", response_model=TentOut, status_code=status.HTTP_201_CREATED)
def create_tent(
    field_id: int,
    name: str = Form(...),
    kind: str = Form("alchemy"),
    col1: int = Form(...),
    row1: int = Form(...),
    col2: int = Form(...),
    row2: int = Form(...),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    _ensure_grid(f, db)
    if kind == WITCH_HOUSE_KIND and f.field_kind != "house":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дом ведьмы размещается только на локациях типа «Дома»",
        )
    tmpl = None
    if kind != WITCH_HOUSE_KIND:
        tmpl = db.query(ProductionTemplate).filter(ProductionTemplate.code == kind).first()
        if tmpl is None:
            all_kinds = [pt.code for pt in db.query(ProductionTemplate).all()] + [WITCH_HOUSE_KIND]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Тип шатра должен быть одним из: {', '.join(sorted(all_kinds))}",
            )
    if kind == KASSA_KIND:
        existing = db.query(Tent).filter(Tent.kind == KASSA_KIND).first()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Касса уже размещена — касса может быть только одна",
            )
    nm = name.strip()
    if not nm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название шатра обязательно")

    c1, r1, c2, r2 = _normalize_rect(col1, row1, col2, row2)
    if c1 < 0 or r1 < 0 or c2 >= f.cols or r2 >= f.rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Прямоугольник шатра выходит за пределы поля",
        )

    # Запретить пересечение с другими шатрами.
    for t in f.tents:
        if not (c2 < t.col1 or c1 > t.col2 or r2 < t.row1 or r1 > t.row2):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Шатёр пересекается с «{t.name}»",
            )

    image_url = save_upload(image, f"tent_{f.id}", max_size=512) if image else None
    t = Tent(
        field_id=f.id, name=nm, image_url=image_url, kind=kind,
        col1=c1, row1=r1, col2=c2, row2=r2,
        build_status="slot", accumulated=0, required=tmpl.required if tmpl else 0,
    )
    db.add(t)
    db.flush()  # нужен t.id

    # Пометить клетки прямоугольника как tent.
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            cell = db.query(FieldCell).filter(
                FieldCell.field_id == f.id, FieldCell.col == c, FieldCell.row == r
            ).first()
            if cell is None:
                cell = FieldCell(field_id=f.id, col=c, row=r)
                db.add(cell)
            if cell.kind == "tent" and cell.tent_id != t.id:
                continue
            cell.kind = "tent"
            cell.tent_id = t.id
            cell.plant_id = None
            cell.occupant_user_id = None

    db.commit()
    db.refresh(t)
    return _tent_to_out(t)


@router.delete("/{field_id}/tents/{tent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tent(
    field_id: int,
    tent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    t = db.query(Tent).filter(Tent.id == tent_id, Tent.field_id == f.id).first()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шатёр не найден")
    # Освободить клетки прямоугольника → empty.
    for cell in db.query(FieldCell).filter(FieldCell.tent_id == t.id).all():
        cell.kind = "empty"
        cell.tent_id = None
    remove_upload(t.image_url)
    db.delete(t)
    db.commit()
    return None


class TentUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None


@router.put("/{field_id}/tents/{tent_id}", response_model=TentOut)
def update_tent(
    field_id: int,
    tent_id: int,
    req: TentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    t = db.query(Tent).filter(Tent.id == tent_id, Tent.field_id == f.id).first()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шатёр не найден")
    if req.name is not None:
        nm = req.name.strip()
        if not nm:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название шатра обязательно")
        t.name = nm
    if req.kind is not None and req.kind != t.kind:
        kind = req.kind
        if kind == WITCH_HOUSE_KIND and f.field_kind != "house":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Дом ведьмы размещается только на локациях типа «Дома»",
            )
        tmpl = None
        if kind != WITCH_HOUSE_KIND:
            tmpl = db.query(ProductionTemplate).filter(ProductionTemplate.code == kind).first()
            if tmpl is None:
                all_kinds = [pt.code for pt in db.query(ProductionTemplate).all()] + [WITCH_HOUSE_KIND]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Тип шатра должен быть одним из: {', '.join(sorted(all_kinds))}",
                )
        if kind == KASSA_KIND:
            existing = db.query(Tent).filter(Tent.kind == KASSA_KIND, Tent.id != t.id).first()
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Касса уже размещена — касса может быть только одна",
                )
        t.kind = kind
        t.required = tmpl.required if tmpl else 0
    db.commit()
    db.refresh(t)
    return _tent_to_out(t)


def _detail(f: Field, db: Session) -> FieldDetailOut:
    return FieldDetailOut(
        id=f.id, code=f.code, name=f.name, map_url=f.map_url,
        cols=f.cols, rows=f.rows, grid_color=f.grid_color,
        plant_category=f.plant_category, min_level=f.min_level,
        field_kind=f.field_kind,
        created_at=f.created_at,
        cells=[_cell_to_out(c) for c in f.cells],
        tents=[_tent_to_out(t) for t in f.tents],
        plants=[_plant_to_out(fp.plant) for fp in f.plants],
        plant_beds=[
            PlantBedOut(id=pb.id, field_id=pb.field_id, col1=pb.col1, row1=pb.row1, col2=pb.col2, row2=pb.row2, plant_category=pb.plant_category, plant_id=pb.plant_id, occupant_user_id=pb.occupant_user_id)
            for pb in f.plant_beds
        ],
        pet_zones=[
            PetZoneOut(id=pz.id, field_id=pz.field_id, col1=pz.col1, row1=pz.row1, col2=pz.col2, row2=pz.row2)
            for pz in f.pet_zones
        ],
        animal_ids=[fa.animal_id for fa in f.animals],
        pet_ids=[fp.pet_id for fp in f.pets],
        brewery_zones=[
            BreweryZoneOut(id=z.id, field_id=z.field_id, zone_kind=z.zone_kind,
                           col1=z.col1, row1=z.row1, col2=z.col2, row2=z.row2,
                           image_url=z.image_url, recipe_id=z.recipe_id)
            for z in f.brewery_zones
        ],
        bar_zones=[
            BarZoneOut(id=z.id, field_id=z.field_id, zone_kind=z.zone_kind,
                       col1=z.col1, row1=z.row1, col2=z.col2, row2=z.row2,
                       image_url=z.image_url, cocktail_recipe_id=z.cocktail_recipe_id,
                       cocktail_recipe_name=z.recipe.name if z.recipe else None)
            for z in f.bar_zones
        ],
        gather_cells=[_gather_cell_out(gc) for gc in f.gather_cells] if f.field_kind == "meadow" else [],
        trade_cells=[_trade_cell_out(tc) for tc in f.trade_cells] if f.field_kind == "shop" else [],
        part_cells=[_part_cell_out(pc) for pc in f.part_cells] if f.field_kind == "infirmary" else [],
        infirmary_zones=[_infirmary_zone_out(z) for z in f.infirmary_zones] if f.field_kind in ("infirmary", "remedy_lab") else [],
        device_cells=[_device_cell_out(dc) for dc in db.query(RemedyDeviceCell).filter(RemedyDeviceCell.field_id == f.id).all()] if f.field_kind == "remedy_lab" else [],
        potion_recipes=[_recipe_out(fpr.recipe) for fpr in f.potion_recipes],
        potion_recipe_ids=[fpr.recipe_id for fpr in f.potion_recipes],
        cocktail_recipes=[
            {"id": fcr.recipe.id, "code": fcr.recipe.code, "name": fcr.recipe.name, "image_url": fcr.recipe.image_url}
            for fcr in f.cocktail_recipes
        ],
        cocktail_recipe_ids=[fcr.cocktail_recipe_id for fcr in f.cocktail_recipes],
    )


@router.get("/{field_id}", response_model=FieldDetailOut)
def get_field_detail(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return _detail(_get_field_or_404(field_id, db), db)


@router.post("/{field_id}/cleanup", response_model=FieldDetailOut)
def cleanup_field(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """Чистит зоны/клетки, вышедшие за границы сетки (мусор после изменения размеров)."""
    f = _get_field_or_404(field_id, db)
    _ensure_grid(f, db)
    db.commit()
    db.refresh(f)
    return _detail(f, db)


@router.post("/{field_id}/plant-beds", response_model=PlantBedOut, status_code=status.HTTP_201_CREATED)
def create_plant_bed(
    field_id: int,
    col1: int = Form(...),
    row1: int = Form(...),
    col2: int = Form(...),
    row2: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    _ensure_grid(f, db)
    c1, r1, c2, r2 = _normalize_rect(col1, row1, col2, row2)
    if c1 < 0 or r1 < 0 or c2 >= f.cols or r2 >= f.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Прямоугольник выходит за пределы поля")

    for pb in f.plant_beds:
        if not (c2 < pb.col1 or c1 > pb.col2 or r2 < pb.row1 or r1 > pb.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пересекается с существующей грядкой")

    for t in f.tents:
        if not (c2 < t.col1 or c1 > t.col2 or r2 < t.row1 or r1 > t.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Пересекается с шатром «{t.name}»")

    for pz in f.pet_zones:
        if not (c2 < pz.col1 or c1 > pz.col2 or r2 < pz.row1 or r1 > pz.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пересекается с зоной питомца")

    pb = PlantBed(field_id=f.id, col1=c1, row1=r1, col2=c2, row2=r2, plant_category=f.plant_category)
    db.add(pb)
    db.flush()

    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            cell = db.query(FieldCell).filter(
                FieldCell.field_id == f.id, FieldCell.col == c, FieldCell.row == r
            ).first()
            if cell is None:
                cell = FieldCell(field_id=f.id, col=c, row=r)
                db.add(cell)
            cell.kind = "bed"
            cell.tent_id = None
            cell.plant_id = None
            cell.occupant_user_id = None

    db.commit()
    db.refresh(pb)
    return PlantBedOut(id=pb.id, field_id=pb.field_id, col1=pb.col1, row1=pb.row1, col2=pb.col2, row2=pb.row2, plant_category=pb.plant_category, plant_id=pb.plant_id, occupant_user_id=pb.occupant_user_id)


@router.delete("/{field_id}/plant-beds/{bed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plant_bed(
    field_id: int,
    bed_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    pb = db.query(PlantBed).filter(PlantBed.id == bed_id, PlantBed.field_id == f.id).first()
    if pb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Грядка не найдена")

    for r in range(pb.row1, pb.row2 + 1):
        for c in range(pb.col1, pb.col2 + 1):
            cell = db.query(FieldCell).filter(
                FieldCell.field_id == f.id, FieldCell.col == c, FieldCell.row == r
            ).first()
            if cell is not None:
                cell.kind = "empty"
                cell.plant_id = None
                cell.occupant_user_id = None
                cell.tent_id = None

    db.delete(pb)
    db.commit()
    return None


@router.post("/{field_id}/pet-zones", response_model=PetZoneOut, status_code=status.HTTP_201_CREATED)
def create_pet_zone(
    field_id: int,
    col1: int = Form(...),
    row1: int = Form(...),
    col2: int = Form(...),
    row2: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    _ensure_grid(f, db)
    c1, r1, c2, r2 = _normalize_rect(col1, row1, col2, row2)
    if c1 < 0 or r1 < 0 or c2 >= f.cols or r2 >= f.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Прямоугольник выходит за пределы поля")

    for pz in f.pet_zones:
        if not (c2 < pz.col1 or c1 > pz.col2 or r2 < pz.row1 or r1 > pz.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пересекается с существующей зоной питомца")

    for t in f.tents:
        if not (c2 < t.col1 or c1 > t.col2 or r2 < t.row1 or r1 > t.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Пересекается с шатром «{t.name}»")

    for pb in f.plant_beds:
        if not (c2 < pb.col1 or c1 > pb.col2 or r2 < pb.row1 or r1 > pb.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пересекается с грядкой")

    pz = PetZone(field_id=f.id, col1=c1, row1=r1, col2=c2, row2=r2)
    db.add(pz)
    db.flush()

    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            cell = db.query(FieldCell).filter(
                FieldCell.field_id == f.id, FieldCell.col == c, FieldCell.row == r
            ).first()
            if cell is None:
                cell = FieldCell(field_id=f.id, col=c, row=r)
                db.add(cell)
            cell.kind = "pet"
            cell.tent_id = None
            cell.plant_id = None
            cell.occupant_user_id = None

    db.commit()
    db.refresh(pz)
    return PetZoneOut(id=pz.id, field_id=pz.field_id, col1=pz.col1, row1=pz.row1, col2=pz.col2, row2=pz.row2)


@router.delete("/{field_id}/pet-zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pet_zone(
    field_id: int,
    zone_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    pz = db.query(PetZone).filter(PetZone.id == zone_id, PetZone.field_id == f.id).first()
    if pz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зона питомца не найдена")

    for r in range(pz.row1, pz.row2 + 1):
        for c in range(pz.col1, pz.col2 + 1):
            cell = db.query(FieldCell).filter(
                FieldCell.field_id == f.id, FieldCell.col == c, FieldCell.row == r
            ).first()
            if cell is not None:
                cell.kind = "empty"
                cell.plant_id = None
                cell.occupant_user_id = None
                cell.tent_id = None

    db.delete(pz)
    db.commit()
    return None


def _check_brewery_field(f: Field) -> None:
    if f.field_kind != "brewery":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Зоны зельеварни размещаются только на локациях типа «Зельеварня»",
        )


def _check_brewery_rect(f: Field, c1: int, r1: int, c2: int, r2: int) -> None:
    if c1 < 0 or r1 < 0 or c2 >= f.cols or r2 >= f.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Прямоугольник выходит за пределы поля")

    for z in f.brewery_zones:
        if not (c2 < z.col1 or c1 > z.col2 or r2 < z.row1 or r1 > z.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пересекается с другой зоной зельеварни")

    for t in f.tents:
        if not (c2 < t.col1 or c1 > t.col2 or r2 < t.row1 or r1 > t.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Пересекается с шатром «{t.name}»")

    for pb in f.plant_beds:
        if not (c2 < pb.col1 or c1 > pb.col2 or r2 < pb.row1 or r1 > pb.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пересекается с грядкой")

    for pz in f.pet_zones:
        if not (c2 < pz.col1 or c1 > pz.col2 or r2 < pz.row1 or r1 > pz.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пересекается с зоной питомца")


def _zone_out(z: BreweryZone) -> BreweryZoneOut:
    return BreweryZoneOut(id=z.id, field_id=z.field_id, zone_kind=z.zone_kind,
                          col1=z.col1, row1=z.row1, col2=z.col2, row2=z.row2,
                          image_url=z.image_url, recipe_id=z.recipe_id)


def _gather_cell_out(gc: GatherCell) -> GatherCellOut:
    return GatherCellOut(
        id=gc.id, field_id=gc.field_id, col=gc.col, row=gc.row, window=gc.window,
        ingredient_ids=[gci.ingredient_id for gci in gc.ingredients],
        ingredient_names=[gci.ingredient.name for gci in gc.ingredients],
    )


def _trade_cell_out(tc: TradeCell) -> TradeCellOut:
    return TradeCellOut(
        id=tc.id, field_id=tc.field_id, col=tc.col, row=tc.row,
        ingredient_ids=[tci.ingredient_id for tci in tc.ingredients],
        ingredient_names=[tci.ingredient.name for tci in tc.ingredients],
    )


def _part_cell_out(pc: ClinicPartCell) -> ClinicPartCellOut:
    return ClinicPartCellOut(
        id=pc.id, field_id=pc.field_id,
        col=pc.col, row=pc.row, part_code=pc.part_code,
    )


def _infirmary_zone_out(z: InfirmaryZone) -> InfirmaryZoneOut:
    return InfirmaryZoneOut(
        id=z.id, field_id=z.field_id, zone_kind=z.zone_kind,
        col1=z.col1, row1=z.row1, col2=z.col2, row2=z.row2,
    )


def _get_gather_cell_on_field(gc_id: int, field_id: int, db: Session) -> GatherCell:
    gc = db.query(GatherCell).filter(GatherCell.id == gc_id, GatherCell.field_id == field_id).first()
    if gc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клетка добычи не найдена")
    return gc


def _get_trade_cell_on_field(tc_id: int, field_id: int, db: Session) -> TradeCell:
    tc = db.query(TradeCell).filter(TradeCell.id == tc_id, TradeCell.field_id == field_id).first()
    if tc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клетка бартера не найдена")
    return tc


def _check_gather_field(f: Field) -> None:
    if f.field_kind != "meadow":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Клетки добычи размещаются только на локациях типа «Лесная поляна»",
        )


def _check_trade_field(f: Field) -> None:
    if f.field_kind != "shop":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Клетки бартера размещаются только на локациях типа «Городская лавка»",
        )


def _valid_ingredient_ids(ids: list[int], db: Session) -> set[int]:
    if not ids:
        return set()
    return {i.id for i in db.query(Ingredient).filter(Ingredient.id.in_(ids)).all()}


def _mark_cell_kind(field_id: int, col: int, row: int, kind: str, db: Session) -> None:
    cell = db.query(FieldCell).filter(
        FieldCell.field_id == field_id, FieldCell.col == col, FieldCell.row == row
    ).first()
    if cell is None:
        cell = FieldCell(field_id=field_id, col=col, row=row)
        db.add(cell)
    if cell.kind != "tent":
        cell.kind = kind
        cell.plant_id = None
        cell.occupant_user_id = None


@router.post("/{field_id}/brewery-zones", response_model=BreweryZoneOut, status_code=status.HTTP_201_CREATED)
def create_brewery_zone(
    field_id: int,
    zone_kind: str = Form(...),
    col1: int = Form(...),
    row1: int = Form(...),
    col2: int = Form(...),
    row2: int = Form(...),
    image: UploadFile | None = File(default=None),
    recipe_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    _ensure_grid(f, db)
    _check_brewery_field(f)
    if zone_kind not in BREWERY_ZONE_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Тип зоны должен быть одним из: {', '.join(BREWERY_ZONE_KINDS)}",
        )
    c1, r1, c2, r2 = _normalize_rect(col1, row1, col2, row2)

    if zone_kind == "ingredient":
        if c1 != c2 or r1 != r2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Окошко ингредиента — ровно одна клетка")
        count = sum(1 for z in f.brewery_zones if z.zone_kind == "ingredient")
        if count >= BREWERY_MAX_INGREDIENT_CELLS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Максимум {BREWERY_MAX_INGREDIENT_CELLS} окошек ингредиентов",
            )

    if zone_kind == "recipe_card":
        if recipe_id is not None:
            linked = {fpr.recipe_id for fpr in f.potion_recipes}
            if recipe_id not in linked:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Зелье не привязано к этой локации")
    elif recipe_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="recipe_id задаётся только для карточки рецепта")

    _check_brewery_rect(f, c1, r1, c2, r2)

    image_url = save_upload(image, f"brewery_{f.id}", max_size=512) if image else None
    z = BreweryZone(field_id=f.id, zone_kind=zone_kind, col1=c1, row1=r1, col2=c2, row2=r2,
                    image_url=image_url, recipe_id=recipe_id if zone_kind == "recipe_card" else None)
    db.add(z)
    db.commit()
    db.refresh(z)
    return _zone_out(z)


@router.put("/{field_id}/brewery-zones/{zone_id}/image", response_model=BreweryZoneOut)
def upload_brewery_zone_image(
    field_id: int,
    zone_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    z = db.query(BreweryZone).filter(BreweryZone.id == zone_id, BreweryZone.field_id == f.id).first()
    if z is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зона не найдена")
    new_url = save_upload(image, f"brewery_{f.id}_{z.id}", max_size=512)
    remove_upload(z.image_url)
    z.image_url = new_url
    db.commit()
    db.refresh(z)
    return _zone_out(z)


@router.delete("/{field_id}/brewery-zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brewery_zone(
    field_id: int,
    zone_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    z = db.query(BreweryZone).filter(BreweryZone.id == zone_id, BreweryZone.field_id == f.id).first()
    if z is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зона не найдена")
    remove_upload(z.image_url)
    db.delete(z)
    db.commit()
    return None


class FieldPotionRecipesRequest(BaseModel):
    recipe_ids: list[int]


@router.put("/{field_id}/potion-recipes", response_model=list[int])
def set_field_potion_recipes(
    field_id: int,
    req: FieldPotionRecipesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    valid_ids = {r.id for r in db.query(PotionRecipe).filter(PotionRecipe.id.in_(req.recipe_ids)).all()}
    removed = {fpr.recipe_id for fpr in f.potion_recipes} - valid_ids
    if removed:
        for z in db.query(BreweryZone).filter(
            BreweryZone.field_id == f.id, BreweryZone.zone_kind == "recipe_card",
            BreweryZone.recipe_id.in_(removed),
        ).all():
            z.recipe_id = None
    db.query(FieldPotionRecipe).filter(FieldPotionRecipe.field_id == f.id).delete()
    for rid in req.recipe_ids:
        if rid in valid_ids:
            db.add(FieldPotionRecipe(field_id=f.id, recipe_id=rid))
    db.commit()
    db.refresh(f)
    return [fpr.recipe_id for fpr in f.potion_recipes]


# ── Зоны лесного бара ──

def _check_bar_field(f: Field) -> None:
    if f.field_kind != "forest_bar":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Зоны бара размещаются только на локациях типа «Лесной бар»",
        )


def _check_bar_rect(f: Field, c1: int, r1: int, c2: int, r2: int) -> None:
    if c1 < 0 or r1 < 0 or c2 >= f.cols or r2 >= f.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Прямоугольник выходит за пределы поля")

    for z in f.bar_zones:
        if not (c2 < z.col1 or c1 > z.col2 or r2 < z.row1 or r1 > z.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пересекается с другой зоной бара")

    for t in f.tents:
        if not (c2 < t.col1 or c1 > t.col2 or r2 < t.row1 or r1 > t.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Пересекается с шатром «{t.name}»")


def _bar_zone_out(z: BarZone) -> BarZoneOut:
    return BarZoneOut(
        id=z.id, field_id=z.field_id, zone_kind=z.zone_kind,
        col1=z.col1, row1=z.row1, col2=z.col2, row2=z.row2,
        image_url=z.image_url, cocktail_recipe_id=z.cocktail_recipe_id,
        cocktail_recipe_name=z.recipe.name if z.recipe else None,
    )


@router.post("/{field_id}/bar-zones", response_model=BarZoneOut, status_code=status.HTTP_201_CREATED)
def create_bar_zone(
    field_id: int,
    zone_kind: str = Form(...),
    col1: int = Form(...),
    row1: int = Form(...),
    col2: int = Form(...),
    row2: int = Form(...),
    image: UploadFile | None = File(default=None),
    cocktail_recipe_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    _ensure_grid(f, db)
    _check_bar_field(f)
    if zone_kind not in BAR_ZONE_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Тип зоны должен быть одним из: {', '.join(BAR_ZONE_KINDS)}",
        )
    c1, r1, c2, r2 = _normalize_rect(col1, row1, col2, row2)

    if zone_kind == "cocktail_card":
        if cocktail_recipe_id is not None:
            linked = {fcr.cocktail_recipe_id for fcr in f.cocktail_recipes}
            if cocktail_recipe_id not in linked:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Коктейль не привязан к этой локации")
    elif cocktail_recipe_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cocktail_recipe_id задаётся только для карточки коктейля")

    _check_bar_rect(f, c1, r1, c2, r2)

    image_url = save_upload(image, f"bar_{f.id}", max_size=512) if image else None
    z = BarZone(field_id=f.id, zone_kind=zone_kind, col1=c1, row1=r1, col2=c2, row2=r2,
                image_url=image_url, cocktail_recipe_id=cocktail_recipe_id if zone_kind == "cocktail_card" else None)
    db.add(z)
    db.commit()
    db.refresh(z)
    return _bar_zone_out(z)


@router.put("/{field_id}/bar-zones/{zone_id}/image", response_model=BarZoneOut)
def upload_bar_zone_image(
    field_id: int,
    zone_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    z = db.query(BarZone).filter(BarZone.id == zone_id, BarZone.field_id == f.id).first()
    if z is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зона не найдена")
    new_url = save_upload(image, f"bar_{f.id}_{z.id}", max_size=512)
    remove_upload(z.image_url)
    z.image_url = new_url
    db.commit()
    db.refresh(z)
    return _bar_zone_out(z)


@router.delete("/{field_id}/bar-zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bar_zone(
    field_id: int,
    zone_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    z = db.query(BarZone).filter(BarZone.id == zone_id, BarZone.field_id == f.id).first()
    if z is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зона не найдена")
    remove_upload(z.image_url)
    db.delete(z)
    db.commit()
    return None


class FieldCocktailRecipesRequest(BaseModel):
    recipe_ids: list[int]


@router.put("/{field_id}/cocktail-recipes", response_model=list[int])
def set_field_cocktail_recipes(
    field_id: int,
    req: FieldCocktailRecipesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    valid_ids = {r.id for r in db.query(CocktailRecipe).filter(CocktailRecipe.id.in_(req.recipe_ids)).all()}
    removed = {fcr.cocktail_recipe_id for fcr in f.cocktail_recipes} - valid_ids
    if removed:
        for z in db.query(BarZone).filter(
            BarZone.field_id == f.id, BarZone.zone_kind == "cocktail_card",
            BarZone.cocktail_recipe_id.in_(removed),
        ).all():
            z.cocktail_recipe_id = None
    db.query(FieldCocktailRecipe).filter(FieldCocktailRecipe.field_id == f.id).delete()
    for rid in req.recipe_ids:
        if rid in valid_ids:
            db.add(FieldCocktailRecipe(field_id=f.id, cocktail_recipe_id=rid))
    db.commit()
    db.refresh(f)
    return [fcr.cocktail_recipe_id for fcr in f.cocktail_recipes]


# ── Клетки добычи (лесная поляна) ──

class GatherCellCreate(BaseModel):
    col: int
    row: int
    window: str = "always"
    ingredient_ids: list[int] = []


class GatherCellUpdate(BaseModel):
    window: str | None = None
    ingredient_ids: list[int] | None = None


@router.post("/{field_id}/gather-cells", response_model=GatherCellOut, status_code=status.HTTP_201_CREATED)
def create_gather_cell(
    field_id: int,
    req: GatherCellCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    _check_gather_field(f)
    if req.window not in GATHER_WINDOW_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Окно должно быть одним из: {', '.join(GATHER_WINDOW_KINDS)}",
        )
    if req.col < 0 or req.row < 0 or req.col >= f.cols or req.row >= f.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Клетка вне поля")
    existing = db.query(GatherCell).filter(
        GatherCell.field_id == f.id, GatherCell.col == req.col, GatherCell.row == req.row
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="На этой клетке уже настроена добыча")

    gc = GatherCell(field_id=f.id, col=req.col, row=req.row, window=req.window)
    db.add(gc)
    db.flush()
    valid_ids = _valid_ingredient_ids(req.ingredient_ids, db)
    for iid in req.ingredient_ids:
        if iid in valid_ids:
            db.add(GatherCellIngredient(gather_cell_id=gc.id, ingredient_id=iid))
    _mark_cell_kind(f.id, req.col, req.row, "gather", db)
    db.commit()
    db.refresh(gc)
    return _gather_cell_out(gc)


@router.put("/{field_id}/gather-cells/{gc_id}", response_model=GatherCellOut)
def update_gather_cell(
    field_id: int,
    gc_id: int,
    req: GatherCellUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    gc = _get_gather_cell_on_field(gc_id, field_id, db)
    if req.window is not None:
        if req.window not in GATHER_WINDOW_KINDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Окно должно быть одним из: {', '.join(GATHER_WINDOW_KINDS)}",
            )
        gc.window = req.window
    if req.ingredient_ids is not None:
        db.query(GatherCellIngredient).filter(GatherCellIngredient.gather_cell_id == gc.id).delete()
        valid_ids = _valid_ingredient_ids(req.ingredient_ids, db)
        for iid in req.ingredient_ids:
            if iid in valid_ids:
                db.add(GatherCellIngredient(gather_cell_id=gc.id, ingredient_id=iid))
    db.commit()
    db.refresh(gc)
    return _gather_cell_out(gc)


@router.delete("/{field_id}/gather-cells/{gc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gather_cell(
    field_id: int,
    gc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    gc = _get_gather_cell_on_field(gc_id, field_id, db)
    cell = db.query(FieldCell).filter(
        FieldCell.field_id == gc.field_id, FieldCell.col == gc.col, FieldCell.row == gc.row
    ).first()
    if cell is not None and cell.kind == "gather":
        cell.kind = "empty"
    db.delete(gc)
    db.commit()
    return None


# ── Клетки бартера (городская лавка) ──

class TradeCellCreate(BaseModel):
    col: int
    row: int
    ingredient_ids: list[int] = []


class TradeCellUpdate(BaseModel):
    ingredient_ids: list[int] | None = None


@router.post("/{field_id}/trade-cells", response_model=TradeCellOut, status_code=status.HTTP_201_CREATED)
def create_trade_cell(
    field_id: int,
    req: TradeCellCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    _check_trade_field(f)
    if req.col < 0 or req.row < 0 or req.col >= f.cols or req.row >= f.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Клетка вне поля")
    existing = db.query(TradeCell).filter(
        TradeCell.field_id == f.id, TradeCell.col == req.col, TradeCell.row == req.row
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="На этой клетке уже настроен бартер")

    tc = TradeCell(field_id=f.id, col=req.col, row=req.row)
    db.add(tc)
    db.flush()
    valid_ids = _valid_ingredient_ids(req.ingredient_ids, db)
    for iid in req.ingredient_ids:
        if iid in valid_ids:
            db.add(TradeCellIngredient(trade_cell_id=tc.id, ingredient_id=iid))
    _mark_cell_kind(f.id, req.col, req.row, "trade", db)
    db.commit()
    db.refresh(tc)
    return _trade_cell_out(tc)


@router.put("/{field_id}/trade-cells/{tc_id}", response_model=TradeCellOut)
def update_trade_cell(
    field_id: int,
    tc_id: int,
    req: TradeCellUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    tc = _get_trade_cell_on_field(tc_id, field_id, db)
    if req.ingredient_ids is not None:
        db.query(TradeCellIngredient).filter(TradeCellIngredient.trade_cell_id == tc.id).delete()
        valid_ids = _valid_ingredient_ids(req.ingredient_ids, db)
        for iid in req.ingredient_ids:
            if iid in valid_ids:
                db.add(TradeCellIngredient(trade_cell_id=tc.id, ingredient_id=iid))
    db.commit()
    db.refresh(tc)
    return _trade_cell_out(tc)


@router.delete("/{field_id}/trade-cells/{tc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trade_cell(
    field_id: int,
    tc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    tc = _get_trade_cell_on_field(tc_id, field_id, db)
    cell = db.query(FieldCell).filter(
        FieldCell.field_id == tc.field_id, FieldCell.col == tc.col, FieldCell.row == tc.row
    ).first()
    if cell is not None and cell.kind == "trade":
        cell.kind = "empty"
    db.delete(tc)
    db.commit()
    return None


# ── Части тела (лесная лечебница) ──

def _check_infirmary_field(f: Field) -> None:
    if f.field_kind != "infirmary":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Части тела размещаются только на локациях типа «Лесная лечебница»",
        )


def _get_part_cell_on_field(pc_id: int, field_id: int, db: Session) -> ClinicPartCell:
    pc = db.query(ClinicPartCell).filter(ClinicPartCell.id == pc_id, ClinicPartCell.field_id == field_id).first()
    if pc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Часть тела не найдена")
    return pc


class PartCellCreate(BaseModel):
    col: int
    row: int
    part_code: str


class PartCellUpdate(BaseModel):
    part_code: str | None = None


@router.post("/{field_id}/part-cells", response_model=ClinicPartCellOut, status_code=status.HTTP_201_CREATED)
def create_part_cell(
    field_id: int,
    req: PartCellCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    _check_infirmary_field(f)
    part_code = req.part_code.strip()
    if not part_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Код части тела обязателен")
    if req.col < 0 or req.row < 0 or req.col >= f.cols or req.row >= f.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Клетка вне поля")
    existing = db.query(ClinicPartCell).filter(
        ClinicPartCell.field_id == f.id, ClinicPartCell.col == req.col, ClinicPartCell.row == req.row
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="На этой клетке уже настроена часть тела")

    pc = ClinicPartCell(field_id=f.id, col=req.col, row=req.row, part_code=part_code)
    db.add(pc)
    _mark_cell_kind(f.id, req.col, req.row, "body_part", db)
    db.commit()
    db.refresh(pc)
    return _part_cell_out(pc)


@router.put("/{field_id}/part-cells/{pc_id}", response_model=ClinicPartCellOut)
def update_part_cell(
    field_id: int,
    pc_id: int,
    req: PartCellUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    pc = _get_part_cell_on_field(pc_id, field_id, db)
    if req.part_code is not None:
        part_code = req.part_code.strip()
        if not part_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Код части тела обязателен")
        pc.part_code = part_code
    db.commit()
    db.refresh(pc)
    return _part_cell_out(pc)


@router.delete("/{field_id}/part-cells/{pc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_part_cell(
    field_id: int,
    pc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    pc = _get_part_cell_on_field(pc_id, field_id, db)
    cell = db.query(FieldCell).filter(
        FieldCell.field_id == pc.field_id, FieldCell.col == pc.col, FieldCell.row == pc.row
    ).first()
    if cell is not None and cell.kind == "body_part":
        cell.kind = "empty"
    db.delete(pc)
    db.commit()
    return None


# ── Зоны лечебницы (животное / книга) ──

def _check_infirmary_rect(f: Field, c1: int, r1: int, c2: int, r2: int) -> None:
    if c1 < 0 or r1 < 0 or c2 >= f.cols or r2 >= f.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Прямоугольник выходит за пределы поля")
    for z in f.infirmary_zones:
        if not (c2 < z.col1 or c1 > z.col2 or r2 < z.row1 or r1 > z.row2):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пересекается с другой зоной лечебницы")


class InfirmaryZoneCreate(BaseModel):
    zone_kind: str
    col1: int
    row1: int
    col2: int
    row2: int


@router.post("/{field_id}/infirmary-zones", response_model=InfirmaryZoneOut, status_code=status.HTTP_201_CREATED)
def create_infirmary_zone(
    field_id: int,
    req: InfirmaryZoneCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    _ensure_grid(f, db)
    if f.field_kind not in ("infirmary", "remedy_lab"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Зоны книги размещаются только на локациях «Лесная лечебница» и «Лаборатория снадобий»")
    if req.zone_kind not in INFIRMARY_ZONE_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Тип зоны должен быть одним из: {', '.join(INFIRMARY_ZONE_KINDS)}",
        )
    c1, r1, c2, r2 = _normalize_rect(req.col1, req.row1, req.col2, req.row2)
    _check_infirmary_rect(f, c1, r1, c2, r2)

    z = InfirmaryZone(field_id=f.id, zone_kind=req.zone_kind, col1=c1, row1=r1, col2=c2, row2=r2)
    db.add(z)
    db.commit()
    db.refresh(z)
    return _infirmary_zone_out(z)


@router.delete("/{field_id}/infirmary-zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_infirmary_zone(
    field_id: int,
    zone_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    z = db.query(InfirmaryZone).filter(InfirmaryZone.id == zone_id, InfirmaryZone.field_id == f.id).first()
    if z is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зона лечебницы не найдена")
    db.delete(z)
    db.commit()
    return None


# ── Приборы Лесной аптеки ──

class DeviceRemedyItemOut(BaseModel):
    remedy_id: int
    remedy_name: str
    remedy_image_url: str | None


class RemedyDeviceCellOut(BaseModel):
    id: int
    col1: int
    row1: int
    col2: int
    row2: int
    install_cards: int
    image_url: str | None
    name: str | None
    remedies: list[DeviceRemedyItemOut]


def _check_remedy_lab_field(f: Field) -> None:
    if f.field_kind != "remedy_lab":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Приборы размещаются только на локациях типа «Лесная аптека»",
        )


def _device_cell_out(cell: RemedyDeviceCell) -> RemedyDeviceCellOut:
    return RemedyDeviceCellOut(
        id=cell.id, col1=cell.col, row1=cell.row,
        col2=cell.col2 if cell.col2 is not None else cell.col,
        row2=cell.row2 if cell.row2 is not None else cell.row,
        install_cards=cell.install_cards or 10,
        image_url=cell.image_url,
        name=cell.name,
        remedies=[
            DeviceRemedyItemOut(
                remedy_id=r.remedy_id,
                remedy_name=r.remedy.name if r.remedy else "?",
                remedy_image_url=r.remedy.image_url if r.remedy else None,
            )
            for r in cell.remedies
        ],
    )


class RemedyDeviceCellCreate(BaseModel):
    col1: int
    row1: int
    col2: int
    row2: int
    install_cards: int = 10
    remedy_ids: list[int] = []
    name: str | None = None


class RemedyDeviceCellUpdate(BaseModel):
    install_cards: int | None = None
    remedy_ids: list[int] | None = None
    name: str | None = None


def _apply_remedy_ids(cell: RemedyDeviceCell, remedy_ids: list[int], db: Session) -> None:
    remedies = db.query(Remedy).filter(Remedy.id.in_(remedy_ids)).all() if remedy_ids else []
    if len(remedies) != len(set(remedy_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некоторые лекарства не найдены")
    db.query(RemedyDeviceRemedy).filter(RemedyDeviceRemedy.cell_id == cell.id).delete(
        synchronize_session=False
    )
    for rid in remedy_ids:
        db.add(RemedyDeviceRemedy(cell_id=cell.id, remedy_id=rid))


@router.post("/{field_id}/remedy-device-cells", response_model=RemedyDeviceCellOut, status_code=status.HTTP_201_CREATED)
def create_remedy_device_cell(
    field_id: int,
    req: RemedyDeviceCellCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    _ensure_grid(f, db)
    _check_remedy_lab_field(f)
    c1, r1, c2, r2 = _normalize_rect(req.col1, req.row1, req.col2, req.row2)
    if c1 < 0 or r1 < 0 or c2 >= f.cols or r2 >= f.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Прямоугольник выходит за пределы поля")
    if req.install_cards < 1 or req.install_cards > 30:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Карт на установку: от 1 до 30")
    for d in db.query(RemedyDeviceCell).filter(RemedyDeviceCell.field_id == f.id).all():
        if not (c2 < d.col or c1 > (d.col2 or d.col) or r2 < d.row or r1 > (d.row2 or d.row)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Зона прибора пересекается с уже установленным прибором",
            )
    count = db.query(RemedyDeviceCell).filter(RemedyDeviceCell.field_id == f.id).count()
    if count >= REMEDY_DEVICE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Максимум {REMEDY_DEVICE_LIMIT} приборов в аптеке",
        )

    cell = RemedyDeviceCell(
        field_id=f.id, col=c1, row=r1, col2=c2, row2=r2,
        install_cards=req.install_cards,
        name=(req.name or "").strip() or None,
    )
    db.add(cell)
    db.flush()
    _apply_remedy_ids(cell, req.remedy_ids, db)
    for rr in range(r1, r2 + 1):
        for cc in range(c1, c2 + 1):
            _mark_cell_kind(f.id, cc, rr, "remedy_device", db)
    db.commit()
    db.refresh(cell)
    return _device_cell_out(cell)


@router.put("/{field_id}/remedy-device-cells/{cell_id}", response_model=RemedyDeviceCellOut)
def update_remedy_device_cell(
    field_id: int,
    cell_id: int,
    req: RemedyDeviceCellUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    cell = db.query(RemedyDeviceCell).filter(
        RemedyDeviceCell.id == cell_id, RemedyDeviceCell.field_id == field_id
    ).first()
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Прибор не найден")
    if req.install_cards is not None:
        if req.install_cards < 1 or req.install_cards > 30:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Карт на установку: от 1 до 30")
        cell.install_cards = req.install_cards
    if req.name is not None:
        cell.name = req.name.strip() or None
    if req.remedy_ids is not None:
        _apply_remedy_ids(cell, req.remedy_ids, db)
    db.commit()
    db.refresh(cell)
    return _device_cell_out(cell)


@router.put("/{field_id}/remedy-device-cells/{cell_id}/image", response_model=RemedyDeviceCellOut)
def upload_remedy_device_cell_image(
    field_id: int,
    cell_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    f = _get_field_or_404(field_id, db)
    cell = db.query(RemedyDeviceCell).filter(
        RemedyDeviceCell.id == cell_id, RemedyDeviceCell.field_id == f.id
    ).first()
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Прибор не найден")
    new_url = save_upload(image, f"remedy_device_{f.id}_{cell.id}", max_size=512)
    remove_upload(cell.image_url)
    cell.image_url = new_url
    db.commit()
    db.refresh(cell)
    return _device_cell_out(cell)


@router.delete("/{field_id}/remedy-device-cells/{cell_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_remedy_device_cell(
    field_id: int,
    cell_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    cell = db.query(RemedyDeviceCell).filter(
        RemedyDeviceCell.id == cell_id, RemedyDeviceCell.field_id == field_id
    ).first()
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Прибор не найден")
    remove_upload(cell.image_url)
    for rr in range(cell.row, (cell.row2 or cell.row) + 1):
        for cc in range(cell.col, (cell.col2 or cell.col) + 1):
            _reset_cell_to_empty(cell.field_id, cc, rr, db)
    db.delete(cell)
    db.commit()
    return None
