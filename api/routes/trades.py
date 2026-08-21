from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import (
    Inventory, TradeHold, TradeOffer, TradeOfferItem, User, UserIngredient,
)
from routes.notifications import notify

router = APIRouter(prefix="/api/trades", tags=["trades"])

TRADE_KINDS = ("plant", "product", "ingredient")
TRADE_DIRECTIONS = ("give", "want")
OPEN_STATUSES = ("open",)


class TradeItemIn(BaseModel):
    kind: str
    item_id: int
    qty: int
    direction: str


class TradeCreate(BaseModel):
    to_user_id: int
    message: str | None = None
    items: list[TradeItemIn]


class TradeItemOut(BaseModel):
    id: int
    kind: str
    item_id: int
    item_name: str
    item_emoji: str | None
    qty: int
    direction: str
    reserved: bool = False


class TradeOfferOut(BaseModel):
    id: int
    from_user_id: int
    from_name: str
    to_user_id: int
    to_name: str
    status: str
    message: str | None
    created_at: str | None
    accepted_at: str | None
    items: list[TradeItemOut]


def _stock_row(db: Session, user_id: int, kind: str, item_id: int):
    if kind == "plant":
        return db.query(Inventory).filter(
            Inventory.user_id == user_id, Inventory.plant_id == item_id
        ).first()
    if kind == "product":
        return db.query(Inventory).filter(
            Inventory.user_id == user_id, Inventory.product_id == item_id
        ).first()
    return db.query(UserIngredient).filter(
        UserIngredient.user_id == user_id, UserIngredient.ingredient_id == item_id
    ).first()


def _stock_qty(db: Session, user_id: int, kind: str, item_id: int) -> int:
    row = _stock_row(db, user_id, kind, item_id)
    return row.qty if row is not None else 0


def _item_meta(db: Session, kind: str, item_id: int) -> tuple[str, str | None]:
    if kind == "plant":
        from models import Plant
        p = db.query(Plant).filter(Plant.id == item_id).first()
        return (p.name if p else "?", p.emoji if p else None)
    if kind == "product":
        from models import Product
        p = db.query(Product).filter(Product.id == item_id).first()
        return (p.name if p else "?", p.emoji if p else None)
    from models import Ingredient
    ing = db.query(Ingredient).filter(Ingredient.id == item_id).first()
    return (ing.name if ing else "?", None)


def _user_name(db: Session, user: User) -> str:
    if user.display_name:
        return user.display_name
    nm: dict = {}
    try:
        from services.vk_names import resolve_vk_names
        nm = resolve_vk_names([user.vk_id]).get(user.vk_id, {})
    except Exception:
        nm = {}
    full = f"{nm.get('first_name', '')} {nm.get('last_name', '')}".strip()
    return full or f"Игрок {user.vk_id}"


def _offer_out(db: Session, offer: TradeOffer) -> TradeOfferOut:
    from_ = db.query(User).filter(User.vk_id == offer.from_user_id).first()
    to = db.query(User).filter(User.vk_id == offer.to_user_id).first()
    return TradeOfferOut(
        id=offer.id,
        from_user_id=offer.from_user_id,
        from_name=_user_name(db, from_) if from_ else f"Игрок {offer.from_user_id}",
        to_user_id=offer.to_user_id,
        to_name=_user_name(db, to) if to else f"Игрок {offer.to_user_id}",
        status=offer.status,
        message=offer.message,
        created_at=offer.created_at.isoformat() if offer.created_at else None,
        accepted_at=offer.accepted_at.isoformat() if offer.accepted_at else None,
        items=[
            TradeItemOut(
                id=it.id, kind=it.kind, item_id=it.item_id,
                item_name=_item_meta(db, it.kind, it.item_id)[0],
                item_emoji=_item_meta(db, it.kind, it.item_id)[1],
                qty=it.qty, direction=it.direction,
                reserved=offer.status == "open" and it.direction == "give",
            )
            for it in offer.items
        ],
    )


def _release_holds(db: Session, offer_id: int, to_user_id: int) -> None:
    """Возвращает зарезервированные предметы «отдаю» обратно отправителю."""
    for hold in db.query(TradeHold).filter(TradeHold.offer_id == offer_id).all():
        _transfer(db, to_user_id, hold.kind, hold.item_id, hold.qty)
        db.delete(hold)


def _validate_items(db: Session, user_id: int, items: list[TradeItemIn]) -> None:
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Добавьте хотя бы один предмет")
    has_give = False
    for it in items:
        if it.kind not in TRADE_KINDS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестный тип предмета")
        if it.direction not in TRADE_DIRECTIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестное направление обмена")
        if it.qty < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Количество должно быть от 1")
        if it.direction == "give":
            has_give = True
    if not has_give:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите, что вы отдаёте (give)")


def _ensure_target_user(db: Session, vk_id: int) -> User:
    target = db.query(User).filter(User.vk_id == vk_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    if (target.status or "active") == "blocked":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Игрок заблокирован")
    return target


def _get_open_offer(db: Session, offer_id: int) -> TradeOffer:
    offer = db.query(TradeOffer).filter(TradeOffer.id == offer_id).first()
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Предложение не найдено")
    if offer.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Предложение уже закрыто")
    return offer


def _transfer(db: Session, user_id: int, kind: str, item_id: int, qty: int) -> None:
    row = _stock_row(db, user_id, kind, item_id)
    if row is None:
        if kind == "plant":
            row = Inventory(user_id=user_id, plant_id=item_id, qty=0)
        elif kind == "product":
            row = Inventory(user_id=user_id, product_id=item_id, qty=0)
        else:
            row = UserIngredient(user_id=user_id, ingredient_id=item_id, qty=0)
        db.add(row)
    row.qty = (row.qty or 0) + qty
    if (row.qty or 0) <= 0:
        db.delete(row)


@router.get("/incoming", response_model=list[TradeOfferOut])
def list_incoming(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offers = (
        db.query(TradeOffer)
        .filter(TradeOffer.to_user_id == user.vk_id, TradeOffer.status.in_(OPEN_STATUSES))
        .order_by(TradeOffer.created_at.desc())
        .all()
    )
    return [_offer_out(db, o) for o in offers]


@router.get("/outgoing", response_model=list[TradeOfferOut])
def list_outgoing(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offers = (
        db.query(TradeOffer)
        .filter(TradeOffer.from_user_id == user.vk_id, TradeOffer.status.in_(OPEN_STATUSES))
        .order_by(TradeOffer.created_at.desc())
        .all()
    )
    return [_offer_out(db, o) for o in offers]


@router.get("/history", response_model=list[TradeOfferOut])
def list_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offers = (
        db.query(TradeOffer)
        .filter(
            (TradeOffer.from_user_id == user.vk_id) | (TradeOffer.to_user_id == user.vk_id),
            TradeOffer.status != "open",
        )
        .order_by(TradeOffer.created_at.desc())
        .limit(50)
        .all()
    )
    return [_offer_out(db, o) for o in offers]


@router.post("", response_model=TradeOfferOut, status_code=status.HTTP_201_CREATED)
def create_trade(
    req: TradeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.to_user_id == user.vk_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя обмениваться с собой")
    target = _ensure_target_user(db, req.to_user_id)
    _validate_items(db, user.vk_id, req.items)

    for it in req.items:
        if it.direction == "give":
            have = _stock_qty(db, user.vk_id, it.kind, it.item_id)
            if have < it.qty:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недостаточно предметов на вашем складе")
        else:
            have = _stock_qty(db, target.vk_id, it.kind, it.item_id)
            if have < it.qty:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У игрока недостаточно запрошенных предметов")

    offer = TradeOffer(
        from_user_id=user.vk_id, to_user_id=req.to_user_id,
        status="open", message=(req.message or "").strip() or None,
    )
    db.add(offer)
    db.flush()
    for it in req.items:
        db.add(TradeOfferItem(
            offer_id=offer.id, kind=it.kind, item_id=it.item_id,
            qty=it.qty, direction=it.direction,
        ))
        if it.direction == "give":
            _transfer(db, user.vk_id, it.kind, it.item_id, -it.qty)
            db.add(TradeHold(
                offer_id=offer.id, kind=it.kind, item_id=it.item_id, qty=it.qty,
            ))
    db.commit()
    db.refresh(offer)
    return _offer_out(db, offer)


@router.post("/{offer_id}/accept", response_model=TradeOfferOut)
def accept_trade(
    offer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offer = _get_open_offer(db, offer_id)
    if offer.to_user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Принять может только получатель")

    for it in offer.items:
        if it.direction == "give":
            continue
        if _stock_qty(db, offer.to_user_id, it.kind, it.item_id) < it.qty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У вас уже нет запрошенных предметов")

    for it in offer.items:
        if it.direction == "give":
            _transfer(db, offer.to_user_id, it.kind, it.item_id, it.qty)
        else:
            _transfer(db, offer.to_user_id, it.kind, it.item_id, -it.qty)
            _transfer(db, offer.from_user_id, it.kind, it.item_id, it.qty)

    for hold in db.query(TradeHold).filter(TradeHold.offer_id == offer.id).all():
        db.delete(hold)

    offer.status = "accepted"
    offer.accepted_at = datetime.datetime.utcnow()
    notify(db, offer.from_user_id, f"✅ {_user_name(db, user)} принял(а) ваше предложение по бартеру", peer_vk_id=offer.to_user_id)
    db.commit()
    db.refresh(offer)
    return _offer_out(db, offer)


@router.post("/{offer_id}/cancel", response_model=TradeOfferOut)
def cancel_trade(
    offer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offer = _get_open_offer(db, offer_id)
    if offer.from_user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Отменить может только отправитель")
    _release_holds(db, offer.id, offer.from_user_id)
    offer.status = "cancelled"
    notify(db, offer.to_user_id, f"🗑 {_user_name(db, user)} отменил(а) своё предложение по бартеру", peer_vk_id=offer.from_user_id)
    db.commit()
    db.refresh(offer)
    return _offer_out(db, offer)


@router.post("/{offer_id}/reject", response_model=TradeOfferOut)
def reject_trade(
    offer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offer = _get_open_offer(db, offer_id)
    if offer.to_user_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Отклонить может только получатель")
    _release_holds(db, offer.id, offer.from_user_id)
    offer.status = "rejected"
    notify(db, offer.from_user_id, f"✕ {_user_name(db, user)} отклонил(а) ваше предложение по бартеру", peer_vk_id=offer.to_user_id)
    db.commit()
    db.refresh(offer)
    return _offer_out(db, offer)
