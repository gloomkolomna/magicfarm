from __future__ import annotations
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import CrystalNormImage, User, UserCrystalNorm
from routes.settings import (
    CRYSTAL_COLORS, CRYSTAL_COUNTS, MAX_VARIANT, MIN_VARIANT, VARIANT_TABLES,
    get_crystal_standard, set_crystal_standard,
)
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/crystal-norms", tags=["crystal-norms"])

MIN_NORM = 1
MAX_NORM = 100000

COLOR_EMOJI = {"green": "🟢", "blue": "🔵", "violet": "🟣"}


def _validate_norms(norms: dict) -> dict[str, dict[int, int]]:
    if not isinstance(norms, dict) or set(norms.keys()) != set(CRYSTAL_COLORS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Нужны все 3 цвета: {', '.join(CRYSTAL_COLORS)}",
        )
    result: dict[str, dict[int, int]] = {}
    for color in CRYSTAL_COLORS:
        per_color = norms[color]
        if not isinstance(per_color, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Цвет {color}: нужен объект")
        result[color] = {}
        for cnt in CRYSTAL_COUNTS:
            raw = per_color.get(str(cnt), per_color.get(cnt))
            if raw is None:
                if cnt == 0:
                    result[color][0] = 0
                    continue
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{COLOR_EMOJI[color]}×{cnt}: значение обязательно",
                )
            try:
                val = int(raw)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{COLOR_EMOJI[color]}×{cnt}: должно быть число",
                )
            if cnt > 0 and (val < MIN_NORM or val > MAX_NORM):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{COLOR_EMOJI[color]}×{cnt}: норма должна быть от {MIN_NORM} до {MAX_NORM}",
                )
            result[color][cnt] = val
    return result


class NormsBlock(BaseModel):
    green: dict
    blue: dict
    violet: dict


class StandardRequest(BaseModel):
    norms: NormsBlock | None = None
    preset: int | None = None


class MineRequest(BaseModel):
    norms: NormsBlock


class PresetOut(BaseModel):
    variant: int
    norms: dict


class MineOut(BaseModel):
    onboarding_done: bool
    norms: dict


def _replace_user_norms(db: Session, user_id: int, norms: dict[str, dict[int, int]]) -> None:
    db.query(UserCrystalNorm).filter(UserCrystalNorm.user_id == user_id).delete()
    for color in CRYSTAL_COLORS:
        for cnt in CRYSTAL_COUNTS:
            if norms[color].get(cnt, 0) > 0:
                db.add(UserCrystalNorm(
                    user_id=user_id, color=color, count=cnt, value=norms[color][cnt],
                ))


@router.get("/presets", response_model=list[PresetOut])
def list_presets(
    user: User = Depends(get_current_user),
):
    return [
        {"variant": v, "norms": {color: dict(per_color) for color, per_color in table.items()}}
        for v, table in VARIANT_TABLES.items()
    ]


@router.get("/standard")
def get_standard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"norms": get_crystal_standard(db)}


@router.put("/admin/standard")
def set_standard(
    req: StandardRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if req.preset is not None:
        if req.preset < MIN_VARIANT or req.preset > MAX_VARIANT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Пресет должен быть от {MIN_VARIANT} до {MAX_VARIANT}",
            )
        norms = {color: dict(per_color) for color, per_color in VARIANT_TABLES[req.preset].items()}
    elif req.norms is not None:
        norms = _validate_norms(req.norms.model_dump())
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите либо preset, либо norms",
        )
    set_crystal_standard(db, norms)
    db.commit()
    return {"norms": norms}


@router.get("/mine", response_model=MineOut)
def get_my_norms(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(UserCrystalNorm).filter(UserCrystalNorm.user_id == user.vk_id).all()
    if not rows:
        return {"onboarding_done": bool(user.onboarding_done), "norms": get_crystal_standard(db)}
    norms: dict[str, dict[int, int]] = {color: {} for color in CRYSTAL_COLORS}
    for r in rows:
        norms[r.color][r.count] = r.value
    return {"onboarding_done": bool(user.onboarding_done), "norms": norms}


@router.put("/mine", response_model=MineOut)
def set_my_norms(
    req: MineRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    norms = _validate_norms(req.norms.model_dump())
    _replace_user_norms(db, user.vk_id, norms)
    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    u.onboarding_done = True
    db.commit()
    return {"onboarding_done": True, "norms": norms}


@router.post("/mine/preset/{n}", response_model=MineOut)
def apply_preset(
    n: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if n < MIN_VARIANT or n > MAX_VARIANT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Пресет должен быть от {MIN_VARIANT} до {MAX_VARIANT}",
        )
    norms = {color: dict(per_color) for color, per_color in VARIANT_TABLES[n].items()}
    _replace_user_norms(db, user.vk_id, norms)
    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    u.onboarding_done = True
    db.commit()
    return {"onboarding_done": True, "norms": norms}


# ── Изображения ячеек норм (админка) ──

class NormImageOut(BaseModel):
    color: str
    count: int
    image_url: str | None


@router.get("/admin/images", response_model=list[NormImageOut])
def list_norm_images(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(CrystalNormImage).all()
    return [NormImageOut(color=r.color, count=r.count, image_url=r.image_url) for r in rows]


@router.put("/admin/images/{color}/{count}", response_model=NormImageOut)
def upload_norm_image(
    color: str,
    count: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if color not in CRYSTAL_COLORS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный цвет")
    if count not in CRYSTAL_COUNTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверное количество")
    row = db.query(CrystalNormImage).filter(
        CrystalNormImage.color == color, CrystalNormImage.count == count
    ).first()
    if row is None:
        row = CrystalNormImage(color=color, count=count)
        db.add(row)
    remove_upload(row.image_url)
    row.image_url = save_upload(image, f"norm_{color}_{count}", max_size=200)
    db.commit()
    db.refresh(row)
    return NormImageOut(color=row.color, count=row.count, image_url=row.image_url)
