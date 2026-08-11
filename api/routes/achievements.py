import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import Achievement, User, UserAchievement

router = APIRouter(prefix="/api/achievements", tags=["achievements"])


class AchievementOut(BaseModel):
    id: int
    code: str
    name: str
    condition_kind: str
    condition_value: int
    image_url: str | None
    earned: bool


def _ach_out(a: Achievement, user_id: int, db: Session) -> AchievementOut:
    earned = db.query(UserAchievement).filter(
        UserAchievement.user_id == user_id, UserAchievement.achievement_id == a.id
    ).first() is not None
    return AchievementOut(
        id=a.id, code=a.code, name=a.name,
        condition_kind=a.condition_kind, condition_value=a.condition_value,
        image_url=a.image_url, earned=earned,
    )


@router.get("", response_model=list[AchievementOut])
def list_achievements(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Achievement).order_by(Achievement.id.asc()).all()
    return [_ach_out(a, user.vk_id, db) for a in rows]


# ── Admin ──

admin_router = APIRouter(prefix="/api/admin/achievements", tags=["admin-achievements"])


class AchievementCreate(BaseModel):
    code: str
    name: str
    condition_kind: str
    condition_value: int = 1
    image_url: str | None = None


@admin_router.get("", response_model=list[AchievementOut])
def admin_list(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(Achievement).order_by(Achievement.id.asc()).all()
    return [_ach_out(a, 0, db) for a in rows]


@admin_router.post("", response_model=AchievementOut, status_code=status.HTTP_201_CREATED)
def admin_create(
    req: AchievementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    existing = db.query(Achievement).filter(Achievement.code == req.code).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Достижение с таким кодом уже есть")
    a = Achievement(
        code=req.code, name=req.name,
        condition_kind=req.condition_kind, condition_value=req.condition_value,
        image_url=req.image_url,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _ach_out(a, 0, db)


@admin_router.put("/{achievement_id}", response_model=AchievementOut)
def admin_update(
    achievement_id: int,
    req: AchievementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    a = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Достижение не найдено")
    a.name = req.name
    a.condition_kind = req.condition_kind
    a.condition_value = req.condition_value
    a.image_url = req.image_url
    db.commit()
    db.refresh(a)
    return _ach_out(a, 0, db)


@admin_router.delete("/{achievement_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete(
    achievement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    a = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Достижение не найдено")
    db.delete(a)
    db.commit()
    return None
