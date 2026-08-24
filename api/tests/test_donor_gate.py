import datetime
from datetime import timedelta

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from types import SimpleNamespace

from models import AllowedPlayer, DonorCache, Setting, User
from services.auth import create_access_token


def set_game_open(db, enabled: bool = True) -> None:
    s = db.query(Setting).filter(Setting.key == "game_open").first()
    if s is None:
        s = Setting(key="game_open", value="1" if enabled else "0")
        db.add(s)
    else:
        s.value = "1" if enabled else "0"
    db.commit()


def add_donor(db, vk_id: int, is_don: bool = True) -> None:
    row = db.query(DonorCache).filter(DonorCache.vk_id == vk_id).first()
    if row is None:
        row = DonorCache(vk_id=vk_id)
        db.add(row)
    row.is_don = is_don
    db.commit()


def add_user(db, vk_id: int, **kwargs) -> User:
    u = db.query(User).filter(User.vk_id == vk_id).first()
    if u is not None:
        return u
    u = User(vk_id=vk_id, **kwargs)
    db.add(u)
    db.commit()
    return u


# ── Вход: дон-гейт при game_open=1 ──


def test_game_open_blocks_new_non_donor(client, db):
    set_game_open(db, True)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "555"}})
    assert res.status_code == 403
    assert "донам" in res.json()["detail"]


def test_game_open_allows_new_donor(client, db):
    set_game_open(db, True)
    add_donor(db, 556, True)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "556"}})
    assert res.status_code == 200
    assert db.query(User).filter(User.vk_id == 556).first() is not None


def test_game_open_allows_existing_non_donor(client, db):
    set_game_open(db, True)
    add_user(db, 557)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "557"}})
    assert res.status_code == 200


def test_game_open_invite_grants_exempt(client, db):
    set_game_open(db, True)
    db.add(AllowedPlayer(vk_id=558))
    db.commit()
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "558"}})
    assert res.status_code == 200
    u = db.query(User).filter(User.vk_id == 558).first()
    assert u is not None and u.donor_exempt
    assert db.query(AllowedPlayer).filter(AllowedPlayer.vk_id == 558).first() is None


def test_game_open_admin_bypasses_donor_gate(client, db):
    set_game_open(db, True)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "400977"}})
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


def test_game_closed_keeps_old_gate(client, db, monkeypatch):
    import config

    set_game_open(db, False)
    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "559"}})
    assert res.status_code == 403
    assert "закрыт" in res.json()["detail"]

    add_user(db, 560)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "560"}})
    assert res.status_code == 200


def test_login_live_sync_updates_cache(client, db, monkeypatch):
    set_game_open(db, True)
    monkeypatch.setattr(
        "services.donor._fetch_remote",
        lambda vk_id: {"is_don": True, "don_since": "2026-08-01T00:00:00", "updated_at": "2026-08-01T00:00:00"},
    )
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "561"}})
    assert res.status_code == 200
    row = db.query(DonorCache).filter(DonorCache.vk_id == 561).first()
    assert row is not None and row.is_don


def test_login_donut_unavailable_falls_back_to_cache(client, db, monkeypatch):
    set_game_open(db, True)
    add_donor(db, 562, True)
    monkeypatch.setattr("services.donor._fetch_remote", lambda vk_id: None)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "562"}})
    assert res.status_code == 200
    row = db.query(DonorCache).filter(DonorCache.vk_id == 562).first()
    assert row is not None and row.is_don


def test_login_donut_unavailable_blocks_new_user(client, db, monkeypatch):
    set_game_open(db, True)
    monkeypatch.setattr("services.donor._fetch_remote", lambda vk_id: None)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "563"}})
    assert res.status_code == 403


# ── Мутации: can_play ──


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _req(method: str = "GET"):
    return SimpleNamespace(method=method)


def _call_mutation(db, vk_id: int):
    from deps import get_current_user

    token = create_access_token(vk_id)
    return get_current_user(_req("POST"), _creds(token), db)


def test_mutation_donor_with_trial_ok(db):
    set_game_open(db, True)
    add_donor(db, 101, True)
    add_user(db, 101, trial_until=datetime.datetime.utcnow() + timedelta(days=3))
    user = _call_mutation(db, 101)
    assert user.vk_id == 101


def test_mutation_donor_expired_subscription_402(db):
    set_game_open(db, True)
    add_donor(db, 102, True)
    add_user(db, 102)
    with pytest.raises(Exception) as exc:
        _call_mutation(db, 102)
    assert exc.value.status_code == 402
    assert "Подписка не активна" in exc.value.detail


def test_mutation_nondon_plays_out_paid_subscription(db):
    set_game_open(db, True)
    add_user(db, 103, subscription_until=datetime.datetime.utcnow() + timedelta(days=10))
    user = _call_mutation(db, 103)
    assert user.vk_id == 103


def test_mutation_nondon_trial_only_402(db):
    set_game_open(db, True)
    add_user(db, 104, trial_until=datetime.datetime.utcnow() + timedelta(days=3))
    with pytest.raises(Exception) as exc:
        _call_mutation(db, 104)
    assert exc.value.status_code == 402
    assert "Корги" in exc.value.detail


def test_mutation_nondon_expired_paid_subscription_402(db):
    set_game_open(db, True)
    add_user(db, 105, subscription_until=datetime.datetime.utcnow() - timedelta(days=1))
    with pytest.raises(Exception) as exc:
        _call_mutation(db, 105)
    assert exc.value.status_code == 402


def test_get_allowed_for_nondon(db):
    set_game_open(db, True)
    add_user(db, 106)
    from deps import get_current_user

    token = create_access_token(106)
    user = get_current_user(_req("GET"), _creds(token), db)
    assert user.vk_id == 106


def test_mutation_exempt_with_trial_ok(db):
    set_game_open(db, True)
    add_user(db, 107, donor_exempt=True, trial_until=datetime.datetime.utcnow() + timedelta(days=3))
    user = _call_mutation(db, 107)
    assert user.vk_id == 107


def test_game_closed_trial_still_plays(db):
    set_game_open(db, False)
    add_user(db, 108, trial_until=datetime.datetime.utcnow() + timedelta(days=3))
    user = _call_mutation(db, 108)
    assert user.vk_id == 108


def test_admin_always_plays(db):
    set_game_open(db, True)
    add_user(db, 400977, role="admin")
    user = _call_mutation(db, 400977)
    assert user.vk_id == 400977


# ── can_play напрямую ──


def test_can_play_matrix(db):
    from services.donor import can_play

    now = datetime.datetime.utcnow()
    donor = add_user(db, 201, trial_until=now + timedelta(days=1))
    add_donor(db, 201, True)
    assert can_play(db, donor) == (True, None)

    donor_expired = add_user(db, 202)
    add_donor(db, 202, True)
    assert can_play(db, donor_expired) == (False, "subscription_expired")

    nondon_paid = add_user(db, 203, subscription_until=now + timedelta(days=10))
    assert can_play(db, nondon_paid) == (True, None)

    nondon_trial = add_user(db, 204, trial_until=now + timedelta(days=1))
    assert can_play(db, nondon_trial) == (False, "not_donor")

    nondon_nothing = add_user(db, 205)
    assert can_play(db, nondon_nothing) == (False, "not_donor")

    exempt = add_user(db, 206, donor_exempt=True, trial_until=now + timedelta(days=1))
    assert can_play(db, exempt) == (True, None)


# ── Оплата: продление только донам ──


def test_create_order_blocked_for_nondon(db):
    set_game_open(db, True)
    from tests.conftest import make_user_client

    with make_user_client(301) as c:
        res = c.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "a@b.ru"})
    assert res.status_code == 403
    assert "донам" in res.json()["detail"]


def test_create_order_donor_passes_gate(db):
    set_game_open(db, True)
    add_donor(db, 302, True)
    from tests.conftest import make_user_client

    with make_user_client(302) as c:
        res = c.post("/api/payment/create-order", json={"dlc_codes": [], "receipt_email": "a@b.ru"})
    assert res.status_code == 503


# ── /me ──


def test_me_reports_donor_fields(db, player_client):
    set_game_open(db, True)
    add_donor(db, 123, True)
    res = player_client.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["is_donor"] is True
    assert body["game_open"] is True
    assert body["block_reason"] is None
    assert body["access_active"] is True


def test_me_block_reason_nondon(db):
    set_game_open(db, True)
    add_user(db, 401)
    from tests.conftest import make_user_client

    with make_user_client(401) as c:
        res = c.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["is_donor"] is False
    assert body["block_reason"] == "not_donor"
    assert body["access_active"] is False


# ── Админка ──


def test_admin_donor_sync_endpoint(db, monkeypatch, admin_client):
    monkeypatch.setattr(
        "services.donor._fetch_remote",
        lambda vk_id: {"is_don": True, "don_since": "2026-08-01T00:00:00"},
    )
    add_user(db, 123)
    res = admin_client.post("/api/admin/players/donor-sync")
    assert res.status_code == 200
    assert res.json()["synced"] >= 1
    row = db.query(DonorCache).filter(DonorCache.vk_id == 123).first()
    assert row is not None and row.is_don


def test_admin_donor_exempt_endpoint(db, admin_client):
    add_user(db, 402)
    res = admin_client.post("/api/admin/players/402/donor-exempt", json={"enabled": True})
    assert res.status_code == 200
    assert res.json()["donor_exempt"] is True
    u = db.query(User).filter(User.vk_id == 402).first()
    assert u.donor_exempt


def test_players_list_has_donor_flags(db, admin_client):
    add_donor(db, 403, True)
    add_user(db, 403)
    res = admin_client.get("/api/admin/players")
    assert res.status_code == 200
    row = next(p for p in res.json() if p["vk_id"] == 403)
    assert row["is_donor"] is True


def test_donor_sync_requires_admin(db, player_client):
    res = player_client.post("/api/admin/players/donor-sync")
    assert res.status_code == 403
