from __future__ import annotations
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
    allowed = (
        db.query(AllowedPlayer.vk_id).filter(AllowedPlayer.vk_id == vk_id).first() is not None
    )
    if config.ADMIN_ONLY and not is_admin and not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к игре пока закрыт")
    if user is None:
        user = User(
            vk_id=vk_id,
            role="admin" if is_admin else "player",
            display_name=None,
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

    token = create_access_token(user.vk_id)
    return SessionResponse(token=token, vk_id=user.vk_id, role=user.role)
