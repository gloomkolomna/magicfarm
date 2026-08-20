from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from db import get_db
from deps import require_role
from models import AllowedPlayer, User
from services.vk_names import parse_vk_input, resolve_vk_names, resolve_vk_screen_name

router = APIRouter(prefix="/api/admin/access", tags=["admin-access"])


class AllowedPlayerOut(BaseModel):
    vk_id: int
    screen_name: str | None
    first_name: str
    last_name: str
    created_at: str | None


class AllowedPlayerAddRequest(BaseModel):
    link: str


def _resolve_target(link: str) -> int:
    parsed = parse_vk_input(link)
    if parsed is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось разобрать ссылку")
    kind, value = parsed
    if kind == "id":
        return int(value)
    resolved = resolve_vk_screen_name(str(value))
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось определить ID по короткому имени (проверьте ссылку или задан ли VK_SERVICE_TOKEN)",
        )
    return int(resolved["id"])


@router.get("/players", response_model=list[AllowedPlayerOut])
def list_allowed_players(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    rows = db.query(AllowedPlayer).order_by(AllowedPlayer.created_at.desc()).limit(500).all()
    names = resolve_vk_names([r.vk_id for r in rows])
    result = []
    for r in rows:
        nm = names.get(r.vk_id, {})
        result.append(AllowedPlayerOut(
            vk_id=r.vk_id,
            screen_name=r.screen_name,
            first_name=nm.get("first_name", ""),
            last_name=nm.get("last_name", ""),
            created_at=r.created_at.isoformat() if r.created_at else None,
        ))
    return result


@router.post("/players", response_model=AllowedPlayerOut, status_code=status.HTTP_201_CREATED)
def add_allowed_player(
    req: AllowedPlayerAddRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    vk_id = _resolve_target(req.link)
    if vk_id in config.get_admin_vk_ids():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот пользователь уже администратор")
    existing = db.query(AllowedPlayer).filter(AllowedPlayer.vk_id == vk_id).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Игрок уже в списке доступа")

    screen_name = None
    parsed = parse_vk_input(req.link)
    if parsed is not None and parsed[0] == "screen_name":
        screen_name = str(parsed[1])

    row = AllowedPlayer(vk_id=vk_id, screen_name=screen_name, added_by=user.vk_id)
    db.add(row)
    db.commit()
    db.refresh(row)

    names = resolve_vk_names([vk_id])
    nm = names.get(vk_id, {})
    return AllowedPlayerOut(
        vk_id=row.vk_id,
        screen_name=row.screen_name,
        first_name=nm.get("first_name", ""),
        last_name=nm.get("last_name", ""),
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


@router.delete("/players/{vk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allowed_player(
    vk_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    row = db.query(AllowedPlayer).filter(AllowedPlayer.vk_id == vk_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден в списке доступа")
    db.delete(row)
    db.commit()
    return None
