from tests.conftest import make_user_client


def test_list_achievements_empty(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/achievements")
        assert r.status_code == 200
        assert r.json() == []


def test_admin_create_achievement(admin_client):
    r = admin_client.post("/api/admin/achievements", json={
        "code": "first_plant", "name": "Первое растение",
        "condition_kind": "plant_count", "condition_value": 1,
    })
    assert r.status_code == 201
    assert r.json()["code"] == "first_plant"
    assert r.json()["earned"] is False


def test_admin_list_achievements(admin_client):
    admin_client.post("/api/admin/achievements", json={
        "code": "first_plant", "name": "Первое растение",
        "condition_kind": "plant_count", "condition_value": 1,
    })
    r = admin_client.get("/api/admin/achievements")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_admin_update_achievement(admin_client):
    r = admin_client.post("/api/admin/achievements", json={
        "code": "first_plant", "name": "Первое растение",
        "condition_kind": "plant_count", "condition_value": 1,
    })
    aid = r.json()["id"]
    r = admin_client.put(f"/api/admin/achievements/{aid}", json={
        "code": "first_plant", "name": "Первая посадка",
        "condition_kind": "plant_count", "condition_value": 1,
    })
    assert r.status_code == 200
    assert r.json()["name"] == "Первая посадка"


def test_admin_delete_achievement(admin_client):
    r = admin_client.post("/api/admin/achievements", json={
        "code": "first_plant", "name": "Первое растение",
        "condition_kind": "plant_count", "condition_value": 1,
    })
    aid = r.json()["id"]
    r = admin_client.delete(f"/api/admin/achievements/{aid}")
    assert r.status_code == 204


def test_achievement_duplicate_code(admin_client):
    admin_client.post("/api/admin/achievements", json={
        "code": "first_plant", "name": "Первое растение",
        "condition_kind": "plant_count", "condition_value": 1,
    })
    r = admin_client.post("/api/admin/achievements", json={
        "code": "first_plant", "name": "Дубль",
        "condition_kind": "plant_count", "condition_value": 1,
    })
    assert r.status_code == 409


def test_player_forbidden(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/admin/achievements", json={
            "code": "x", "name": "X", "condition_kind": "x",
        })
        assert r.status_code == 403
