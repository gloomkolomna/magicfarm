import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from types import SimpleNamespace

import config


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _req(method: str = "GET"):
    return SimpleNamespace(method=method)


def test_admin_only_login_blocks_player(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "999"}})
    assert res.status_code == 403


def test_admin_only_login_allows_admin(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "400977"}})
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


def test_get_current_user_blocks_player(monkeypatch, db):
    from deps import get_current_user
    from models import User
    from services.auth import create_access_token

    db.add(User(vk_id=424242, role="player"))
    db.commit()

    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    token = create_access_token(424242)

    with pytest.raises(HTTPException) as exc:
        get_current_user(_req(), _creds(token), db)
    assert exc.value.status_code == 403


def test_get_current_user_allows_admin(monkeypatch, db):
    from deps import get_current_user
    from models import User
    from services.auth import create_access_token

    db.add(User(vk_id=400977, role="admin"))
    db.commit()

    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    token = create_access_token(400977)

    user = get_current_user(_req(), _creds(token), db)
    assert user.vk_id == 400977


def test_get_current_user_off_allows_player(monkeypatch, db):
    from deps import get_current_user
    from models import User
    from services.auth import create_access_token

    db.add(User(vk_id=424242, role="player"))
    db.commit()

    monkeypatch.setattr(config, "ADMIN_ONLY", False)
    token = create_access_token(424242)

    user = get_current_user(_req(), _creds(token), db)
    assert user.vk_id == 424242
