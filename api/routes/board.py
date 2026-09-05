from __future__ import annotations
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import BoardHold, BoardPost, BoardPostItem, User
from routes.notifications import notify
from routes.trades import _item_meta, _stock_qty, _transfer, _user_name

router = APIRouter(prefix="/api/board", tags=["board"])

BOARD_KINDS = ("plant", "product", "ingredient")
BOARD_DIRECTIONS = ("give", "want")
BOARD_TTL_DAYS = 3
BOARD_MESSAGE_MAX = 1000


class BoardItemIn(BaseModel):
    kind: str
    item_id: int
    qty: int
    direction: str


class BoardCreate(BaseModel):
    message: str | None = None
    items: list[BoardItemIn]


class BoardItemOut(BaseModel):
    id: int
    kind: str
    item_id: int
    item_name: str
    item_emoji: str | None
    item_image: str | None = None
    qty: int
    direction: str


class BoardPostOut(BaseModel):
    id: int
    author_id: int
    author_name: str
    status: str
    message: str | None
    created_at: str | None
    expires_at: str | None
    items: list[BoardItemOut]
    can_respond: bool = False


def _validate_items(items: list[BoardItemIn]) -> list[BoardItemIn]:
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Добавьте хотя бы один предмет")
    merged: dict[tuple[str, int, str], BoardItemIn] = {}
    for it in items:
        if it.kind not in BOARD_KINDS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестный тип предмета")
        if it.direction not in BOARD_DIRECTIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестное направление обмена")
        if it.qty < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Количество должно быть от 1")
        key = (it.kind, it.item_id, it.direction)
        if key in merged:
            merged[key].qty += it.qty
        else:
            merged[key] = it
    result = list(merged.values())
    if not any(i.direction == "give" for i in result):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите, что вы отдаёте")
    if not any(i.direction == "want" for i in result):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите, что вы хотите получить")
    if len([i for i in result if i.direction == "give"]) > 1 or len([i for i in result if i.direction == "want"]) > 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Обмен только 1 к 1: не более одного предмета с каждой стороны")
    return result


def _release_holds(db: Session, post_id: int, author_id: int) -> None:
    for hold in db.query(BoardHold).filter(BoardHold.post_id == post_id).all():
        _transfer(db, author_id, hold.kind, hold.item_id, hold.qty)
        db.delete(hold)


def _expire_stale(db: Session) -> None:
    now = datetime.datetime.utcnow()
    stale = (
        db.query(BoardPost)
        .filter(BoardPost.status == "open", BoardPost.expires_at < now)
        .all()
    )
    for post in stale:
        _release_holds(db, post.id, post.author_id)
        post.status = "expired"
    if stale:
        db.commit()


def _can_respond(db: Session, viewer_id: int, post: BoardPost) -> bool:
    for it in post.items:
        if it.direction == "want":
            if _stock_qty(db, viewer_id, it.kind, it.item_id) < it.qty:
                return False
    return True


def _items_text(db: Session, items: list[BoardPostItem]) -> str:
    parts = []
    for it in items:
        name, emoji, _ = _item_meta(db, it.kind, it.item_id)
        label = f"{emoji} {name}".strip() if emoji else name
        parts.append(f"{label} ×{it.qty}")
    return ", ".join(parts)


def _post_out(db: Session, post: BoardPost, viewer_id: int | None = None) -> BoardPostOut:
    author = db.query(User).filter(User.vk_id == post.author_id).first()
    items = []
    for it in post.items:
        name, emoji, image = _item_meta(db, it.kind, it.item_id)
        items.append(BoardItemOut(
            id=it.id, kind=it.kind, item_id=it.item_id,
            item_name=name, item_emoji=emoji, item_image=image,
            qty=it.qty, direction=it.direction,
        ))
    can_respond = False
    if viewer_id is not None and post.status == "open" and viewer_id != post.author_id:
        can_respond = _can_respond(db, viewer_id, post)
    return BoardPostOut(
        id=post.id,
        author_id=post.author_id,
        author_name=_user_name(db, author) if author else f"Игрок {post.author_id}",
        status=post.status,
        message=post.message,
        created_at=post.created_at.isoformat() if post.created_at else None,
        expires_at=post.expires_at.isoformat() if post.expires_at else None,
        items=items,
        can_respond=can_respond,
    )


@router.get("", response_model=list[BoardPostOut])
def list_board(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _expire_stale(db)
    posts = (
        db.query(BoardPost)
        .filter(BoardPost.status == "open", BoardPost.author_id != user.vk_id)
        .order_by(BoardPost.created_at.desc())
        .all()
    )
    result = []
    for post in posts:
        if _can_respond(db, user.vk_id, post):
            result.append(_post_out(db, post, user.vk_id))
    return result


@router.get("/mine", response_model=list[BoardPostOut])
def list_mine(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _expire_stale(db)
    posts = (
        db.query(BoardPost)
        .filter(BoardPost.author_id == user.vk_id, BoardPost.status == "open")
        .order_by(BoardPost.created_at.desc())
        .all()
    )
    return [_post_out(db, p, user.vk_id) for p in posts]


@router.get("/history", response_model=list[BoardPostOut])
def list_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    posts = (
        db.query(BoardPost)
        .filter(BoardPost.author_id == user.vk_id, BoardPost.status != "open")
        .order_by(BoardPost.created_at.desc())
        .limit(50)
        .all()
    )
    return [_post_out(db, p) for p in posts]


@router.post("", response_model=BoardPostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    req: BoardCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = _validate_items(req.items)
    message = (req.message or "").strip() or None
    if message is not None and len(message) > BOARD_MESSAGE_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Сообщение не может быть длиннее {BOARD_MESSAGE_MAX} символов",
        )

    for it in items:
        if it.direction == "give":
            have = _stock_qty(db, user.vk_id, it.kind, it.item_id)
            if have < it.qty:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недостаточно предметов на вашем складе")

    post = BoardPost(
        author_id=user.vk_id,
        status="open",
        message=message,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=BOARD_TTL_DAYS),
    )
    db.add(post)
    db.flush()
    for it in items:
        db.add(BoardPostItem(
            post_id=post.id, kind=it.kind, item_id=it.item_id,
            qty=it.qty, direction=it.direction,
        ))
        if it.direction == "give":
            _transfer(db, user.vk_id, it.kind, it.item_id, -it.qty)
            db.add(BoardHold(post_id=post.id, kind=it.kind, item_id=it.item_id, qty=it.qty))
    db.commit()
    db.refresh(post)
    return _post_out(db, post)


@router.post("/{post_id}/respond", response_model=BoardPostOut)
def respond(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _expire_stale(db)
    post = db.query(BoardPost).filter(BoardPost.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объявление не найдено")
    if post.status != "open":
        if post.status == "fulfilled":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Объявление уже занято")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Объявление уже закрыто")
    if post.author_id == user.vk_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя откликнуться на своё объявление")

    for it in post.items:
        if it.direction == "want":
            if _stock_qty(db, user.vk_id, it.kind, it.item_id) < it.qty:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У вас недостаточно запрошенных предметов")

    claimed = db.execute(
        update(BoardPost)
        .where(BoardPost.id == post_id, BoardPost.status == "open")
        .values(status="fulfilled", fulfilled_by=user.vk_id, fulfilled_at=datetime.datetime.utcnow())
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Объявление уже занято")

    for it in post.items:
        if it.direction == "give":
            _transfer(db, user.vk_id, it.kind, it.item_id, it.qty)
        else:
            _transfer(db, user.vk_id, it.kind, it.item_id, -it.qty)
            _transfer(db, post.author_id, it.kind, it.item_id, it.qty)

    for hold in db.query(BoardHold).filter(BoardHold.post_id == post.id).all():
        db.delete(hold)

    received = [it for it in post.items if it.direction == "want"]
    given = [it for it in post.items if it.direction == "give"]
    received_txt = _items_text(db, received)
    given_txt = _items_text(db, given)
    text = f"✅ {_user_name(db, user)} откликнулся(ась) на ваше объявление на доске"
    if received_txt:
        text += f" · вы получили: {received_txt}"
    if given_txt:
        text += f" · вы отдали: {given_txt}"
    notify(db, post.author_id, text, peer_vk_id=user.vk_id, kind="trades")
    db.commit()
    db.refresh(post)
    return _post_out(db, post)


@router.post("/{post_id}/cancel", response_model=BoardPostOut)
def cancel(
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _expire_stale(db)
    post = db.query(BoardPost).filter(BoardPost.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объявление не найдено")
    if post.author_id != user.vk_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Отменить может только автор")
    if post.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Объявление уже закрыто")
    claimed = db.execute(
        update(BoardPost)
        .where(BoardPost.id == post_id, BoardPost.status == "open")
        .values(status="cancelled")
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Объявление уже закрыто")
    _release_holds(db, post.id, post.author_id)
    db.commit()
    db.refresh(post)
    return _post_out(db, post)
