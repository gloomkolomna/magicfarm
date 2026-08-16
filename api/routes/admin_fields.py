from __future__ import annotations
import datetime
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import require_role
from models import (
    BREWERY_MAX_INGREDIENT_CELLS, BREWERY_ZONE_KINDS, Animal, BreweryZone, Field, FieldAnimal,
    FieldCell, FieldPet, FieldPlant, FieldPotionRecipe, Pet, PetZone, Plant, PlantBed,
    PotionRecipe, ProductionTemplate, Tent, User, WITCH_HOUSE_KIND,
)
from services.uploads import remove_upload, save_upload

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


def _ensure_grid(f: Field, db: Session) -> None:
    """Гарантирует, что для поля есть все клетки cols×rows (kind=empty по умолчанию).
    Лишние клетки (вышедшие за пределы при уменьшении размеров) удаляются.
    """
    existing = {(c.col, c.row): c for c in db.query(FieldCell).filter(FieldCell.field_id == f.id).all()}
    for r in range(f.rows):
        for c in range(f.cols):
            if (c, r) not in existing:
                db.add(FieldCell(field_id=f.id, col=c, row=r, kind="empty"))
    # Удалить клетки за пределами сетки (кроме занятых шатрами — они внутри).
    for (c, r), cell in existing.items():
        if c >= f.cols or r >= f.rows:
            if cell.kind in ("tent", "pet", "barnyard"):
                continue
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


class PlantOut(BaseModel):
    id: int
    code: str
    name: str
    emoji: str | None


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
    potion_recipe_ids: list[int] = []


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
    return PlantOut(id=p.id, code=p.code, name=p.name, emoji=p.emoji)


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
    return _detail(f)


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
        wanted.add((c, r))
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
    return _detail(f)


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

    cell.kind = "empty" if cell.kind == req.kind else req.kind
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


def _detail(f: Field) -> FieldDetailOut:
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
        potion_recipe_ids=[fpr.recipe_id for fpr in f.potion_recipes],
    )


@router.get("/{field_id}", response_model=FieldDetailOut)
def get_field_detail(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return _detail(_get_field_or_404(field_id, db))


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
        if recipe_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Для карточки рецепта выберите зелье")
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
            remove_upload(z.image_url)
            db.delete(z)
    db.query(FieldPotionRecipe).filter(FieldPotionRecipe.field_id == f.id).delete()
    for rid in req.recipe_ids:
        if rid in valid_ids:
            db.add(FieldPotionRecipe(field_id=f.id, recipe_id=rid))
    db.commit()
    db.refresh(f)
    return [fpr.recipe_id for fpr in f.potion_recipes]
