from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_location
from models import (
    ClinicPartCell, Disease, DiseaseSymptom, Field, InfirmaryZone, PatientAnimal, User,
    UserCard, UserExamineLog, UserPatientState, UserRemedy, UserRemedyCard,
)
from routes.admin_fields import _get_field_or_404
from services.achievements import check_and_award

router = APIRouter(prefix="/api/infirmary", tags=["infirmary"], dependencies=[Depends(require_location("infirmary"))])

DIAGNOSE_PENALTY = 200
EXAMINE_PENALTY = 100


def _healed_patient_ids(user_id: int, db: Session) -> set[int]:
    return {
        s.patient_id
        for s in db.query(UserPatientState).filter(
            UserPatientState.user_id == user_id,
            UserPatientState.status.in_(["treated", "released"]),
        ).all()
    }


# ── Схемы ──

class InfirmaryPatientOut(BaseModel):
    id: int
    name: str
    level: int
    animal_type_name: str | None
    animal_type_emoji: str | None
    animal_image_url: str | None
    healed: bool
    card_earned: bool


class InfirmaryLevelOut(BaseModel):
    level: int
    unlocked: bool
    patients: list[InfirmaryPatientOut]


class InfirmaryOut(BaseModel):
    levels: list[InfirmaryLevelOut]
    current: InfirmaryCurrentOut | None = None
    locations: list[InfirmaryLocationOut] = []
    memories: list[InfirmaryMemoryOut] = []


class PartCellOut(BaseModel):
    id: int
    col: int
    row: int
    part_code: str


class InfirmaryZoneOut(BaseModel):
    id: int
    zone_kind: str
    col1: int
    row1: int
    col2: int
    row2: int


class InfirmarySceneOut(BaseModel):
    stage: str
    field_id: int
    name: str
    map_url: str | None
    cols: int
    rows: int


class InfirmaryCurrentOut(BaseModel):
    id: int
    name: str
    level: int
    animal_type_name: str | None
    animal_type_emoji: str | None
    animal_image_url: str | None
    disease_name: str | None
    status: str
    current_field_id: int | None
    remedy_lab_field_id: int | None = None
    card_image_url: str | None
    penalty_due: int = 0
    scenes: list[InfirmarySceneOut]


class InfirmaryMemoryOut(BaseModel):
    patient_id: int
    name: str
    level: int
    healthy_image_url: str | None
    healed: bool


class InfirmaryLocationOut(BaseModel):
    field_id: int
    name: str
    field_kind: str
    map_url: str | None


class InfirmaryDetailOut(BaseModel):
    field_id: int
    name: str
    map_url: str | None
    cols: int
    rows: int
    stage: str | None
    patient_id: int | None
    patient_name: str | None
    patient_level: int | None
    patient_type_name: str | None
    patient_type_emoji: str | None
    patient_animal_image_url: str | None
    status: str | None
    disease_name: str | None
    remedy_name: str | None
    healed: bool
    card_earned: bool
    penalty_due: int = 0
    examined_parts: list[str] = []
    part_cells: list[PartCellOut]
    infirmary_zones: list[InfirmaryZoneOut]
    patient_scenes: list[InfirmarySceneOut] = []
    remedy_lab_field_id: int | None = None


class SymptomOut(BaseModel):
    part_code: str
    text: str


class HandbookDiseaseOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    image_url: str | None
    remedy_id: int | None
    remedy_name: str | None
    remedy_image_url: str | None
    symptoms: list[SymptomOut]


class HandbookOut(BaseModel):
    diseases: list[HandbookDiseaseOut]


class ExamineRequest(BaseModel):
    part_code: str


class ExamineOut(BaseModel):
    part_code: str
    symptoms: list[str]
    first_time: bool = True
    penalty_due: int = 0


class RecipeItemOut(BaseModel):
    ingredient_id: int | None
    ingredient_name: str | None
    plant_id: int | None
    plant_name: str | None
    qty: int


class DiagnoseOut(BaseModel):
    correct: bool
    crosses_balance: int
    penalty_due: int = 0
    remedy_card_id: int | None = None
    remedy_id: int | None = None
    remedy_name: str | None = None
    remedy_description: str | None = None
    remedy_image_url: str | None = None
    recipe_items: list[RecipeItemOut] = []


class DiagnoseRequest(BaseModel):
    disease_id: int


# ── Хаб лечебницы ──

def _patient_status(user_id: int, patient_id: int, db: Session) -> str:
    state = db.query(UserPatientState).filter(
        UserPatientState.user_id == user_id, UserPatientState.patient_id == patient_id
    ).first()
    return state.status if state is not None else "sick"


def _get_state(user_id: int, patient_id: int, db: Session) -> UserPatientState | None:
    return db.query(UserPatientState).filter(
        UserPatientState.user_id == user_id, UserPatientState.patient_id == patient_id
    ).first()


def _patient_scenes_out(p: PatientAnimal) -> list[InfirmarySceneOut]:
    scenes = []
    for stage in ("sick", "treating", "healthy"):
        s = next((x for x in p.scenes if x.clinic_stage == stage), None)
        if s is not None:
            scenes.append(InfirmarySceneOut(
                stage=stage, field_id=s.id, name=s.name, map_url=s.map_url, cols=s.cols, rows=s.rows,
            ))
    return scenes


@router.get("", response_model=InfirmaryOut)
def get_infirmary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patients = db.query(PatientAnimal).order_by(
        PatientAnimal.level.asc(), PatientAnimal.id.asc()
    ).all()
    healed = _healed_patient_ids(user.vk_id, db)
    from models import UserCard
    collection = {
        c.patient_id for c in db.query(UserCard).filter(UserCard.user_id == user.vk_id).all()
    }

    by_level: dict[int, list[PatientAnimal]] = {}
    for p in patients:
        by_level.setdefault(p.level, []).append(p)

    levels = []
    for level in (1, 2, 3):
        items = by_level.get(level, [])
        unlocked = level == 1
        if level > 1:
            prev = by_level.get(level - 1, [])
            unlocked = all(p.id in healed for p in prev) if prev else True
        levels.append(InfirmaryLevelOut(
            level=level,
            unlocked=unlocked,
            patients=[InfirmaryPatientOut(
                id=p.id, name=p.name, level=p.level,
                animal_type_name=p.animal_type.name if p.animal_type else None,
                animal_type_emoji=p.animal_type.emoji if p.animal_type else None,
                animal_image_url=p.animal_image_url,
                healed=p.id in healed,
                card_earned=p.id in collection,
            ) for p in items],
        ))

    lab = db.query(Field).filter(Field.field_kind == "remedy_lab").order_by(Field.id.asc()).first()

    current = None
    for p in patients:
        if _patient_status(user.vk_id, p.id, db) != "released":
            status_ = _patient_status(user.vk_id, p.id, db)
            scenes = _patient_scenes_out(p)
            state = _get_state(user.vk_id, p.id, db)
            current_field_id = state.current_field_id if state and state.current_field_id else None
            if current_field_id is None or not any(s.field_id == current_field_id for s in scenes):
                sc = next((s for s in scenes if s.stage == status_), scenes[0] if scenes else None)
                current_field_id = sc.field_id if sc else None
            current = InfirmaryCurrentOut(
                id=p.id, name=p.name, level=p.level,
                animal_type_name=p.animal_type.name if p.animal_type else None,
                animal_type_emoji=p.animal_type.emoji if p.animal_type else None,
                animal_image_url=p.animal_image_url,
                disease_name=p.disease.name if p.disease else None,
                status=status_,
                current_field_id=current_field_id,
                remedy_lab_field_id=lab.id if lab else None,
                card_image_url=p.card_image_url,
                penalty_due=(state.penalty_due or 0) if state else 0,
                scenes=scenes,
            )
            break

    locations = []
    if current is not None and current.current_field_id is not None:
        sc = next((s for s in current.scenes if s.field_id == current.current_field_id), None)
        if sc is not None:
            locations.append(InfirmaryLocationOut(
                field_id=sc.field_id, name="Лесная лечебница",
                field_kind="infirmary", map_url=sc.map_url,
            ))
    for f in db.query(Field).order_by(Field.id.asc()).all():
        if f.field_kind in ("meadow", "shop", "remedy_lab", "forest_bar"):
            locations.append(InfirmaryLocationOut(
                field_id=f.id, name=f.name, field_kind=f.field_kind, map_url=f.map_url,
            ))

    memories = []
    for p in patients:
        if p.id not in healed:
            continue
        healthy = next((s for s in p.scenes if s.clinic_stage == "healthy"), None)
        memories.append(InfirmaryMemoryOut(
            patient_id=p.id, name=p.name, level=p.level,
            healthy_image_url=healthy.map_url if healthy else None,
            healed=True,
        ))

    return InfirmaryOut(levels=levels, current=current, locations=locations, memories=memories)


# ── Справочник ──

@router.get("/handbook", response_model=HandbookOut)
def get_handbook(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    diseases = db.query(Disease).order_by(Disease.id.asc()).all()
    return HandbookOut(diseases=[
        HandbookDiseaseOut(
            id=d.id, code=d.code, name=d.name, description=d.description,
            image_url=d.image_url,
            remedy_id=d.remedy_id,
            remedy_name=d.remedy.name if d.remedy else None,
            remedy_image_url=d.remedy.image_url if d.remedy else None,
            symptoms=[SymptomOut(part_code=s.part_code, text=s.text) for s in d.symptoms],
        )
        for d in diseases
    ])


# ── Детализация сцены лечебницы ──

@router.get("/{field_id}", response_model=InfirmaryDetailOut)
def get_infirmary_detail(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = _get_field_or_404(field_id, db)
    if f.field_kind != "infirmary":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Это не лесная лечебница")

    patient = f.clinic_animal
    collection = {
        c.patient_id for c in db.query(UserCard).filter(UserCard.user_id == user.vk_id).all()
    }

    if patient is not None:
        state = _get_state(user.vk_id, patient.id, db)
        if state is None:
            state = UserPatientState(user_id=user.vk_id, patient_id=patient.id, status="sick")
            db.add(state)
        state.current_field_id = f.id
        db.commit()

    part_cells = db.query(ClinicPartCell).filter(
        ClinicPartCell.field_id == f.id
    ).order_by(ClinicPartCell.row.asc(), ClinicPartCell.col.asc()).all()

    patient_id = patient.id if patient else None
    status_ = _patient_status(user.vk_id, patient.id, db) if patient else None

    state = _get_state(user.vk_id, patient.id, db) if patient else None
    penalty_due = (state.penalty_due or 0) if state else 0
    examined_parts = [
        log.part_code for log in db.query(UserExamineLog).filter(
            UserExamineLog.user_id == user.vk_id, UserExamineLog.patient_id == patient.id
        ).all()
    ] if patient else []

    zones = db.query(InfirmaryZone).filter(
        InfirmaryZone.field_id == f.id
    ).order_by(InfirmaryZone.id.asc()).all()

    lab = db.query(Field).filter(Field.field_kind == "remedy_lab").order_by(Field.id.asc()).first()

    return InfirmaryDetailOut(
        field_id=f.id, name=f.name, map_url=f.map_url, cols=f.cols, rows=f.rows,
        stage=f.clinic_stage,
        patient_id=patient_id,
        patient_name=patient.name if patient else None,
        patient_level=patient.level if patient else None,
        patient_type_name=patient.animal_type.name if patient and patient.animal_type else None,
        patient_type_emoji=patient.animal_type.emoji if patient and patient.animal_type else None,
        patient_animal_image_url=patient.animal_image_url if patient else None,
        status=status_,
        disease_name=patient.disease.name if patient and patient.disease else None,
        remedy_name=(patient.disease.remedy.name if patient and patient.disease and patient.disease.remedy else None),
        healed=(status_ in ("treated", "released")) if status_ else False,
        card_earned=(patient_id in collection) if patient_id else False,
        penalty_due=penalty_due,
        examined_parts=examined_parts,
        part_cells=[PartCellOut(id=pc.id, col=pc.col, row=pc.row, part_code=pc.part_code) for pc in part_cells],
        infirmary_zones=[InfirmaryZoneOut(id=z.id, zone_kind=z.zone_kind, col1=z.col1, row1=z.row1, col2=z.col2, row2=z.row2) for z in zones],
        patient_scenes=_patient_scenes_out(patient) if patient else [],
        remedy_lab_field_id=lab.id if lab else None,
    )


# ── Осмотр части тела ──

@router.post("/patients/{patient_id}/examine", response_model=ExamineOut)
def examine_patient(
    patient_id: int,
    req: ExamineRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = db.query(PatientAnimal).filter(PatientAnimal.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден")

    part_code = req.part_code.strip()
    parts = set()
    for s in patient.scenes:
        parts |= {pc.part_code for pc in s.part_cells}
    if not part_code or part_code not in parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестная часть тела")

    state = db.query(UserPatientState).filter(
        UserPatientState.user_id == user.vk_id, UserPatientState.patient_id == patient.id
    ).first()
    if state is None:
        state = UserPatientState(user_id=user.vk_id, patient_id=patient.id, status="sick")
        db.add(state)

    log = db.query(UserExamineLog).filter(
        UserExamineLog.user_id == user.vk_id,
        UserExamineLog.patient_id == patient.id,
        UserExamineLog.part_code == part_code,
    ).first()
    first_time = log is None
    if first_time:
        db.add(UserExamineLog(user_id=user.vk_id, patient_id=patient.id, part_code=part_code))
    else:
        state.penalty_due = (state.penalty_due or 0) + EXAMINE_PENALTY
    db.commit()

    symptoms = db.query(DiseaseSymptom).filter(
        DiseaseSymptom.disease_id == patient.disease_id,
        DiseaseSymptom.part_code == part_code,
    ).all()
    return ExamineOut(
        part_code=part_code,
        symptoms=[s.text for s in symptoms],
        first_time=first_time,
        penalty_due=state.penalty_due or 0,
    )


# ── Диагноз ──

@router.post("/patients/{patient_id}/diagnose", response_model=DiagnoseOut)
def diagnose_patient(
    patient_id: int,
    req: DiagnoseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = db.query(PatientAnimal).filter(PatientAnimal.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден")

    state = db.query(UserPatientState).filter(
        UserPatientState.user_id == user.vk_id, UserPatientState.patient_id == patient.id
    ).first()
    if state is not None and state.status in ("treated", "released"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пациент уже вылечен")

    existing_card = db.query(UserRemedyCard).filter(
        UserRemedyCard.user_id == user.vk_id, UserRemedyCard.patient_id == patient.id
    ).first()
    if existing_card is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Диагноз уже поставлен")

    if ((state.penalty_due or 0) if state else 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Сначала отшейте штраф: {state.penalty_due} крестиков",
        )

    if req.disease_id != patient.disease_id:
        if state is None:
            state = UserPatientState(user_id=user.vk_id, patient_id=patient.id, status="sick")
            db.add(state)
        state.penalty_due = (state.penalty_due or 0) + DIAGNOSE_PENALTY
        db.commit()
        return DiagnoseOut(
            correct=False,
            crosses_balance=user.crosses_balance or 0,
            penalty_due=state.penalty_due or 0,
        )

    remedy = patient.disease.remedy if patient.disease else None
    if remedy is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У болезни не назначена мазь")
    card = UserRemedyCard(user_id=user.vk_id, patient_id=patient.id, remedy_id=remedy.id)
    db.add(card)
    if state is None:
        state = UserPatientState(user_id=user.vk_id, patient_id=patient.id, status="diagnosed")
        db.add(state)
    else:
        state.status = "diagnosed"
    db.commit()
    db.refresh(card)

    recipe_items = [
        RecipeItemOut(
            ingredient_id=item.ingredient_id,
            ingredient_name=item.ingredient.name if item.ingredient else None,
            plant_id=item.plant_id,
            plant_name=item.plant.name if item.plant else None,
            qty=item.qty,
        )
        for item in remedy.recipe_items
    ]
    return DiagnoseOut(
        correct=True,
        crosses_balance=user.crosses_balance or 0,
        remedy_card_id=card.id,
        remedy_id=remedy.id,
        remedy_name=remedy.name,
        remedy_description=remedy.description,
        remedy_image_url=remedy.image_url,
        recipe_items=recipe_items,
    )


# ── Дать лекарство ──

class GiveRemedyOut(BaseModel):
    patient_id: int
    patient_name: str
    status: str
    remedy_name: str | None
    otter_granted: bool = False


@router.post("/patients/{patient_id}/give-remedy", response_model=GiveRemedyOut)
def give_remedy(
    patient_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = db.query(PatientAnimal).filter(PatientAnimal.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден")

    state = db.query(UserPatientState).filter(
        UserPatientState.user_id == user.vk_id, UserPatientState.patient_id == patient.id
    ).first()
    if state is not None and state.status in ("treated", "released"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пациент уже вылечен")
    if state is None or state.status not in ("diagnosed",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сначала поставьте диагноз")

    card = db.query(UserRemedyCard).filter(
        UserRemedyCard.user_id == user.vk_id, UserRemedyCard.patient_id == patient.id
    ).first()
    if card is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сначала поставьте диагноз")

    stock = db.query(UserRemedy).filter(
        UserRemedy.user_id == user.vk_id, UserRemedy.remedy_id == card.remedy_id
    ).first()
    if stock is None or (stock.qty or 0) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Лекарства нет на складе — сварите его в Лесной аптеке",
        )

    stock.qty = (stock.qty or 0) - 1
    state.status = "treated"
    state.healed_at = datetime.datetime.utcnow()

    otter_granted = False
    name_low = (patient.name or "").lower()
    type_low = (patient.animal_type.name if patient.animal_type else "") or ""
    if "выдр" in name_low or "выдр" in type_low.lower():
        from routes.pets import grant_forest_pet_if_absent
        otter_granted = grant_forest_pet_if_absent(user.vk_id, db)

    db.commit()
    return GiveRemedyOut(
        patient_id=patient.id,
        patient_name=patient.name,
        status="treated",
        remedy_name=card.remedy.name if card.remedy else None,
        otter_granted=otter_granted,
    )


# ── Выпустить на волю ──

class ReleaseOut(BaseModel):
    patient_id: int
    patient_name: str
    card_earned: bool


@router.post("/patients/{patient_id}/release", response_model=ReleaseOut)
def release_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = db.query(PatientAnimal).filter(PatientAnimal.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден")

    state = db.query(UserPatientState).filter(
        UserPatientState.user_id == user.vk_id, UserPatientState.patient_id == patient.id
    ).first()
    if state is None or state.status not in ("treated", "released"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пациент ещё не вылечен — сначала приготовьте лекарство",
        )
    if state.status == "released":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пациент уже выпущен")

    existing_card = db.query(UserCard).filter(
        UserCard.user_id == user.vk_id, UserCard.patient_id == patient.id
    ).first()
    card_earned = existing_card is None
    if existing_card is None:
        db.add(UserCard(user_id=user.vk_id, patient_id=patient.id))
    state.status = "released"
    db.commit()

    check_and_award(user.vk_id, "healed_count", db)
    check_and_award(user.vk_id, "infirmary_level_complete", db)
    check_and_award(user.vk_id, "full_collection", db)

    return ReleaseOut(patient_id=patient.id, patient_name=patient.name, card_earned=card_earned)
