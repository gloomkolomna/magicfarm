from models import User, UserCrystalNorm
from routes.settings import DEFAULT_CARD_NORMS, CRYSTAL_COLORS
from services.card_draw import calculate_norm, cards_from_json, cards_to_json, draw_cards


def _seed_user(db, vk_id=123):
    user = db.query(User).filter(User.vk_id == vk_id).first()
    if user is None:
        user = User(vk_id=vk_id, role="player", onboarding_done=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        for color in CRYSTAL_COLORS:
            db.add(UserCrystalNorm(user_id=vk_id, color=color, count=1, value=DEFAULT_CARD_NORMS[color]))
        db.commit()
    return user


def test_draw_cards_normal_only(db):
    cards = draw_cards(db, 1, False)
    assert len(cards) == 1
    c = cards[0]
    assert c["is_treasure"] is False
    assert c["color"] in ("green", "blue", "violet")
    assert 1 <= c["value"] <= 5


def test_draw_cards_multiple_no_repeats(db):
    cards = draw_cards(db, 3, False)
    assert len(cards) == 3
    pairs = [(c["color"], c["value"]) for c in cards]
    assert len(pairs) == len(set(pairs))


def test_draw_cards_with_treasure(db):
    cards = draw_cards(db, 18, True)
    assert len(cards) == 18
    treasure_count = sum(1 for c in cards if c["is_treasure"])
    assert treasure_count == 3


def test_draw_cards_all_cards(db):
    cards = draw_cards(db, 18, True)
    assert len(cards) == 18


def test_draw_cards_zero_returns_empty(db):
    assert draw_cards(db, 0, False) == []


def test_draw_cards_exceeds_pool_clamped(db):
    cards = draw_cards(db, 100, True)
    assert len(cards) == 18


def test_cards_json_roundtrip(db):
    cards = draw_cards(db, 2, False)
    raw = cards_to_json(cards)
    parsed = cards_from_json(raw)
    assert parsed == cards


def test_cards_from_json_none():
    assert cards_from_json(None) == []


def test_cards_from_json_empty():
    assert cards_from_json("") == []


def test_calculate_norm_normal(db):
    user = _seed_user(db)
    cards = [{"color": "green", "value": 3, "is_treasure": False}]
    norm = calculate_norm(db, user, cards)
    assert norm == DEFAULT_CARD_NORMS["green"] * 3


def test_calculate_norm_multiple_cards(db):
    user = _seed_user(db)
    cards = [
        {"color": "green", "value": 2, "is_treasure": False},
        {"color": "blue", "value": 1, "is_treasure": False},
    ]
    norm = calculate_norm(db, user, cards)
    assert norm == DEFAULT_CARD_NORMS["green"] * 2 + DEFAULT_CARD_NORMS["blue"] * 1


def test_calculate_norm_treasure_zero_if_not_set(db):
    user = _seed_user(db)
    cards = [{"color": "green", "value": 0, "is_treasure": True}]
    norm = calculate_norm(db, user, cards)
    assert norm == 0
