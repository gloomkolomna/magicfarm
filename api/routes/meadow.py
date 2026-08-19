from __future__ import annotations
import random

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Field, GatherCell, Ingredient, User, UserGatherLog, UserIngredient
from routes.admin_fields import _get_field_or_404
from routes.ingredients import IngredientOut, _ingredient_out
from services import msk_time

router = APIRouter(prefix="/api/meadow", tags=["meadow"])


def _check_field_gate(f: Field, user: User) -> None:
    if f.min_level is not None and (user.level or 0) < f.min_level:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Эта локация пока недоступна")


class MeadowCellOut(BaseModel):
    id: int
    col: int
    row: int
    window: str
    available: bool
    collected_today: bool
    next_open_at: str | None
    countdown_to: str | None
    ingredients: list[IngredientOut]


class MeadowOut(BaseModel):
    field_id: int
    name: str
    map_url: str | None
    cols: int
    rows: int
    now_msk: str
    cells: list[MeadowCellOut]


@router.get("/{field_id}", response_model=MeadowOut)
def get_meadow(
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = _get_field_or_404(field_id, db)
    if f.field_kind != "meadow":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Это не лесная поляна")
    _check_field_gate(f, user)

    now = msk_time.now_msk()
    today = now.date().isoformat()
    cells = db.query(GatherCell).filter(
        GatherCell.field_id == f.id
    ).order_by(GatherCell.row.asc(), GatherCell.col.asc()).all()
    collected = {
        log.gather_cell_id
        for log in db.query(UserGatherLog).filter(
            UserGatherLog.user_id == user.vk_id, UserGatherLog.date == today
        ).all()
    }
    result = []
    for gc in cells:
        active = msk_time.window_active(gc.window, now)
        collected_here = gc.id in collected
        available = active and not collected_here

        next_open = None
        countdown_to = None
        if available:
            end = msk_time.window_end_at(gc.window, now)
            if end is not None:
                countdown_to = end.isoformat()
        elif collected_here:
            countdown_to = msk_time.next_midnight_msk(now).isoformat()
        else:
            nxt = msk_time.next_open_at(gc.window, now)
            if nxt is not None:
                next_open = nxt.isoformat()
                countdown_to = nxt.isoformat()

        result.append(MeadowCellOut(
            id=gc.id, col=gc.col, row=gc.row, window=gc.window,
            available=available,
            collected_today=collected_here,
            next_open_at=next_open,
            countdown_to=countdown_to,
            ingredients=[_ingredient_out(gci.ingredient) for gci in gc.ingredients],
        ))
    return MeadowOut(
        field_id=f.id, name=f.name, map_url=f.map_url,
        cols=f.cols, rows=f.rows, now_msk=now.isoformat(), cells=result,
    )


class GatherResult(BaseModel):
    cell_id: int
    ingredient: IngredientOut
    apothecary_qty: int


@router.post("/cells/{cell_id}/gather", response_model=GatherResult)
def gather(
    cell_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    gc = db.query(GatherCell).filter(GatherCell.id == cell_id).first()
    if gc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клетка добычи не найдена")
    _check_field_gate(gc.field, user)

    now = msk_time.now_msk()
    if not msk_time.window_active(gc.window, now):
        nxt = msk_time.next_open_at(gc.window, now)
        detail = "Клетка спит"
        if nxt is not None:
            detail += f". Вернитесь в {nxt.strftime('%H:%M')} МСК"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    today = now.date().isoformat()
    existing_log = db.query(UserGatherLog).filter(
        UserGatherLog.user_id == user.vk_id,
        UserGatherLog.gather_cell_id == gc.id,
        UserGatherLog.date == today,
    ).first()
    if existing_log is not None:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Сегодня с этой клетки уже собрали")

    ing_ids = [gci.ingredient_id for gci in gc.ingredients]
    if not ing_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="На этой клетке пока ничего не растёт")

    picked_id = random.choice(ing_ids)
    ui = db.query(UserIngredient).filter(
        UserIngredient.user_id == user.vk_id, UserIngredient.ingredient_id == picked_id
    ).first()
    if ui is None:
        ui = UserIngredient(user_id=user.vk_id, ingredient_id=picked_id, qty=0)
        db.add(ui)
    ui.qty = (ui.qty or 0) + 1
    db.add(UserGatherLog(user_id=user.vk_id, gather_cell_id=gc.id, date=today))
    db.commit()

    ing = db.query(Ingredient).filter(Ingredient.id == picked_id).first()
    return GatherResult(cell_id=gc.id, ingredient=_ingredient_out(ing), apothecary_qty=ui.qty)
