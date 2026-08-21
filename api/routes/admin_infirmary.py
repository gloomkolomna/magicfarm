from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import require_role
from models import (
    PATIENT_LEVELS, ClinicAnimalType, Disease, DiseaseSymptom, Field, Ingredient, PatientAnimal,
    Plant, Remedy, RemedyRecipeItem, Setting, User,
)
from routes.admin_catalog import _auto_code, _unique_code
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/admin", tags=["admin-infirmary"])

INFIRMARY_BG_KEY = "infirmary_background_url"

INFIRMARY_STAGE_LABELS = {
    "sick": "Больное",
    "treating": "На лечении",
    "healthy": "Здоровое",
}

INFIRMARY_STAGES = ("sick", "treating", "healthy")


def _scene_name(animal_name: str, stage: str) -> str:
    return f"{animal_name} — {INFIRMARY_STAGE_LABELS[stage].lower()}"


# ── Схемы вывода ──

class RemedyItemOut(BaseModel):
    ingredient_id: int | None
    ingredient_name: str | None
    plant_id: int | None
    plant_name: str | None
    qty: int


class RemedyOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    image_url: str | None
    recipe_items: list[RemedyItemOut]


class SymptomOut(BaseModel):
    part_code: str
    text: str


class DiseaseOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    image_url: str | None
    remedy_id: int | None
    remedy_name: str | None
    symptoms: list[SymptomOut]


class AnimalTypeOut(BaseModel):
    id: int
    code: str
    name: str
    emoji: str | None
    sort_order: int


class PatientSceneOut(BaseModel):
    field_id: int
    stage: str
    name: str
    map_url: str | None


class PatientOut(BaseModel):
    id: int
    code: str
    name: str
    level: int
    card_image_url: str | None
    animal_image_url: str | None
    animal_type_id: int | None
    animal_type_name: str | None
    animal_type_emoji: str | None
    disease_id: int | None
    disease_name: str | None
    scenes: list[PatientSceneOut]


def _remedy_item_out(item: RemedyRecipeItem) -> RemedyItemOut:
    return RemedyItemOut(
        ingredient_id=item.ingredient_id,
        ingredient_name=item.ingredient.name if item.ingredient else None,
        plant_id=item.plant_id,
        plant_name=item.plant.name if item.plant else None,
        qty=item.qty,
    )


def _remedy_out(r: Remedy) -> RemedyOut:
    return RemedyOut(
        id=r.id, code=r.code, name=r.name, description=r.description,
        image_url=r.image_url,
        recipe_items=[_remedy_item_out(i) for i in r.recipe_items],
    )


def _symptom_out(s: DiseaseSymptom) -> SymptomOut:
    return SymptomOut(part_code=s.part_code, text=s.text)


def _disease_out(d: Disease) -> DiseaseOut:
    return DiseaseOut(
        id=d.id, code=d.code, name=d.name, description=d.description,
        image_url=d.image_url,
        remedy_id=d.remedy_id,
        remedy_name=d.remedy.name if d.remedy else None,
        symptoms=[_symptom_out(s) for s in d.symptoms],
    )


def _patient_scenes(p: PatientAnimal) -> list[PatientSceneOut]:
    return [
        PatientSceneOut(field_id=s.id, stage=s.clinic_stage, name=s.name, map_url=s.map_url)
        for s in sorted(p.scenes, key=lambda s: (INFIRMARY_STAGES.index(s.clinic_stage) if s.clinic_stage in INFIRMARY_STAGES else 99))
    ]


def _patient_out(p: PatientAnimal) -> PatientOut:
    return PatientOut(
        id=p.id, code=p.code, name=p.name, level=p.level,
        card_image_url=p.card_image_url, animal_image_url=p.animal_image_url,
        animal_type_id=p.animal_type_id,
        animal_type_name=p.animal_type.name if p.animal_type else None,
        animal_type_emoji=p.animal_type.emoji if p.animal_type else None,
        disease_id=p.disease_id,
        disease_name=p.disease.name if p.disease else None,
        scenes=_patient_scenes(p),
    )


# ── Мази ──

class RecipeItemIn(BaseModel):
    ingredient_id: int | None = None
    plant_id: int | None = None
    qty: int = 1


class RemedyCreate(BaseModel):
    name: str
    description: str | None = None
    recipe_items: list[RecipeItemIn] = []


class RemedyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    recipe_items: list[RecipeItemIn] | None = None


def _set_recipe_items(remedy_id: int, items: list[RecipeItemIn], db: Session) -> None:
    db.query(RemedyRecipeItem).filter(RemedyRecipeItem.remedy_id == remedy_id).delete()
    for item in items:
        if item.qty < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Количество ингредиента должно быть не меньше 1")
        if (item.ingredient_id is None) == (item.plant_id is None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите ровно один источник: ингредиент ИЛИ растение",
            )
        if item.ingredient_id is not None and db.query(Ingredient).filter(Ingredient.id == item.ingredient_id).first() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ингредиент не найден")
        if item.plant_id is not None and db.query(Plant).filter(Plant.id == item.plant_id).first() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Растение не найдено")
        db.add(RemedyRecipeItem(
            remedy_id=remedy_id, ingredient_id=item.ingredient_id, plant_id=item.plant_id, qty=item.qty,
        ))


@router.get("/remedies", response_model=list[RemedyOut])
def list_remedies(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(Remedy).order_by(Remedy.id.asc()).all()
    return [_remedy_out(r) for r in rows]


@router.post("/remedies", response_model=RemedyOut, status_code=status.HTTP_201_CREATED)
def create_remedy(
    req: RemedyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    code = _unique_code(_auto_code(req.name, "remedy"), Remedy, db)
    r = Remedy(code=code, name=req.name.strip(), description=req.description)
    db.add(r)
    db.flush()
    _set_recipe_items(r.id, req.recipe_items, db)
    db.commit()
    db.refresh(r)
    return _remedy_out(r)


@router.put("/remedies/{remedy_id}", response_model=RemedyOut)
def update_remedy(
    remedy_id: int,
    req: RemedyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(Remedy).filter(Remedy.id == remedy_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Мазь не найдена")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        r.name = req.name.strip()
    if req.description is not None:
        r.description = req.description
    if req.recipe_items is not None:
        _set_recipe_items(r.id, req.recipe_items, db)
    db.commit()
    db.refresh(r)
    return _remedy_out(r)


@router.delete("/remedies/{remedy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_remedy(
    remedy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(Remedy).filter(Remedy.id == remedy_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Мазь не найдена")
    remove_upload(r.image_url)
    db.delete(r)
    db.commit()
    return None


@router.put("/remedies/{remedy_id}/image", response_model=RemedyOut)
def upload_remedy_image(
    remedy_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    r = db.query(Remedy).filter(Remedy.id == remedy_id).first()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Мазь не найдена")
    remove_upload(r.image_url)
    r.image_url = save_upload(image, f"remedy_{remedy_id}", max_size=400)
    db.commit()
    db.refresh(r)
    return _remedy_out(r)


# ── Болезни ──

class SymptomIn(BaseModel):
    part_code: str
    text: str


class DiseaseCreate(BaseModel):
    name: str
    description: str | None = None
    remedy_id: int | None = None
    symptoms: list[SymptomIn] = []


class DiseaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    remedy_id: int | None = None
    symptoms: list[SymptomIn] | None = None


def _set_symptoms(disease_id: int, symptoms: list[SymptomIn], db: Session) -> None:
    db.query(DiseaseSymptom).filter(DiseaseSymptom.disease_id == disease_id).delete()
    for s in symptoms:
        part_code = s.part_code.strip()
        text = s.text.strip()
        if not part_code or not text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Часть тела и симптом обязательны")
        db.add(DiseaseSymptom(disease_id=disease_id, part_code=part_code, text=text))


def _validate_remedy(remedy_id: int | None, db: Session) -> None:
    if remedy_id is not None and db.query(Remedy).filter(Remedy.id == remedy_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Мазь не найдена")


@router.get("/diseases", response_model=list[DiseaseOut])
def list_diseases(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(Disease).order_by(Disease.id.asc()).all()
    return [_disease_out(d) for d in rows]


@router.post("/diseases", response_model=DiseaseOut, status_code=status.HTTP_201_CREATED)
def create_disease(
    req: DiseaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    _validate_remedy(req.remedy_id, db)
    code = _unique_code(_auto_code(req.name, "disease"), Disease, db)
    d = Disease(code=code, name=req.name.strip(), description=req.description, remedy_id=req.remedy_id)
    db.add(d)
    db.flush()
    _set_symptoms(d.id, req.symptoms, db)
    db.commit()
    db.refresh(d)
    return _disease_out(d)


@router.put("/diseases/{disease_id}", response_model=DiseaseOut)
def update_disease(
    disease_id: int,
    req: DiseaseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    d = db.query(Disease).filter(Disease.id == disease_id).first()
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Болезнь не найдена")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        d.name = req.name.strip()
    if req.description is not None:
        d.description = req.description
    if req.remedy_id is not None:
        _validate_remedy(req.remedy_id, db)
        d.remedy_id = req.remedy_id
    if req.symptoms is not None:
        _set_symptoms(d.id, req.symptoms, db)
    db.commit()
    db.refresh(d)
    return _disease_out(d)


@router.put("/diseases/{disease_id}/image", response_model=DiseaseOut)
def upload_disease_image(
    disease_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    d = db.query(Disease).filter(Disease.id == disease_id).first()
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Болезнь не найдена")
    remove_upload(d.image_url)
    d.image_url = save_upload(image, f"disease_{disease_id}", max_size=600)
    db.commit()
    db.refresh(d)
    return _disease_out(d)


@router.delete("/diseases/{disease_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_disease(
    disease_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    d = db.query(Disease).filter(Disease.id == disease_id).first()
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Болезнь не найдена")
    remove_upload(d.image_url)
    db.delete(d)
    db.commit()
    return None


# ── Типы животных лечебницы ──

class AnimalTypeCreate(BaseModel):
    name: str
    emoji: str | None = None


class AnimalTypeUpdate(BaseModel):
    name: str | None = None
    emoji: str | None = None


def _validate_animal_type(type_id: int | None, db: Session) -> None:
    if type_id is not None and db.query(ClinicAnimalType).filter(ClinicAnimalType.id == type_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Тип животного не найден")


@router.get("/clinic-animal-types", response_model=list[AnimalTypeOut])
def list_animal_types(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(ClinicAnimalType).order_by(ClinicAnimalType.sort_order.asc(), ClinicAnimalType.id.asc()).all()
    return [
        AnimalTypeOut(id=t.id, code=t.code, name=t.name, emoji=t.emoji, sort_order=t.sort_order)
        for t in rows
    ]


@router.post("/clinic-animal-types", response_model=AnimalTypeOut, status_code=status.HTTP_201_CREATED)
def create_animal_type(
    req: AnimalTypeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    code = _unique_code(_auto_code(req.name, "animal_type"), ClinicAnimalType, db)
    t = ClinicAnimalType(code=code, name=req.name.strip(), emoji=req.emoji)
    db.add(t)
    db.commit()
    db.refresh(t)
    return AnimalTypeOut(id=t.id, code=t.code, name=t.name, emoji=t.emoji, sort_order=t.sort_order)


@router.put("/clinic-animal-types/{type_id}", response_model=AnimalTypeOut)
def update_animal_type(
    type_id: int,
    req: AnimalTypeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    t = db.query(ClinicAnimalType).filter(ClinicAnimalType.id == type_id).first()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тип животного не найден")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        t.name = req.name.strip()
    if req.emoji is not None:
        t.emoji = req.emoji
    db.commit()
    db.refresh(t)
    return AnimalTypeOut(id=t.id, code=t.code, name=t.name, emoji=t.emoji, sort_order=t.sort_order)


@router.delete("/clinic-animal-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_animal_type(
    type_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    t = db.query(ClinicAnimalType).filter(ClinicAnimalType.id == type_id).first()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тип животного не найден")
    db.delete(t)
    db.commit()
    return None


# ── Животные лечебницы ──

class PatientCreate(BaseModel):
    name: str
    level: int = 1
    disease_id: int | None = None
    animal_type_id: int | None = None


class PatientUpdate(BaseModel):
    name: str | None = None
    level: int | None = None
    disease_id: int | None = None
    animal_type_id: int | None = None


def _create_patient_scenes(p: PatientAnimal, db: Session) -> None:
    for stage in INFIRMARY_STAGES:
        code = _unique_code(_auto_code(_scene_name(p.name, stage), "scene"), Field, db)
        f = Field(
            code=code, name=_scene_name(p.name, stage), cols=3, rows=2,
            field_kind="infirmary", clinic_animal_id=p.id, clinic_stage=stage,
        )
        db.add(f)


@router.get("/patients", response_model=list[PatientOut])
def list_patients(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(PatientAnimal).order_by(PatientAnimal.level.asc(), PatientAnimal.id.asc()).all()
    return [_patient_out(p) for p in rows]


@router.post("/patients", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    req: PatientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if not req.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
    if req.level not in PATIENT_LEVELS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Уровень должен быть одним из: {', '.join(map(str, PATIENT_LEVELS))}")
    if req.disease_id is not None and db.query(Disease).filter(Disease.id == req.disease_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Болезнь не найдена")
    _validate_animal_type(req.animal_type_id, db)
    code = _unique_code(_auto_code(req.name, "patient"), PatientAnimal, db)
    p = PatientAnimal(
        code=code, name=req.name.strip(), level=req.level,
        disease_id=req.disease_id, animal_type_id=req.animal_type_id,
    )
    db.add(p)
    db.flush()
    _create_patient_scenes(p, db)
    db.commit()
    db.refresh(p)
    return _patient_out(p)


@router.put("/patients/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int,
    req: PatientUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(PatientAnimal).filter(PatientAnimal.id == patient_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название обязательно")
        p.name = req.name.strip()
    if req.level is not None:
        if req.level not in PATIENT_LEVELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Уровень должен быть одним из: {', '.join(map(str, PATIENT_LEVELS))}")
        p.level = req.level
    if req.disease_id is not None:
        if db.query(Disease).filter(Disease.id == req.disease_id).first() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Болезнь не найдена")
        p.disease_id = req.disease_id
    if req.animal_type_id is not None:
        _validate_animal_type(req.animal_type_id, db)
        p.animal_type_id = req.animal_type_id
    for s in p.scenes:
        s.name = _scene_name(p.name, s.clinic_stage)
    db.commit()
    db.refresh(p)
    return _patient_out(p)


@router.delete("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(PatientAnimal).filter(PatientAnimal.id == patient_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    remove_upload(p.card_image_url)
    remove_upload(p.animal_image_url)
    for s in p.scenes:
        remove_upload(s.map_url)
    db.delete(p)
    db.commit()
    return None


@router.put("/patients/{patient_id}/card-image", response_model=PatientOut)
def upload_patient_card_image(
    patient_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(PatientAnimal).filter(PatientAnimal.id == patient_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    remove_upload(p.card_image_url)
    p.card_image_url = save_upload(image, f"patient_card_{patient_id}", max_size=1200)
    db.commit()
    db.refresh(p)
    return _patient_out(p)


@router.put("/patients/{patient_id}/animal-image", response_model=PatientOut)
def upload_patient_animal_image(
    patient_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.query(PatientAnimal).filter(PatientAnimal.id == patient_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    remove_upload(p.animal_image_url)
    p.animal_image_url = save_upload(image, f"patient_animal_{patient_id}", max_size=400)
    db.commit()
    db.refresh(p)
    return _patient_out(p)


@router.put("/infirmary-background")
def upload_infirmary_background(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    url = save_upload(image, "infirmary_bg", max_size=1400)
    s = db.query(Setting).filter(Setting.key == INFIRMARY_BG_KEY).first()
    if s is None:
        s = Setting(key=INFIRMARY_BG_KEY, value=url)
        db.add(s)
    else:
        remove_upload(s.value)
        s.value = url
    db.commit()
    return {"url": url}
