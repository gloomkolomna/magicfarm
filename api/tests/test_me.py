def test_me_requires_auth(client):
    res = client.get("/api/me")
    assert res.status_code == 401


def test_me_admin(admin_client):
    res = admin_client.get("/api/me")
    assert res.status_code == 200
    data = res.json()
    assert data["vk_id"] == 400977
    assert data["role"] == "admin"
    assert data["crosses_balance"] == 0
    assert data["crosses_total"] == 0
    assert data["coins"] == 0
    assert data["round"] == 1
    assert data["onboarding_done"] is True


def test_me_player(player_client):
    res = player_client.get("/api/me")
    assert res.status_code == 200
    data = res.json()
    assert data["vk_id"] == 123
    assert data["role"] == "player"
    assert data["crosses_balance"] == 0
    assert data["round"] == 1
    assert data["onboarding_done"] is True


def test_me_onboarding_false_for_new_user():
    from tests.conftest import make_user_client_no_onboarding
    with make_user_client_no_onboarding(321, "player") as c:
        data = c.get("/api/me").json()
    assert data["onboarding_done"] is False
