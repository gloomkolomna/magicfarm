from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Plant, User

router = APIRouter(prefix="/api/plants", tags=["plants"])


class PlantOut(BaseModel):
    id: int
    code: str
    name: str
    emoji: str | None
    category: str
    level: int
    norm_per_crystal: int
    bonus_text: str | None
    bonus_kind: str | None
    description: str | None
    stitch_condition: str | None
    image_young_url: str | None
    image_grown_url: str | None


def _to_out(p: Plant) -> PlantOut:
    return PlantOut(
        id=p.id, code=p.code, name=p.name, emoji=p.emoji,
        category=p.category, level=p.level, norm_per_crystal=p.norm_per_crystal,
        bonus_text=p.bonus_text, bonus_kind=p.bonus_kind, description=p.description,
        stitch_condition=p.stitch_condition,
        image_young_url=p.image_young_url, image_grown_url=p.image_grown_url,
    )


def _get_plant_or_404(plant_id: int, db: Session) -> Plant:
    p = db.query(Plant).filter(Plant.id == plant_id).first()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Растение не найдено")
    return p


@router.get("", response_model=list[PlantOut])
def list_plants(
    category: str | None = None,
    level: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Plant)
    if category is not None:
        q = q.filter(Plant.category == category)
    if level is not None:
        q = q.filter(Plant.level == level)
    rows = q.order_by(Plant.id.asc()).all()
    return [_to_out(p) for p in rows]


@router.get("/{plant_id}", response_model=PlantOut)
def get_plant(
    plant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _to_out(_get_plant_or_404(plant_id, db))
