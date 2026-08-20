from fastapi.security import HTTPAuthorizationCredentials
from types import SimpleNamespace

import config


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _req(method: str = "GET"):
    return SimpleNamespace(method=method)


def _no_names(vk_ids):
    return {}


def test_parse_vk_input_variants():
    from services.vk_names import parse_vk_input

    assert parse_vk_input("https://vk.ru/id795384") == ("id", 795384)
    assert parse_vk_input("https://vk.com/eugenibelovolov") == ("screen_name", "eugenibelovolov")
    assert parse_vk_input("https://m.vk.com/id123/") == ("id", 123)
    assert parse_vk_input("vk.ru/id42") == ("id", 42)
    assert parse_vk_input("795384") == ("id", 795384)
    assert parse_vk_input("id795384") == ("id", 795384)
    assert parse_vk_input("eugenibelovolov") == ("screen_name", "eugenibelovolov")
    assert parse_vk_input("") is None
    assert parse_vk_input("   ") is None
    assert parse_vk_input("https://vk.ru/") is None
    assert parse_vk_input("не ссылка!!!") is None


def test_session_blocks_stranger(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "9999"}})
    assert res.status_code == 403
    assert res.json()["detail"] == "Доступ к игре пока закрыт"


def test_session_allows_whitelisted_player(client, db, monkeypatch):
    from models import AllowedPlayer, User

    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    db.add(AllowedPlayer(vk_id=777))
    db.commit()

    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "777"}})
    assert res.status_code == 200
    body = res.json()
    assert body["vk_id"] == 777
    assert body["role"] == "player"
    assert body["token"]

    assert db.query(User).filter(User.vk_id == 777).first() is not None


def test_get_current_user_whitelisted_player(monkeypatch, db):
    from deps import get_current_user
    from models import AllowedPlayer, User
    from services.auth import create_access_token

    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    db.add(User(vk_id=777, role="player"))
    db.add(AllowedPlayer(vk_id=777))
    db.commit()

    user = get_current_user(_req(), _creds(create_access_token(777)), db)
    assert user.vk_id == 777


def test_whitelist_removal_does_not_revoke_logged_in_player(monkeypatch, db):
    from deps import get_current_user
    from models import AllowedPlayer, User
    from services.auth import create_access_token

    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    db.add(User(vk_id=777, role="player"))
    row = AllowedPlayer(vk_id=777)
    db.add(row)
    db.commit()

    token = create_access_token(777)
    assert get_current_user(_req(), _creds(token), db).vk_id == 777

    db.delete(row)
    db.commit()

    assert get_current_user(_req(), _creds(token), db).vk_id == 777


def test_session_consumes_invite(client, db, monkeypatch):
    from models import AllowedPlayer

    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    db.add(AllowedPlayer(vk_id=777))
    db.commit()

    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "777"}})
    assert res.status_code == 200

    assert db.query(AllowedPlayer).filter(AllowedPlayer.vk_id == 777).first() is None


def test_existing_player_logs_in_without_invite(client, db, monkeypatch):
    from models import User

    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    db.add(User(vk_id=777, role="player"))
    db.commit()

    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "777"}})
    assert res.status_code == 200
    assert res.json()["role"] == "player"


def test_admin_add_player_by_numeric_url(admin_client, db, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    res = admin_client.post("/api/admin/access/players", json={"link": "https://vk.ru/id777"})
    assert res.status_code == 201
    assert res.json()["vk_id"] == 777

    from models import AllowedPlayer
    row = db.query(AllowedPlayer).filter(AllowedPlayer.vk_id == 777).first()
    assert row is not None
    assert row.screen_name is None
    assert row.added_by == 400977


def test_admin_add_player_by_bare_id(admin_client, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    res = admin_client.post("/api/admin/access/players", json={"link": "778"})
    assert res.status_code == 201
    assert res.json()["vk_id"] == 778


def test_admin_add_player_by_id_prefixed(admin_client, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    res = admin_client.post("/api/admin/access/players", json={"link": "id777"})
    assert res.status_code == 201
    assert res.json()["vk_id"] == 777


def test_admin_add_player_by_named_link(admin_client, db, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    monkeypatch.setattr(
        "routes.admin_access.resolve_vk_screen_name",
        lambda name: {"id": 555, "first_name": "Евгений", "last_name": "Беловолов"},
    )
    res = admin_client.post("/api/admin/access/players", json={"link": "https://vk.ru/eugenibelovolov"})
    assert res.status_code == 201
    body = res.json()
    assert body["vk_id"] == 555
    assert body["screen_name"] == "eugenibelovolov"


def test_admin_add_player_named_link_unresolvable(admin_client, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    monkeypatch.setattr("routes.admin_access.resolve_vk_screen_name", lambda name: None)
    res = admin_client.post("/api/admin/access/players", json={"link": "https://vk.com/nosuchuser"})
    assert res.status_code == 400


def test_admin_add_player_invalid_link(admin_client, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    res = admin_client.post("/api/admin/access/players", json={"link": "кривая ссылка!!!"})
    assert res.status_code == 400


def test_admin_add_player_duplicate(admin_client, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    res = admin_client.post("/api/admin/access/players", json={"link": "777"})
    assert res.status_code == 201
    res = admin_client.post("/api/admin/access/players", json={"link": "https://vk.ru/id777"})
    assert res.status_code == 409


def test_admin_add_player_admin_rejected(admin_client, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    res = admin_client.post("/api/admin/access/players", json={"link": "400977"})
    assert res.status_code == 400


def test_admin_list_players(admin_client, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    admin_client.post("/api/admin/access/players", json={"link": "777"})
    res = admin_client.get("/api/admin/access/players")
    assert res.status_code == 200
    vk_ids = [r["vk_id"] for r in res.json()]
    assert 777 in vk_ids


def test_admin_delete_player(admin_client, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    admin_client.post("/api/admin/access/players", json={"link": "777"})
    res = admin_client.delete("/api/admin/access/players/777")
    assert res.status_code == 204
    res = admin_client.delete("/api/admin/access/players/777")
    assert res.status_code == 404


def test_admin_added_player_can_login(client, admin_client, monkeypatch):
    monkeypatch.setattr("routes.admin_access.resolve_vk_names", _no_names)
    monkeypatch.setattr(config, "ADMIN_ONLY", True)
    res = admin_client.post("/api/admin/access/players", json={"link": "777"})
    assert res.status_code == 201

    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "777"}})
    assert res.status_code == 200
    assert res.json()["role"] == "player"


def test_access_endpoints_forbidden_for_player(player_client, monkeypatch):
    res = player_client.get("/api/admin/access/players")
    assert res.status_code == 403
    res = player_client.post("/api/admin/access/players", json={"link": "777"})
    assert res.status_code == 403
    res = player_client.delete("/api/admin/access/players/777")
    assert res.status_code == 403
