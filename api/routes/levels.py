from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user, require_role
from models import LevelGate, User
from services.achievements import check_and_award
from services.leveling import check_level_up
from services.uploads import save_upload

router = APIRouter(prefix="/api/levels", tags=["levels"])

UNLOCK_OPTIONS = [
    "Животноводство +1",
    "Животноводство +2",
    "Питомец-помощник +1",
    "Сад 1 уровня",
    "Сад 2 уровня",
    "Сад 3 уровня",
    "Грядка 2 уровня",
    "Грядка 3 уровня",
]


class LevelGateOut(BaseModel):
    level: int
    coins_required: int
    plots_required: int
    unlock_type: str | None
    image_url: str | None


def _gate_to_out(g: LevelGate) -> LevelGateOut:
    return LevelGateOut(
        level=g.level,
        coins_required=g.coins_required,
        plots_required=g.plots_required,
        unlock_type=g.unlock_type,
        image_url=g.image_url,
    )


@router.get("", response_model=list[LevelGateOut])
def list_levels(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(LevelGate).order_by(LevelGate.level.asc()).all()
    return [_gate_to_out(g) for g in rows]


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


admin_router = APIRouter(prefix="/api/admin/levels", tags=["admin-levels"])


@admin_router.get("", response_model=list[LevelGateOut])
def admin_list_levels(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(LevelGate).order_by(LevelGate.level.asc()).all()
    return [_gate_to_out(g) for g in rows]


@admin_router.put("", response_model=LevelGateOut)
def admin_set_level(
    level: int,
    coins_required: int,
    plots_required: int,
    unlock_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if level < 1 or level > 16:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Уровень 1-16")
    if unlock_type is not None and unlock_type not in UNLOCK_OPTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый тип разблокировки. Допустимые: {', '.join(UNLOCK_OPTIONS)}",
        )
    g = db.query(LevelGate).filter(LevelGate.level == level).first()
    if g is None:
        g = LevelGate(level=level)
        db.add(g)
    g.coins_required = coins_required
    g.plots_required = plots_required
    g.unlock_type = unlock_type
    db.commit()
    db.refresh(g)
    return _gate_to_out(g)


@admin_router.post("/{level}/image", response_model=LevelGateOut)
def admin_upload_level_image(
    level: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    g = db.query(LevelGate).filter(LevelGate.level == level).first()
    if g is None:
        g = LevelGate(level=level, coins_required=0, plots_required=0)
        db.add(g)
    url = save_upload(image, prefix=f"level_{level}")
    g.image_url = url
    db.commit()
    db.refresh(g)
    return _gate_to_out(g)


@admin_router.delete("/{level}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_level(
    level: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    g = db.query(LevelGate).filter(LevelGate.level == level).first()
    if g is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Уровень не найден")
    db.delete(g)
    db.commit()
    return None
