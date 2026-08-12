from __future__ import annotations
import json
import random

from sqlalchemy.orm import Session

from models import CrystalCard


def draw_cards(db: Session, num_cards: int, allow_treasure: bool) -> list[dict]:
    ordinary = db.query(CrystalCard).filter(CrystalCard.is_treasure == False).all()
    treasure = db.query(CrystalCard).filter(CrystalCard.is_treasure == True).all() if allow_treasure else []

    pool = list(ordinary)
    if treasure:
        pool.extend(treasure)

    if num_cards < 1:
        return []
    if num_cards > len(pool):
        num_cards = len(pool)

    drawn = random.sample(pool, num_cards)
    return [{"color": c.color, "value": c.value, "is_treasure": c.is_treasure} for c in drawn]


def cards_to_json(cards: list[dict]) -> str:
    return json.dumps(cards, ensure_ascii=False)


def cards_from_json(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return []


def calculate_norm(db: Session, user, cards: list[dict]) -> int:
    from routes.settings import crystal_norm
    total = 0
    for c in cards:
        if c.get("is_treasure"):
            total += _treasure_norm(db, user, c["color"])
        else:
            total += crystal_norm(db, user, c["color"], c["value"])
    return total


def _treasure_norm(db: Session, user, color: str) -> int:
    from models import UserCrystalNorm
    treasure_color = f"treasure_{color}"
    row = db.query(UserCrystalNorm).filter(
        UserCrystalNorm.user_id == user.vk_id,
        UserCrystalNorm.color == treasure_color,
    ).first()
    if row is not None:
        return row.value
    return 0


def seed_cards(db: Session) -> None:
    from models import CrystalCard
    if db.query(CrystalCard).first() is not None:
        return
    for color in ("green", "blue", "violet"):
        for value in range(1, 6):
            db.add(CrystalCard(color=color, value=value, is_treasure=False))
    for color in ("green", "blue", "violet"):
        db.add(CrystalCard(color=color, value=0, is_treasure=True))
    db.commit()
