from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import ChatMessage, User
from services.vk_names import resolve_vk_names

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessageIn(BaseModel):
    text: str


class ChatMessageOut(BaseModel):
    id: int
    from_user_id: int
    to_user_id: int
    text: str
    created_at: str
    read: bool


class ConversationOut(BaseModel):
    vk_id: int
    display_name: str
    last_message: str
    last_message_at: str | None
    unread_count: int


def _user_name(user: User) -> str:
    if user.display_name:
        return user.display_name
    nm = resolve_vk_names([user.vk_id]).get(user.vk_id, {})
    full = f"{nm.get('first_name', '')} {nm.get('last_name', '')}".strip()
    return full or f"Игрок {user.vk_id}"


def _msg_out(m: ChatMessage) -> ChatMessageOut:
    return ChatMessageOut(
        id=m.id, from_user_id=m.from_user_id, to_user_id=m.to_user_id,
        text=m.text, created_at=m.created_at.isoformat(),
        read=m.read_at is not None,
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(ChatMessage)
        .filter(or_(ChatMessage.from_user_id == user.vk_id, ChatMessage.to_user_id == user.vk_id))
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    by_peer: dict[int, list[ChatMessage]] = {}
    for m in rows:
        peer = m.to_user_id if m.from_user_id == user.vk_id else m.from_user_id
        by_peer.setdefault(peer, []).append(m)

    peers = {p.vk_id: p for p in db.query(User).filter(User.vk_id.in_(by_peer.keys())).all()}
    result = []
    for peer_id, msgs in by_peer.items():
        last = msgs[-1]
        unread = sum(1 for m in msgs if m.to_user_id == user.vk_id and m.read_at is None)
        p = peers.get(peer_id)
        result.append(ConversationOut(
            vk_id=peer_id,
            display_name=_user_name(p) if p else f"Игрок {peer_id}",
            last_message=last.text,
            last_message_at=last.created_at.isoformat(),
            unread_count=unread,
        ))
    result.sort(key=lambda c: c.last_message_at or "", reverse=True)
    return result


@router.get("/with/{vk_id}", response_model=list[ChatMessageOut])
def get_thread(
    vk_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if vk_id == user.vk_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя писать самому себе")
    peer = db.query(User).filter(User.vk_id == vk_id).first()
    if peer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    if (peer.status or "active") == "blocked":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Игрок заблокирован")

    incoming = (
        db.query(ChatMessage)
        .filter(ChatMessage.to_user_id == user.vk_id, ChatMessage.from_user_id == vk_id, ChatMessage.read_at.is_(None))
        .all()
    )
    now = datetime.datetime.utcnow()
    for m in incoming:
        m.read_at = now
    if incoming:
        db.commit()

    msgs = (
        db.query(ChatMessage)
        .filter(
            or_(
                (ChatMessage.from_user_id == user.vk_id) & (ChatMessage.to_user_id == vk_id),
                (ChatMessage.from_user_id == vk_id) & (ChatMessage.to_user_id == user.vk_id),
            )
        )
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [_msg_out(m) for m in msgs]


@router.post("/with/{vk_id}", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    vk_id: int,
    req: ChatMessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if vk_id == user.vk_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя писать самому себе")
    peer = db.query(User).filter(User.vk_id == vk_id).first()
    if peer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    if (peer.status or "active") == "blocked":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Игрок заблокирован")
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сообщение не может быть пустым")
    if len(text) > 2000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сообщение слишком длинное")

    m = ChatMessage(from_user_id=user.vk_id, to_user_id=vk_id, text=text)
    db.add(m)
    db.commit()
    db.refresh(m)
    return _msg_out(m)
