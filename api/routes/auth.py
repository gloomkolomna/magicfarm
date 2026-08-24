from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from db import get_db
from models import AllowedPlayer, User
from services.auth import create_access_token
from services.vk_sign import verify_launch_params

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SessionRequest(BaseModel):
    params: dict


class SessionResponse(BaseModel):
    token: str
    vk_id: int
    role: str


@router.post("/session", response_model=SessionResponse)
def create_session(req: SessionRequest, db: Session = Depends(get_db)):
    vk_id = verify_launch_params(req.params)
    if vk_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверная подпись")

    user = db.query(User).filter(User.vk_id == vk_id).first()
    is_admin = vk_id in config.get_admin_vk_ids()
    invite = db.query(AllowedPlayer).filter(AllowedPlayer.vk_id == vk_id).first()
    if config.ADMIN_ONLY and not is_admin and user is None and invite is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к игре пока закрыт")
    if user is None:
        from services.subscription import get_trial_days

        user = User(
            vk_id=vk_id,
            role="admin" if is_admin else "player",
            display_name=None,
            trial_until=datetime.datetime.utcnow() + datetime.timedelta(days=get_trial_days(db)),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if user.role != "admin" and user.status == "blocked":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт заблокирован")
        if is_admin and user.role != "admin":
            user.role = "admin"
            db.commit()
            db.refresh(user)

    if invite is not None:
        db.delete(invite)
        db.commit()

    if not user.display_name:
        full = ""
        try:
            from services.vk_names import resolve_vk_names
            nm = resolve_vk_names([user.vk_id]).get(user.vk_id, {})
            full = f"{nm.get('first_name', '')} {nm.get('last_name', '')}".strip()
        except Exception:
            full = ""
        if full:
            user.display_name = full
            db.commit()

    token = create_access_token(user.vk_id)
    return SessionResponse(token=token, vk_id=user.vk_id, role=user.role)
