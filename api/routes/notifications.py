from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import Notification, User

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: int
    text: str
    peer_vk_id: int | None = None
    kind: str | None = None
    created_at: str
    read: bool


class UnreadCountOut(BaseModel):
    count: int = 0


class OkOut(BaseModel):
    ok: bool = True


def _notif_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id, text=n.text, peer_vk_id=n.peer_vk_id, kind=n.kind,
        created_at=n.created_at.isoformat() if n.created_at else "",
        read=n.read_at is not None,
    )


def notify(db: Session, user_id: int, text: str, peer_vk_id: int | None = None, kind: str | None = None) -> None:
    db.add(Notification(user_id=user_id, text=text, peer_vk_id=peer_vk_id, kind=kind))


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.vk_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(50)
        .all()
    )
    return [_notif_out(n) for n in rows]


@router.get("/unread-count", response_model=UnreadCountOut)
def unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user.vk_id, Notification.read_at.is_(None))
        .count()
    )
    return UnreadCountOut(count=count)


@router.post("/read", response_model=OkOut)
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.vk_id, Notification.read_at.is_(None))
        .all()
    )
    now = datetime.datetime.utcnow()
    for n in rows:
        n.read_at = now
    if rows:
        db.commit()
    return OkOut()


@router.post("/{notification_id}/read", response_model=OkOut)
def mark_one_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.vk_id,
    ).first()
    if n is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Уведомление не найдено")
    if n.read_at is None:
        n.read_at = datetime.datetime.utcnow()
        db.commit()
    return OkOut()
