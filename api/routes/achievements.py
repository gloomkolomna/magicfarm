from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import Achievement, ProductionTemplate, User, UserAchievement
from routes.admin_catalog import _auto_code, _unique_code
from services.achievements import ACHIEVEMENT_KINDS, known_kinds
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/achievements", tags=["achievements"])


class AchievementOut(BaseModel):
    id: int
    code: str
    name: str
    condition_kind: str
    condition_value: int
    production_code: str | None = None
    image_url: str | None
    earned: bool


def _ach_out(a: Achievement, user_id: int, db: Session) -> AchievementOut:
    earned = db.query(UserAchievement).filter(
        UserAchievement.user_id == user_id, UserAchievement.achievement_id == a.id
    ).first() is not None
    return AchievementOut(
        id=a.id, code=a.code, name=a.name,
        condition_kind=a.condition_kind, condition_value=a.condition_value,
        production_code=a.production_code,
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
    code: str | None = None
    name: str
    condition_kind: str
    condition_value: int = 1
    production_code: str | None = None
    image_url: str | None = None


def _validate_production_code(code: str | None, db: Session) -> None:
    if not code:
        return
    if db.query(ProductionTemplate).filter(ProductionTemplate.code == code).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Производство не найдено")


@admin_router.get("", response_model=list[AchievementOut])
def admin_list(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(Achievement).order_by(Achievement.id.asc()).all()
    return [_ach_out(a, 0, db) for a in rows]


@admin_router.get("/kinds")
def admin_kinds(
    user: User = Depends(require_role("admin")),
):
    return ACHIEVEMENT_KINDS


@admin_router.post("", response_model=AchievementOut, status_code=status.HTTP_201_CREATED)
def admin_create(
    req: AchievementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if req.condition_kind not in known_kinds():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестный тип условия")
    if req.condition_kind != "infirmary_level_complete":
        _validate_production_code(req.production_code, db)
    code = (req.code or "").strip() or _unique_code(_auto_code(req.name, "ach"), Achievement, db)
    a = Achievement(
        code=code, name=req.name,
        condition_kind=req.condition_kind, condition_value=req.condition_value,
        production_code=req.production_code,
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
    if req.condition_kind not in known_kinds():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестный тип условия")
    if req.condition_kind != "infirmary_level_complete":
        _validate_production_code(req.production_code, db)
    a.name = req.name
    a.condition_kind = req.condition_kind
    a.condition_value = req.condition_value
    a.production_code = req.production_code
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


@admin_router.put("/{achievement_id}/image", response_model=AchievementOut)
def upload_achievement_image(
    achievement_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    a = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Достижение не найдено")
    remove_upload(a.image_url)
    a.image_url = save_upload(image, f"achievement_{achievement_id}", max_size=400)
    db.commit()
    db.refresh(a)
    return _ach_out(a, 0, db)
