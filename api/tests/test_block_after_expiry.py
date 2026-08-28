import datetime
from datetime import timedelta

from models import User
from services.subscription_tasks import apply_future_blocks
from tests.conftest import TestingSessionLocal


def _utcnow():
    return datetime.datetime.utcnow()


def _seed(vk_id, *, sub_days=None, trial_days=None, block=False, status="active", role="player"):
    with TestingSessionLocal() as db:
        db.add(User(
            vk_id=vk_id, role=role, status=status, block_after_expiry=block,
            trial_until=_utcnow() + timedelta(days=trial_days) if trial_days is not None else None,
            subscription_until=_utcnow() + timedelta(days=sub_days) if sub_days is not None else None,
        ))
        db.commit()


def _get(vk_id):
    with TestingSessionLocal() as db:
        u = db.query(User).filter(User.vk_id == vk_id).first()
        return u.status, bool(u.block_after_expiry)


def test_admin_sets_block_after_expiry(admin_client):
    _seed(501, sub_days=10)
    res = admin_client.post("/api/admin/players/501/block-after-expiry", json={"enabled": True})
    assert res.status_code == 200
    body = res.json()
    assert body["block_after_expiry"] is True
    assert body["status"] == "active"
    assert _get(501) == ("active", True)


def test_admin_block_with_expired_access_sets_readonly_now(admin_client):
    _seed(502)
    res = admin_client.post("/api/admin/players/502/block-after-expiry", json={"enabled": True})
    assert res.status_code == 200
    assert res.json()["status"] == "readonly"
    assert _get(502) == ("readonly", True)


def test_admin_unblock_restores_active(admin_client):
    _seed(503, status="readonly", block=True)
    res = admin_client.post("/api/admin/players/503/block-after-expiry", json={"enabled": False})
    assert res.status_code == 200
    assert res.json()["status"] == "active"
    assert _get(503) == ("active", False)


def test_admin_unblock_keeps_blocked_status(admin_client):
    _seed(504, status="blocked", block=True)
    res = admin_client.post("/api/admin/players/504/block-after-expiry", json={"enabled": False})
    assert res.status_code == 200
    assert res.json()["status"] == "blocked"


def test_admin_block_unknown_player_404(admin_client):
    res = admin_client.post("/api/admin/players/9999/block-after-expiry", json={"enabled": True})
    assert res.status_code == 404


def test_block_after_expiry_requires_admin(player_client):
    _seed(505)
    res = player_client.post("/api/admin/players/505/block-after-expiry", json={"enabled": True})
    assert res.status_code == 403


def test_players_list_includes_block_after_expiry(admin_client):
    _seed(506, block=True)
    _seed(507)
    res = admin_client.get("/api/admin/players")
    assert res.status_code == 200
    rows = {p["vk_id"]: p["block_after_expiry"] for p in res.json()}
    assert rows[506] is True
    assert rows[507] is False


def test_me_returns_subscription_fields(player_client):
    player_client.get("/api/me")
    with TestingSessionLocal() as db:
        u = db.query(User).filter(User.vk_id == 123).first()
        u.subscription_until = _utcnow() + timedelta(days=5)
        u.block_after_expiry = True
        db.commit()
    res = player_client.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["block_after_expiry"] is True
    assert body["subscription_days_left"] == 5


def test_apply_future_blocks_sets_readonly_after_expiry(db):
    _seed(508, sub_days=-1, block=True)
    changed = apply_future_blocks(db)
    assert changed == 1
    assert _get(508) == ("readonly", True)
    assert apply_future_blocks(db) == 0


def test_apply_future_blocks_keeps_active_subscription(db):
    _seed(509, sub_days=3, block=True)
    assert apply_future_blocks(db) == 0
    assert _get(509)[0] == "active"


def test_apply_future_blocks_keeps_active_trial(db):
    _seed(510, trial_days=2, block=True)
    assert apply_future_blocks(db) == 0
    assert _get(510)[0] == "active"


def test_apply_future_blocks_skips_unflagged(db):
    _seed(511, sub_days=-1)
    assert apply_future_blocks(db) == 0
    assert _get(511)[0] == "active"


def test_apply_future_blocks_keeps_blocked_status(db):
    _seed(512, sub_days=-1, block=True, status="blocked")
    assert apply_future_blocks(db) == 0
    assert _get(512)[0] == "blocked"


def test_apply_future_blocks_skips_admins(db):
    _seed(513, sub_days=-1, block=True, role="admin")
    assert apply_future_blocks(db) == 0
    assert _get(513)[0] == "active"
