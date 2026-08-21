from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import (
    ChatMessage, Gift, Ingredient, Plant, Product, User,
)
from routes.notifications import notify
from routes.trades import _stock_qty, _transfer, _user_name

router = APIRouter(prefix="/api/gifts", tags=["gifts"])

GIFT_KINDS = ("plant", "product", "ingredient")


class GiftSend(BaseModel):
    to_user_id: int
    kind: str
    item_id: int
    qty: int = 1


class GiftOut(BaseModel):
    id: int
    from_user_id: int
    from_name: str
    to_user_id: int
    kind: str
    item_id: int
    item_name: str
    item_emoji: str | None
    item_image_url: str | None
    qty: int
    created_at: str | None
    claimed: bool


def _gift_meta(db: Session, kind: str, item_id: int) -> tuple[str, str | None, str | None]:
    if kind == "plant":
        p = db.query(Plant).filter(Plant.id == item_id).first()
        image = None
        if p is not None:
            image = p.image_harvested_url or p.image_grown_url or p.image_url
        return (p.name if p else "?", p.emoji if p else None, image)
    if kind == "product":
        p = db.query(Product).filter(Product.id == item_id).first()
        return (p.name if p else "?", p.emoji if p else None, p.image_url if p else None)
    ing = db.query(Ingredient).filter(Ingredient.id == item_id).first()
    return (ing.name if ing else "?", None, ing.image_url if ing else None)


def _gift_out(db: Session, g: Gift) -> GiftOut:
    from_ = db.query(User).filter(User.vk_id == g.from_user_id).first()
    name, emoji, image = _gift_meta(db, g.kind, g.item_id)
    return GiftOut(
        id=g.id,
        from_user_id=g.from_user_id,
        from_name=_user_name(db, from_) if from_ else f"Игрок {g.from_user_id}",
        to_user_id=g.to_user_id,
        kind=g.kind, item_id=g.item_id,
        item_name=name, item_emoji=emoji, item_image_url=image,
        qty=g.qty,
        created_at=g.created_at.isoformat() if g.created_at else None,
        claimed=g.claimed_at is not None,
    )


def _get_gift(db: Session, gift_id: int) -> Gift:
    g = db.query(Gift).filter(Gift.id == gift_id).first()
    if g is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Подарок не найден")
    return g


@router.get("/received", response_model=list[GiftOut])
def list_received(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    gifts = (
        db.query(Gift)
        .filter(Gift.to_user_id == user.vk_id, Gift.claimed_at.is_(None))
        .order_by(Gift.created_at.desc())
        .all()
    )
    return [_gift_out(db, g) for g in gifts]


@router.get("/{gift_id}", response_model=GiftOut)
def get_gift(
    gift_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    g = _get_gift(db, gift_id)
    if g.to_user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Открыть подарок может только получатель")
    return _gift_out(db, g)


@router.post("", response_model=GiftOut, status_code=status.HTTP_201_CREATED)
def send_gift(
    req: GiftSend,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.to_user_id == user.vk_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя отправить подарок самому себе")
    if req.kind not in GIFT_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестный тип подарка")
    if req.qty < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Количество должно быть от 1")

    target = db.query(User).filter(User.vk_id == req.to_user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    if (target.status or "active") == "blocked":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Игрок заблокирован")

    if _stock_qty(db, user.vk_id, req.kind, req.item_id) < req.qty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недостаточно предметов на вашем складе")

    _transfer(db, user.vk_id, req.kind, req.item_id, -req.qty)

    gift = Gift(
        from_user_id=user.vk_id, to_user_id=req.to_user_id,
        kind=req.kind, item_id=req.item_id, qty=req.qty,
    )
    db.add(gift)
    db.flush()
    db.add(ChatMessage(
        from_user_id=user.vk_id, to_user_id=req.to_user_id,
        text="🎁 Вам пришёл подарок", kind="gift", gift_id=gift.id,
    ))
    notify(db, req.to_user_id, f"🎁 {_user_name(db, user)} отправил(а) вам подарок")
    db.commit()
    db.refresh(gift)
    return _gift_out(db, gift)


@router.post("/{gift_id}/claim", response_model=GiftOut)
def claim_gift(
    gift_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    g = _get_gift(db, gift_id)
    if g.to_user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Получить подарок может только получатель")
    if g.claimed_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Подарок уже получен")

    _transfer(db, user.vk_id, g.kind, g.item_id, g.qty)
    g.claimed_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(g)
    return _gift_out(db, g)
