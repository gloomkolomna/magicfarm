from __future__ import annotations
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import get_db
from deps import require_role
from models import Animal, CrystalCard, Pet, Plant, Product, ProductionTemplate, User
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/admin/catalog", tags=["admin-catalog"])
public_router = APIRouter(prefix="/api/crystal-cards", tags=["crystal-cards"])

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    " ": "_", "-": "_",
}


def _auto_code(name: str, prefix: str = "") -> str:
    raw = name.strip().lower()
    result = "".join(_TRANSLIT.get(ch, ch) for ch in raw if ch.isalpha() or ch in (" ", "-") or ch.isdigit())
    result = re.sub(r"[^a-z0-9_]+", "_", result).strip("_")
    if not result or not result[0].isalpha():
        result = (prefix or "item") + ("_" + result if result else "")
    return result


def _unique_code(base: str, model_cls, db: Session) -> str:
    code = base
    n = 2
    while db.query(model_cls).filter(model_cls.code == code).first() is not None:
        code = f"{base}_{n}"
        n += 1
    return code


# ── Pydantic schemas ──

class PlantCreate(BaseModel):
    name: str
    emoji: str | None = None
    category: str = "garden"
    level: int = 1
    description: str | None = None
    stitch_condition: str | None = None


class PlantUpdate(BaseModel):
    name: str | None = None
    emoji: str | None = None
    category: str | None = None
    level: int | None = None
    description: str | None = None
    stitch_condition: str | None = None


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


class AnimalCreate(BaseModel):
    name: str
    emoji: str | None = None
    product_name: str | None = None
    sort_order: int = 0


class AnimalUpdate(BaseModel):
    name: str | None = None
    emoji: str | None = None
    product_name: str | None = None
    sort_order: int | None = None


class AnimalOut(BaseModel):
    id: int
    code: str
    name: str
    emoji: str | None
    product_name: str | None
    sort_order: int
    image_url: str | None
    image_empty_pen_url: str | None
    image_pen_url: str | None
    image_harvested_url: str | None


BONUS_KINDS: dict[str, str] = {
    "harvest_orchard": "+1 к урожаю сада",
    "harvest_plot": "+1 к урожаю грядки",
    "order_coins": "+5 монет к заказу",
    "craft_bonus": "+1 товар при крафте",
    "animal_product": "+1 продукция животного",
}


class PetCreate(BaseModel):
    name: str
    emoji: str | None = None
    bonus_kind: str | None = None
    bonus_description: str | None = None


class PetUpdate(BaseModel):
    name: str | None = None
    emoji: str | None = None
    bonus_kind: str | None = None
    bonus_description: str | None = None


class PetOut(BaseModel):
    id: int
    code: str
    name: str
    emoji: str | None
    bonus_kind: str | None
    bonus_description: str | None
    image_url: str | None


# ── Helpers ──

def _plant_out(p: Plant) -> PlantOut:
    return PlantOut(
        id=p.id, code=p.code, name=p.name, emoji=p.emoji,
        category=p.category, level=p.level, norm_per_crystal=p.norm_per_crystal,
        description=p.description, stitch_condition=p.stitch_condition,
        image_url=p.image_url, image_young_url=p.image_young_url, image_grown_url=p.image_grown_url,
        image_harvested_url=p.image_harvested_url,
    )


def _animal_out(a: Animal) -> AnimalOut:
    return AnimalOut(
        id=a.id, code=a.code, name=a.name, emoji=a.emoji,
        product_name=a.product_name, sort_order=a.sort_order,
        image_url=a.image_url,
        image_empty_pen_url=a.image_empty_pen_url,
        image_pen_url=a.image_pen_url,
        image_harvested_url=a.image_harvested_url,
    )


def _pet_out(p: Pet) -> PetOut:
    return PetOut(
        id=p.id, code=p.code, name=p.name, emoji=p.emoji,
        bonus_kind=p.bonus_kind,
        bonus_description=p.bonus_description,
        image_url=p.image_url,
    )


def _validate_code(code: str) -> str:
    code = re.sub(r"[^a-z0-9_]+", "_", code.strip().lower()).strip("_")
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Код обязателен")
    if not code[0].isalpha():
        code = "c_" + code
    return code


def _make_plant_code(name: str, db: Session) -> str:
    """Генерирует уникальный code растения. Из кириллицы делаем plant_N."""
    base = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not base or not base[0].isalpha():
        base = "plant"
    code = base
    n = 2
    while db.query(Plant).filter(Plant.code == code).first() is not None:
        code = f"{base}_{n}"
        n += 1
    return code


# ── Plants CRUD ──

@router.get("/plants", response_model=list[PlantOut])
def list_plants(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [_plant_out(p) for p in db.query(Plant).order_by(Plant.id.asc()).all()]


@router.post("/plants", response_model=PlantOut, status_code=status.HTTP_201_CREATED)
def create_plant(
    req: PlantCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    code = _unique_code(_auto_code(req.name, "plant"), Plant, db)
    p = Plant(
        code=code, name=req.name.strip(), emoji=req.emoji, category=req.category,
        level=req.level, norm_per_crystal=100,
        description=req.description, stitch_condition=req.stitch_condition,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _plant_out(p)


@router.put("/plants/{plant_id}", response_model=PlantOut)
def update_plant(
    plant_id: int,
    req: PlantUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Plant).filter(Plant.id == plant_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        p.name = req.name.strip()
    if req.emoji is not None:
        p.emoji = req.emoji
    if req.category is not None:
        p.category = req.category
    if req.level is not None:
        p.level = req.level
    if req.description is not None:
        p.description = req.description
    if req.stitch_condition is not None:
        p.stitch_condition = req.stitch_condition
    db.commit()
    db.refresh(p)
    return _plant_out(p)


@router.delete("/plants/{plant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plant(
    plant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Plant).filter(Plant.id == plant_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")
    db.delete(p)
    db.commit()
    return None


# ── Animals CRUD ──

@router.get("/animals", response_model=list[AnimalOut])
def list_animals(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [_animal_out(a) for a in db.query(Animal).order_by(Animal.sort_order.asc(), Animal.id.asc()).all()]


@router.post("/animals", response_model=AnimalOut, status_code=status.HTTP_201_CREATED)
def create_animal(
    req: AnimalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    code = _unique_code(_auto_code(req.name, "animal"), Animal, db)
    a = Animal(code=code, name=req.name.strip(), emoji=req.emoji, product_name=req.product_name, sort_order=req.sort_order)
    db.add(a)
    db.commit()
    db.refresh(a)
    return _animal_out(a)


@router.put("/animals/{animal_id}", response_model=AnimalOut)
def update_animal(
    animal_id: int,
    req: AnimalUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    a = db.query(Animal).filter(Animal.id == animal_id).first()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Животное не найдено")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        a.name = req.name.strip()
    if req.emoji is not None:
        a.emoji = req.emoji
    if req.product_name is not None:
        a.product_name = req.product_name
    if req.sort_order is not None:
        a.sort_order = req.sort_order
    db.commit()
    db.refresh(a)
    return _animal_out(a)


@router.delete("/animals/{animal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_animal(
    animal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    a = db.query(Animal).filter(Animal.id == animal_id).first()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Животное не найдено")
    db.delete(a)
    db.commit()
    return None


# ── Pets CRUD ──

@router.get("/pets", response_model=list[PetOut])
def list_pets(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [_pet_out(p) for p in db.query(Pet).order_by(Pet.id.asc()).all()]


@router.post("/pets", response_model=PetOut, status_code=status.HTTP_201_CREATED)
def create_pet(
    req: PetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    bonus_kind = req.bonus_kind.strip() if req.bonus_kind else None
    if bonus_kind is not None and bonus_kind not in BONUS_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Недопустимый вид бонуса: {bonus_kind}")
    code = _unique_code(_auto_code(req.name, "pet"), Pet, db)
    p = Pet(code=code, name=req.name.strip(), emoji=req.emoji, bonus_kind=bonus_kind, bonus_description=req.bonus_description)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _pet_out(p)


@router.put("/pets/{pet_id}", response_model=PetOut)
def update_pet(
    pet_id: int,
    req: PetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Pet).filter(Pet.id == pet_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Питомец не найден")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        p.name = req.name.strip()
    if req.emoji is not None:
        p.emoji = req.emoji
    if req.bonus_kind is not None:
        bonus_kind = req.bonus_kind.strip() if req.bonus_kind else None
        if bonus_kind is not None and bonus_kind not in BONUS_KINDS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Недопустимый вид бонуса: {bonus_kind}")
        p.bonus_kind = bonus_kind
    if req.bonus_description is not None:
        p.bonus_description = req.bonus_description
    db.commit()
    db.refresh(p)
    return _pet_out(p)


@router.delete("/pets/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pet(
    pet_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Pet).filter(Pet.id == pet_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Питомец не найден")
    db.delete(p)
    db.commit()
    return None


# ── Products CRUD ──

class ProductCreate(BaseModel):
    name: str
    emoji: str | None = None
    plant_id: int | None = None
    animal_id: int | None = None
    pet_id: int | None = None
    stars: int = 1
    production_kind: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    emoji: str | None = None
    plant_id: int | None = None
    animal_id: int | None = None
    pet_id: int | None = None
    stars: int | None = None
    production_kind: str | None = None


class ProductOut(BaseModel):
    id: int
    code: str
    name: str
    emoji: str | None
    plant_id: int | None
    animal_id: int | None
    pet_id: int | None
    stars: int
    production_kind: str | None
    image_url: str | None


def _product_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id, code=p.code, name=p.name, emoji=p.emoji,
        plant_id=p.plant_id, animal_id=p.animal_id, pet_id=p.pet_id,
        stars=p.stars, production_kind=p.production_kind,
        image_url=p.image_url,
    )


def _validate_product_source(plant_id: int | None, animal_id: int | None, pet_id: int | None, db: Session) -> None:
    if animal_id is not None and db.query(Animal).filter(Animal.id == animal_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Животное не найдено")
    if pet_id is not None and db.query(Pet).filter(Pet.id == pet_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Питомец не найден")
    if plant_id is not None and db.query(Plant).filter(Plant.id == plant_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")


@router.get("/products", response_model=list[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [_product_out(p) for p in db.query(Product).order_by(Product.id.asc()).all()]


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    req: ProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    _validate_product_source(req.plant_id, req.animal_id, req.pet_id, db)
    code = _unique_code(_auto_code(req.name, "product"), Product, db)
    if req.plant_id is not None:
        existing = db.query(Product).filter(Product.plant_id == req.plant_id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"У растения уже есть товар «{existing.name}»")
    p = Product(
        code=code, name=req.name.strip(), emoji=req.emoji,
        plant_id=req.plant_id, animal_id=req.animal_id, pet_id=req.pet_id,
        stars=req.stars, production_kind=req.production_kind,
    )
    db.add(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="У этого растения уже есть товар")
    db.refresh(p)
    return _product_out(p)


@router.put("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    req: ProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Product).filter(Product.id == product_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        p.name = req.name.strip()
    if req.emoji is not None:
        p.emoji = req.emoji
    if req.plant_id is not None:
        existing = db.query(Product).filter(Product.plant_id == req.plant_id, Product.id != product_id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"У растения уже есть товар «{existing.name}»")
        _validate_product_source(req.plant_id, None, None, db)
        p.plant_id = req.plant_id
    if req.animal_id is not None:
        _validate_product_source(None, req.animal_id, None, db)
        p.animal_id = req.animal_id
    if req.pet_id is not None:
        _validate_product_source(None, None, req.pet_id, db)
        p.pet_id = req.pet_id
    if req.stars is not None:
        p.stars = req.stars
    if req.production_kind is not None:
        p.production_kind = req.production_kind
    db.commit()
    db.refresh(p)
    return _product_out(p)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Product).filter(Product.id == product_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    db.delete(p)
    db.commit()
    return None


# ── Production Templates CRUD ──

class ProductionTemplateCreate(BaseModel):
    code: str | None = None
    name: str
    emoji: str | None = None
    required: int = 500
    cards_to_draw: int = 3
    surcharge: int = 30


class ProductionTemplateUpdate(BaseModel):
    name: str | None = None
    emoji: str | None = None
    required: int | None = None
    cards_to_draw: int | None = None
    surcharge: int | None = None


class ProductionTemplateOut(BaseModel):
    id: int
    code: str
    name: str
    emoji: str | None
    required: int
    cards_to_draw: int
    surcharge: int
    image_url: str | None


def _pt_out(pt: ProductionTemplate) -> ProductionTemplateOut:
    return ProductionTemplateOut(
        id=pt.id, code=pt.code, name=pt.name, emoji=pt.emoji,
        required=pt.required,
        cards_to_draw=pt.cards_to_draw,
        surcharge=pt.surcharge,
        image_url=pt.image_url,
    )


@router.get("/production-templates", response_model=list[ProductionTemplateOut])
def list_production_templates(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [_pt_out(pt) for pt in db.query(ProductionTemplate).order_by(ProductionTemplate.id.asc()).all()]


@router.post("/production-templates", response_model=ProductionTemplateOut, status_code=status.HTTP_201_CREATED)
def create_production_template(
    req: ProductionTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if req.code and req.code.strip():
        code = _validate_code(req.code)
        if db.query(ProductionTemplate).filter(ProductionTemplate.code == code).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Производство с кодом '{code}' уже есть")
    else:
        code = _unique_code(_auto_code(req.name, "prod"), ProductionTemplate, db)
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    pt = ProductionTemplate(
        code=code, name=req.name.strip(), emoji=req.emoji,
        required=req.required, cards_to_draw=req.cards_to_draw, surcharge=req.surcharge,
    )
    db.add(pt)
    db.commit()
    db.refresh(pt)
    return _pt_out(pt)


@router.put("/production-templates/{pt_id}", response_model=ProductionTemplateOut)
def update_production_template(
    pt_id: int,
    req: ProductionTemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    pt = db.query(ProductionTemplate).filter(ProductionTemplate.id == pt_id).first()
    if pt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Производство не найдено")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        pt.name = req.name.strip()
    if req.emoji is not None:
        pt.emoji = req.emoji
    if req.required is not None:
        pt.required = req.required
    if req.cards_to_draw is not None:
        pt.cards_to_draw = req.cards_to_draw
    if req.surcharge is not None:
        pt.surcharge = req.surcharge
    db.commit()
    db.refresh(pt)
    return _pt_out(pt)


@router.delete("/production-templates/{pt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_production_template(
    pt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    pt = db.query(ProductionTemplate).filter(ProductionTemplate.id == pt_id).first()
    if pt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Производство не найдено")
    db.delete(pt)
    db.commit()
    return None


# ── Image upload ──

@router.put("/plants/{plant_id}/image", response_model=PlantOut)
def upload_plant_image(
    plant_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Plant).filter(Plant.id == plant_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")
    remove_upload(p.image_url)
    p.image_url = save_upload(image, f"plant_{plant_id}", max_size=400)
    db.commit()
    db.refresh(p)
    return _plant_out(p)


@router.put("/plants/{plant_id}/image-young", response_model=PlantOut)
def upload_plant_image_young(
    plant_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Plant).filter(Plant.id == plant_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")
    remove_upload(p.image_young_url)
    p.image_young_url = save_upload(image, f"plant_{plant_id}_young", max_size=400)
    db.commit()
    db.refresh(p)
    return _plant_out(p)


@router.put("/plants/{plant_id}/image-grown", response_model=PlantOut)
def upload_plant_image_grown(
    plant_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Plant).filter(Plant.id == plant_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")
    remove_upload(p.image_grown_url)
    p.image_grown_url = save_upload(image, f"plant_{plant_id}_grown", max_size=400)
    db.commit()
    db.refresh(p)
    return _plant_out(p)


@router.put("/plants/{plant_id}/image-harvested", response_model=PlantOut)
def upload_plant_image_harvested(
    plant_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Plant).filter(Plant.id == plant_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")
    remove_upload(p.image_harvested_url)
    p.image_harvested_url = save_upload(image, f"plant_{plant_id}_harvested", max_size=400)
    db.commit()
    db.refresh(p)
    return _plant_out(p)


@router.put("/animals/{animal_id}/image", response_model=AnimalOut)
def upload_animal_image(
    animal_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    a = db.query(Animal).filter(Animal.id == animal_id).first()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Животное не найдено")
    remove_upload(a.image_url)
    a.image_url = save_upload(image, f"animal_{animal_id}", max_size=400)
    db.commit()
    db.refresh(a)
    return _animal_out(a)


@router.put("/animals/{animal_id}/image-empty-pen", response_model=AnimalOut)
def upload_animal_empty_pen_image(
    animal_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    a = db.query(Animal).filter(Animal.id == animal_id).first()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Животное не найдено")
    remove_upload(a.image_empty_pen_url)
    a.image_empty_pen_url = save_upload(image, f"animal_pen_empty_{animal_id}", max_size=400)
    db.commit()
    db.refresh(a)
    return _animal_out(a)


@router.put("/animals/{animal_id}/image-pen", response_model=AnimalOut)
def upload_animal_pen_image(
    animal_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    a = db.query(Animal).filter(Animal.id == animal_id).first()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Животное не найдено")
    remove_upload(a.image_pen_url)
    a.image_pen_url = save_upload(image, f"animal_pen_{animal_id}", max_size=400)
    db.commit()
    db.refresh(a)
    return _animal_out(a)


@router.put("/animals/{animal_id}/image-harvested", response_model=AnimalOut)
def upload_animal_image_harvested(
    animal_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    a = db.query(Animal).filter(Animal.id == animal_id).first()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Животное не найдено")
    remove_upload(a.image_harvested_url)
    a.image_harvested_url = save_upload(image, f"animal_harvested_{animal_id}", max_size=400)
    db.commit()
    db.refresh(a)
    return _animal_out(a)


@router.put("/pets/{pet_id}/image", response_model=PetOut)
def upload_pet_image(
    pet_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Pet).filter(Pet.id == pet_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Питомец не найден")
    remove_upload(p.image_url)
    p.image_url = save_upload(image, f"pet_{pet_id}", max_size=400)
    db.commit()
    db.refresh(p)
    return _pet_out(p)


@router.put("/production-templates/{pt_id}/image", response_model=ProductionTemplateOut)
def upload_production_template_image(
    pt_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    pt = db.query(ProductionTemplate).filter(ProductionTemplate.id == pt_id).first()
    if pt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Производство не найдено")
    remove_upload(pt.image_url)
    pt.image_url = save_upload(image, f"prod_{pt_id}", max_size=400)
    db.commit()
    db.refresh(pt)
    return _pt_out(pt)


@router.put("/products/{product_id}/image", response_model=ProductOut)
def upload_product_image(
    product_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(Product).filter(Product.id == product_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    remove_upload(p.image_url)
    p.image_url = save_upload(image, f"product_{product_id}", max_size=400)
    db.commit()
    db.refresh(p)
    return _product_out(p)


class CrystalCardOut(BaseModel):
    id: int
    color: str
    value: int
    is_treasure: bool
    image_url: str | None


def _card_out(c: CrystalCard) -> CrystalCardOut:
    return CrystalCardOut(id=c.id, color=c.color, value=c.value, is_treasure=c.is_treasure, image_url=c.image_url)


@router.get("/crystal-cards", response_model=list[CrystalCardOut])
def list_crystal_cards(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [_card_out(c) for c in db.query(CrystalCard).order_by(CrystalCard.id.asc()).all()]


@router.put("/crystal-cards/{card_id}/image", response_model=CrystalCardOut)
def upload_crystal_card_image(
    card_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    card = db.query(CrystalCard).filter(CrystalCard.id == card_id).first()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Карта не найдена")
    remove_upload(card.image_url)
    card.image_url = save_upload(image, f"crystal_card_{card_id}", max_size=400)
    db.commit()
    db.refresh(card)
    return _card_out(card)


@public_router.get("", response_model=list[CrystalCardOut])
def list_public_crystal_cards(
    db: Session = Depends(get_db),
):
    return [_card_out(c) for c in db.query(CrystalCard).order_by(CrystalCard.id.asc()).all()]
