from __future__ import annotations
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import CrystalNormImage, User, UserCrystalNorm
from routes.settings import (
    CRYSTAL_COLORS, DEFAULT_DICE_NORM,
    get_crystal_standard, set_crystal_standard,
)
from services.uploads import remove_upload, save_upload

router = APIRouter(prefix="/api/crystal-norms", tags=["crystal-norms"])

MIN_NORM = 1
MAX_NORM = 100000
IMAGE_COUNTS = (0, 1, 2, 3, 4, 5)

COLOR_EMOJI = {"green": "🟢", "blue": "🔵", "violet": "🟣"}


def _validate_norms(norms: dict) -> dict[str, dict[str, int]]:
    if not isinstance(norms, dict) or set(norms.keys()) != set(CRYSTAL_COLORS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Нужны все 3 цвета: {', '.join(CRYSTAL_COLORS)}",
        )
    result: dict[str, dict[str, int]] = {}
    for color in CRYSTAL_COLORS:
        per_color = norms[color]
        if not isinstance(per_color, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Цвет {color}: нужен объект",
            )
        raw_norm = per_color.get("norm")
        if raw_norm is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{COLOR_EMOJI[color]}: норма обязательна",
            )
        try:
            norm = int(raw_norm)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{COLOR_EMOJI[color]}: норма должна быть числом",
            )
        if norm < MIN_NORM or norm > MAX_NORM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{COLOR_EMOJI[color]}: норма должна быть от {MIN_NORM} до {MAX_NORM}",
            )
        raw_treasure = per_color.get("treasure", 0)
        try:
            treasure = int(raw_treasure)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{COLOR_EMOJI[color]} 💎: сокровище должно быть числом",
            )
        if treasure < 0 or treasure > MAX_NORM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{COLOR_EMOJI[color]} 💎: сокровище должно быть от 0 до {MAX_NORM}",
            )
        result[color] = {"norm": norm, "treasure": treasure}
    return result


def _validate_dice_norm(raw) -> int:
    try:
        val = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Норма кубика должна быть числом",
        )
    if val < MIN_NORM or val > MAX_NORM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Норма кубика должна быть от {MIN_NORM} до {MAX_NORM}",
        )
    return val


class ColorNorms(BaseModel):
    norm: int
    treasure: int = 0


class NormsBlock(BaseModel):
    green: ColorNorms
    blue: ColorNorms
    violet: ColorNorms


class LevelNorms(BaseModel):
    level1: int | None = None
    level2: int | None = None
    level3: int | None = None


class StandardRequest(BaseModel):
    norms: NormsBlock


class MineRequest(BaseModel):
    norms: NormsBlock
    dice_norm: int
    animal_product_norm: int | None = None
    study_norms: LevelNorms | None = None
    production_norms: LevelNorms | None = None


class MineOut(BaseModel):
    onboarding_done: bool
    norms: dict
    dice_norm: int
    animal_product_norm: int
    study_norms: dict
    production_norms: dict


def _replace_user_norms(db: Session, user_id: int, norms: dict[str, dict[str, int]]) -> None:
    db.query(UserCrystalNorm).filter(UserCrystalNorm.user_id == user_id).delete()
    for color in CRYSTAL_COLORS:
        db.add(UserCrystalNorm(
            user_id=user_id, color=color, count=1, value=norms[color]["norm"],
        ))
        if norms[color]["treasure"] > 0:
            db.add(UserCrystalNorm(
                user_id=user_id, color=f"treasure_{color}", count=0, value=norms[color]["treasure"],
            ))


def _user_norms(db: Session, user: User) -> dict[str, dict[str, int]]:
    rows = db.query(UserCrystalNorm).filter(UserCrystalNorm.user_id == user.vk_id).all()
    personal: dict[str, int] = {}
    treasure: dict[str, int] = {}
    for r in rows:
        if r.color.startswith("treasure_"):
            treasure[r.color[len("treasure_"):]] = r.value
        elif r.count == 1:
            personal[r.color] = r.value
    standard = get_crystal_standard(db)
    result: dict[str, dict[str, int]] = {}
    for color in CRYSTAL_COLORS:
        base = personal.get(color, standard[color]["norm"])
        tr = treasure.get(color, standard[color]["treasure"])
        result[color] = {"norm": base, "treasure": tr}
    return result


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
    norms = _validate_norms(req.norms.model_dump())
    set_crystal_standard(db, norms)
    db.commit()
    return {"norms": norms}


def _validate_level_norms(raw: dict | None) -> dict[str, int | None]:
    result: dict[str, int | None] = {"level1": None, "level2": None, "level3": None}
    if raw is None:
        return result
    for key in result:
        val = raw.get(key)
        if val is None:
            continue
        try:
            num = int(val)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Норма уровня {key[-1]} должна быть числом",
            )
        if num < 1 or num > 100000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Норма уровня {key[-1]} должна быть от 1 до 100000",
            )
        result[key] = num
    return result


def _user_level_norms(user: User, attrs: dict[int, str]) -> dict[str, int | None]:
    return {f"level{lvl}": getattr(user, attr, None) for lvl, attr in attrs.items()}


def _apply_level_norms(user: User, attrs: dict[int, str], norms: dict[str, int | None]) -> None:
    for lvl, attr in attrs.items():
        val = norms.get(f"level{lvl}")
        if val is not None:
            setattr(user, attr, val)


@router.get("/mine", response_model=MineOut)
def get_my_norms(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from routes.settings import (
        _PRODUCTION_NORM_ATTRS, _STUDY_NORM_ATTRS,
        DEFAULT_ANIMAL_PRODUCT_NORM,
    )
    return {
        "onboarding_done": bool(user.onboarding_done),
        "norms": _user_norms(db, user),
        "dice_norm": user.dice_norm if user.dice_norm else DEFAULT_DICE_NORM,
        "animal_product_norm": (
            user.animal_product_norm if user.animal_product_norm else DEFAULT_ANIMAL_PRODUCT_NORM
        ),
        "study_norms": _user_level_norms(user, _STUDY_NORM_ATTRS),
        "production_norms": _user_level_norms(user, _PRODUCTION_NORM_ATTRS),
    }


@router.put("/mine", response_model=MineOut)
def set_my_norms(
    req: MineRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from routes.settings import (
        _PRODUCTION_NORM_ATTRS, _STUDY_NORM_ATTRS,
        DEFAULT_ANIMAL_PRODUCT_NORM,
    )
    norms = _validate_norms(req.norms.model_dump())
    dice = _validate_dice_norm(req.dice_norm)
    animal_product = (
        _validate_dice_norm(req.animal_product_norm) if req.animal_product_norm is not None else None
    )
    study = _validate_level_norms(req.study_norms.model_dump() if req.study_norms else None)
    production = _validate_level_norms(req.production_norms.model_dump() if req.production_norms else None)
    _replace_user_norms(db, user.vk_id, norms)
    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    u.dice_norm = dice
    if animal_product is not None:
        u.animal_product_norm = animal_product
    _apply_level_norms(u, _STUDY_NORM_ATTRS, study)
    _apply_level_norms(u, _PRODUCTION_NORM_ATTRS, production)
    u.onboarding_done = True
    db.commit()
    return {
        "onboarding_done": True,
        "norms": norms,
        "dice_norm": dice,
        "animal_product_norm": (
            u.animal_product_norm if u.animal_product_norm else DEFAULT_ANIMAL_PRODUCT_NORM
        ),
        "study_norms": study,
        "production_norms": production,
    }


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
    if count not in IMAGE_COUNTS:
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
