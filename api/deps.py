from __future__ import annotations
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from db import get_db
from models import User
from services.auth import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


READONLY_SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    vk_id = decode_access_token(creds.credentials)
    if vk_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный токен")
    user = db.query(User).filter(User.vk_id == vk_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    if user.role != "admin" and user.status == "blocked":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт заблокирован")
    if user.role != "admin" and user.status == "readonly" and request.method not in READONLY_SAFE_METHODS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ закрыт: только просмотр")
    return user


def require_role(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return user
    return checker


def require_location(location_code: str):
    def checker(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        from services.availability import location_lock_reason

        reason = location_lock_reason(location_code, user, db)
        if reason is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
        return user
    return checker


def require_onboarding(user: User = Depends(get_current_user)) -> User:
    if not user.onboarding_done:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Сначала задайте нормы вышивки в онбординге",
        )
    return user
