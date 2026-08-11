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
