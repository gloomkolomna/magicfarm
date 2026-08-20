from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from tests.conftest import TestingSessionLocal


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _req(method: str = "GET"):
    return SimpleNamespace(method=method)


def _seed_user(vk_id: int, role: str = "player", status: str = "active"):
    from models import User

    s = TestingSessionLocal()
    try:
        if s.query(User).filter(User.vk_id == vk_id).first() is None:
            s.add(User(vk_id=vk_id, role=role, status=status))
        s.commit()
    finally:
        s.close()


def _token(vk_id: int) -> str:
    from services.auth import create_access_token

    return create_access_token(vk_id)


@contextmanager
def token_client():
    from fastapi.testclient import TestClient
    from main import app
    from tests.conftest import _setup_app

    _setup_app(app)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_set_player_status_admin():
    _seed_user(400977, role="admin")
    _seed_user(123)
    with token_client() as c:
        for status in ("blocked", "active", "readonly"):
            res = c.post(
                f"/api/admin/players/123/status",
                json={"status": status},
                headers=_auth(_token(400977)),
            )
            assert res.status_code == 200
            assert res.json()["status"] == status


def test_set_player_status_validation():
    _seed_user(400977, role="admin")
    _seed_user(123)
    with token_client() as c:
        admin = _auth(_token(400977))
        res = c.post("/api/admin/players/123/status", json={"status": "hacked"}, headers=admin)
        assert res.status_code == 400

        res = c.post("/api/admin/players/999999/status", json={"status": "blocked"}, headers=admin)
        assert res.status_code == 404

        res = c.post("/api/admin/players/400977/status", json={"status": "blocked"}, headers=admin)
        assert res.status_code == 400


def test_set_player_status_forbidden_for_player():
    _seed_user(400977, role="admin")
    _seed_user(123)
    with token_client() as c:
        res = c.post(
            "/api/admin/players/123/status",
            json={"status": "blocked"},
            headers=_auth(_token(123)),
        )
        assert res.status_code == 403


def test_blocked_player_cannot_login(client, db, monkeypatch):
    from models import AllowedPlayer, User

    monkeypatch.setattr("config.ADMIN_ONLY", True)
    db.add(User(vk_id=777, role="player", status="blocked"))
    db.add(AllowedPlayer(vk_id=777))
    db.commit()

    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "777"}})
    assert res.status_code == 403
    assert res.json()["detail"] == "Аккаунт заблокирован"


def test_blocked_player_existing_token_rejected_then_unblocked(monkeypatch, db):
    from deps import get_current_user
    from models import User
    from services.auth import create_access_token

    monkeypatch.setattr("config.ADMIN_ONLY", False)
    db.add(User(vk_id=777, role="player", status="blocked"))
    db.commit()

    token = create_access_token(777)

    with pytest.raises(HTTPException) as exc:
        get_current_user(_req(), _creds(token), db)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Аккаунт заблокирован"

    u = db.query(User).filter(User.vk_id == 777).first()
    u.status = "active"
    db.commit()

    user = get_current_user(_req(), _creds(token), db)
    assert user.vk_id == 777


def test_readonly_player_can_view_but_not_act():
    _seed_user(400977, role="admin")
    _seed_user(123, status="readonly")
    with token_client() as c:
        headers = _auth(_token(123))

        res = c.get("/api/me", headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "readonly"

        res = c.post("/api/farm/plots/999999/invest", json={"amount": 10}, headers=headers)
        assert res.status_code == 403
        assert res.json()["detail"] == "Доступ закрыт: только просмотр"

        admin = _auth(_token(400977))
        res = c.post("/api/admin/players/123/status", json={"status": "active"}, headers=admin)
        assert res.status_code == 200

        res = c.post("/api/farm/plots/999999/invest", json={"amount": 10}, headers=headers)
        assert not (res.status_code == 403 and res.json().get("detail") == "Доступ закрыт: только просмотр")


def test_readonly_direct_method_check(monkeypatch, db):
    from deps import get_current_user
    from models import User
    from services.auth import create_access_token

    monkeypatch.setattr("config.ADMIN_ONLY", False)
    db.add(User(vk_id=778, role="player", status="readonly"))
    db.commit()
    token = create_access_token(778)

    assert get_current_user(_req("GET"), _creds(token), db).vk_id == 778
    with pytest.raises(HTTPException) as exc:
        get_current_user(_req("POST"), _creds(token), db)
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException):
        get_current_user(_req("DELETE"), _creds(token), db)


def test_admin_status_ignored_for_admin_role(monkeypatch, db):
    from deps import get_current_user
    from models import User
    from services.auth import create_access_token

    monkeypatch.setattr("config.ADMIN_ONLY", False)
    db.add(User(vk_id=400977, role="admin", status="blocked"))
    db.commit()
    token = create_access_token(400977)

    user = get_current_user(_req("POST"), _creds(token), db)
    assert user.vk_id == 400977


def test_delete_player_full():
    from models import AllowedPlayer, Plot, User, UserDlcUnlock

    _seed_user(400977, role="admin")
    _seed_user(123)
    s = TestingSessionLocal()
    s.add(Plot(user_id=123, plant_id=1, qty=1, required=100))
    s.add(UserDlcUnlock(user_id=123, location_code="infirmary"))
    s.add(AllowedPlayer(vk_id=123))
    s.commit()
    plot_id = s.query(Plot).filter(Plot.user_id == 123).first().id
    s.close()

    with token_client() as c:
        admin = _auth(_token(400977))
        res = c.delete("/api/admin/players/123", headers=admin)
        assert res.status_code == 204

        res = c.get("/api/admin/players/123", headers=admin)
        assert res.status_code == 404

        res = c.delete("/api/admin/players/123", headers=admin)
        assert res.status_code == 404

    s = TestingSessionLocal()
    assert s.query(User).filter(User.vk_id == 123).first() is None
    assert s.query(Plot).filter(Plot.id == plot_id).first() is None
    assert s.query(UserDlcUnlock).filter(UserDlcUnlock.user_id == 123).first() is None
    assert s.query(AllowedPlayer).filter(AllowedPlayer.vk_id == 123).first() is None
    s.close()


def test_delete_player_validation():
    _seed_user(400977, role="admin")
    _seed_user(123)
    with token_client() as c:
        admin = _auth(_token(400977))
        res = c.delete("/api/admin/players/400977", headers=admin)
        assert res.status_code == 400

        res = c.delete("/api/admin/players/999999", headers=admin)
        assert res.status_code == 404

        res = c.delete("/api/admin/players/123", headers=_auth(_token(123)))
        assert res.status_code == 403


def test_players_list_contains_status():
    _seed_user(400977, role="admin")
    _seed_user(123, status="readonly")
    with token_client() as c:
        res = c.get("/api/admin/players", headers=_auth(_token(400977)))
        assert res.status_code == 200
        row = next((p for p in res.json() if p["vk_id"] == 123), None)
        assert row is not None
        assert row["status"] == "readonly"
