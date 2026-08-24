from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import ChatMessage, Gift, User
from routes.gifts import _gift_meta
from services.vk_names import vk_display_name

router = APIRouter(prefix="/api/chat", tags=["chat"])

CONVERSATION_MESSAGES_LIMIT = 200


class ChatMessageIn(BaseModel):
    text: str


class ChatMessageOut(BaseModel):
    id: int
    from_user_id: int
    to_user_id: int
    text: str
    created_at: str
    read: bool
    kind: str = "text"
    gift_id: int | None = None
    gift_claimed: bool = False
    gift_item_emoji: str | None = None
    gift_item_image_url: str | None = None


class ConversationOut(BaseModel):
    vk_id: int
    display_name: str
    last_message: str
    last_message_at: str | None
    unread_count: int


def _user_name(user: User) -> str:
    return vk_display_name(user)


def _msg_out(m: ChatMessage, gift_meta: dict[int, tuple[bool, str | None, str | None]] | None = None) -> ChatMessageOut:
    claimed, emoji, image = (False, None, None)
    if m.gift_id is not None and gift_meta is not None:
        claimed, emoji, image = gift_meta.get(m.gift_id, (False, None, None))
    return ChatMessageOut(
        id=m.id, from_user_id=m.from_user_id, to_user_id=m.to_user_id,
        text=m.text, created_at=m.created_at.isoformat(),
        read=m.read_at is not None,
        kind=m.kind or "text", gift_id=m.gift_id,
        gift_claimed=claimed,
        gift_item_emoji=emoji,
        gift_item_image_url=image,
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recent = (
        db.query(ChatMessage)
        .filter(or_(ChatMessage.from_user_id == user.vk_id, ChatMessage.to_user_id == user.vk_id))
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(CONVERSATION_MESSAGES_LIMIT)
        .all()
    )
    unread_rows = (
        db.query(ChatMessage.from_user_id, func.count(ChatMessage.id))
        .filter(ChatMessage.to_user_id == user.vk_id, ChatMessage.read_at.is_(None))
        .group_by(ChatMessage.from_user_id)
        .all()
    )
    unread_by_peer = {peer: cnt for peer, cnt in unread_rows}

    by_peer: dict[int, ChatMessage] = {}
    for m in reversed(recent):
        peer = m.to_user_id if m.from_user_id == user.vk_id else m.from_user_id
        by_peer[peer] = m

    peers = {p.vk_id: p for p in db.query(User).filter(User.vk_id.in_(by_peer.keys())).all()}
    result = []
    for peer_id, last in by_peer.items():
        p = peers.get(peer_id)
        result.append(ConversationOut(
            vk_id=peer_id,
            display_name=_user_name(p) if p else f"Игрок {peer_id}",
            last_message=last.text,
            last_message_at=last.created_at.isoformat(),
            unread_count=unread_by_peer.get(peer_id, 0),
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
    gift_meta: dict[int, tuple[bool, str | None, str | None]] = {}
    gift_ids = [m.gift_id for m in msgs if m.gift_id is not None]
    if gift_ids:
        for g in db.query(Gift).filter(Gift.id.in_(gift_ids)).all():
            _, emoji, image = _gift_meta(db, g.kind, g.item_id)
            gift_meta[g.id] = (g.claimed_at is not None, emoji, image)
    return [_msg_out(m, gift_meta) for m in msgs]


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
