def test_session_dev_mode_admin(client):
    # В dev-режиме подпись VK не проверяется, доверяем vk_user_id.
    # vk_id из ADMIN_VK_IDS (400977) → роль admin.
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "400977"}})
    assert res.status_code == 200
    data = res.json()
    assert data["vk_id"] == 400977
    assert data["role"] == "admin"
    assert isinstance(data["token"], str) and len(data["token"]) > 0


def test_session_dev_mode_player(client):
    # Случайный vk_id → роль player.
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "999999"}})
    assert res.status_code == 200
    data = res.json()
    assert data["vk_id"] == 999999
    assert data["role"] == "player"


def test_session_second_admin(client):
    # Второй ID из ADMIN_VK_IDS (795384) → тоже admin.
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "795384"}})
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


def test_session_missing_vk_user_id(client):
    res = client.post("/api/auth/session", json={"params": {}})
    assert res.status_code == 401


def test_session_admin_promotion_on_relogin(client):
    # Игрок зашёл как player, затем его vk_id добавили в ADMIN_VK_IDS —
    # при повторном логине роль должна повыситься до admin.
    client.post("/api/auth/session", json={"params": {"vk_user_id": "400977"}})
    res = client.post("/api/auth/session", json={"params": {"vk_user_id": "400977"}})
    assert res.json()["role"] == "admin"


def _make_sign(params: dict, secret: str = "test-secret") -> str:
    import base64
    import hashlib
    import hmac

    vk_pairs = sorted(
        (k, v) for k, v in params.items() if k.startswith("vk_") and k != "sign"
    )
    query = "&".join(f"{k}={v}" for k, v in vk_pairs)
    digest = hmac.new(secret.encode(), query.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def test_session_real_sign_ok(client, monkeypatch):
    # Прод-режим: подпись VK проверяется по-настоящему.
    # VK передаёт sign в формате base64url (без padding).
    import config

    monkeypatch.setattr(config, "DEV_LOGIN_ENABLED", False)

    params = {
        "vk_access_token_settings": "",
        "vk_app_id": "54712760",
        "vk_are_notifications_enabled": "0",
        "vk_is_app_user": "1",
        "vk_is_favorite": "0",
        "vk_language": "ru",
        "vk_platform": "desktop_web",
        "vk_ref": "other",
        "vk_ts": "1786560930",
        "vk_user_id": "400977",
    }
    params["sign"] = _make_sign(params)
    res = client.post("/api/auth/session", json={"params": params})
    assert res.status_code == 200
    assert res.json()["vk_id"] == 400977
    assert res.json()["role"] == "admin"


def test_session_real_sign_tampered(client, monkeypatch):
    import config

    monkeypatch.setattr(config, "DEV_LOGIN_ENABLED", False)

    params = {
        "vk_app_id": "54712760",
        "vk_user_id": "400977",
    }
    params["sign"] = "NGZ_GR5_ffqDy8C_obMgtDaPVzMUBVOavWb5PaR_cAY"
    res = client.post("/api/auth/session", json={"params": params})
    assert res.status_code == 401


def test_session_real_sign_missing(client, monkeypatch):
    import config

    monkeypatch.setattr(config, "DEV_LOGIN_ENABLED", False)

    params = {"vk_app_id": "54712760", "vk_user_id": "400977"}
    res = client.post("/api/auth/session", json={"params": params})
    assert res.status_code == 401
