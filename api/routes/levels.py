import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import LevelGate, User
from services.achievements import check_and_award
from services.leveling import check_level_up

router = APIRouter(prefix="/api/levels", tags=["levels"])


class LevelGateOut(BaseModel):
    variant: int
    level: int
    coins_required: int
    plots_required: int
    rewards: dict | None


def _gate_to_out(g: LevelGate) -> LevelGateOut:
    rewards = None
    if g.rewards_json:
        try:
            rewards = json.loads(g.rewards_json)
        except (TypeError, ValueError):
            rewards = None
    return LevelGateOut(
        variant=g.variant, level=g.level,
        coins_required=g.coins_required, plots_required=g.plots_required,
        rewards=rewards,
    )


@router.get("", response_model=list[LevelGateOut])
def list_levels(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.route_variant is None:
        return []
    rows = db.query(LevelGate).filter(
        LevelGate.variant == user.route_variant
    ).order_by(LevelGate.level.asc()).all()
    return [_gate_to_out(g) for g in rows]


class RouteVariantRequest(BaseModel):
    variant: int


@router.put("/route-variant", response_model=dict)
def set_route_variant(
    req: RouteVariantRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.route_variant is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Вариант маршрутного листа уже выбран и не может быть изменён",
        )
    if req.variant < 1 or req.variant > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вариант должен быть от 1 до 4",
        )
    exists = db.query(LevelGate).filter(LevelGate.variant == req.variant).first()
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для этого варианта ещё не заданы уровни",
        )
    u = db.query(User).filter(User.vk_id == user.vk_id).first()
    u.route_variant = req.variant
    db.commit()
    return {"route_variant": req.variant}


@router.post("/advance", response_model=dict)
def advance_level(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    new_level = check_level_up(db, user)

    check_and_award(user.vk_id, "level_reached", db)

    if new_level is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Условия для перехода на следующий уровень не выполнены",
        )
    return {"level": new_level}


# ── Admin ──

admin_router = APIRouter(prefix="/api/admin/levels", tags=["admin-levels"])


class LevelGateCreate(BaseModel):
    variant: int
    level: int
    coins_required: int
    plots_required: int
    rewards: dict | None = None


@admin_router.get("", response_model=list[LevelGateOut])
def admin_list_levels(
    variant: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    q = db.query(LevelGate).order_by(LevelGate.variant.asc(), LevelGate.level.asc())
    if variant is not None:
        q = q.filter(LevelGate.variant == variant)
    return [_gate_to_out(g) for g in q.all()]


@admin_router.put("", response_model=LevelGateOut)
def admin_set_level(
    req: LevelGateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if req.variant < 1 or req.variant > 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вариант 1-4")
    if req.level < 1 or req.level > 16:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Уровень 1-16")
    g = db.query(LevelGate).filter(
        LevelGate.variant == req.variant, LevelGate.level == req.level
    ).first()
    if g is None:
        g = LevelGate(variant=req.variant, level=req.level)
        db.add(g)
    g.coins_required = req.coins_required
    g.plots_required = req.plots_required
    g.rewards_json = json.dumps(req.rewards) if req.rewards else None
    db.commit()
    db.refresh(g)
    return _gate_to_out(g)


@admin_router.delete("/{variant}/{level}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_level(
    variant: int,
    level: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    g = db.query(LevelGate).filter(
        LevelGate.variant == variant, LevelGate.level == level
    ).first()
    if g is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Уровень не найден")
    db.delete(g)
    db.commit()
    return None
