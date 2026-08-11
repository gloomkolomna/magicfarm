import io

from tests.conftest import make_user_client


def _seed_plant_inventory(vk_id: int, plant_id: int, qty: int):
    from models import Inventory
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        inv = Inventory(user_id=vk_id, plant_id=plant_id, qty=qty)
        s.add(inv)
        s.commit()
    finally:
        s.close()


def _seed_product_inventory(vk_id: int, product_id: int, qty: int):
    from models import Inventory
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        inv = Inventory(user_id=vk_id, product_id=product_id, qty=qty)
        s.add(inv)
        s.commit()
    finally:
        s.close()


def test_list_recipes(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/potions/recipes")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["name"] == "Сонное пророчество"


def test_create_cauldron(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        assert r.status_code == 201
        data = r.json()
        assert data["recipe_id"] == 1
        assert data["status"] == "empty"
        assert data["capacity"] == 4
        assert len(data["slots"]) == 4


def test_cauldron_conflict(admin_client):
    with make_user_client(123, "player") as c:
        c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        assert r.status_code == 409


def test_fill_slot(admin_client):
    _seed_plant_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        r = c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={
            "item_kind": "plant", "item_id": 1,
        })
        assert r.status_code == 200
        assert r.json()["slots"][0]["item_id"] == 1
        assert r.json()["status"] == "filling"


def test_clear_slot(admin_client):
    _seed_plant_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={"item_kind": "plant", "item_id": 1})
        r = c.delete(f"/api/potions/cauldrons/{cid}/slot/0")
        assert r.status_code == 200
        assert r.json()["slots"][0]["item_id"] is None
        assert r.json()["status"] == "empty"


def test_brew(admin_client):
    _seed_plant_inventory(123, 1, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/1", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/2", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
        r = c.post(f"/api/potions/cauldrons/{cid}/brew")
        assert r.status_code == 200
        assert r.json()["status"] == "done"


def test_user_potions(admin_client):
    _seed_plant_inventory(123, 1, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/1", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/2", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/brew")
        r = c.get("/api/potions")
        assert len(r.json()) == 1
        assert r.json()[0]["bonus_code"] == "skip_plant_stitch"
        assert r.json()[0]["activated"] is False


def test_activate_potion(admin_client):
    _seed_plant_inventory(123, 1, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/1", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/2", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/brew")
        potions = c.get("/api/potions").json()
        pid = potions[0]["id"]
        r = c.post(f"/api/potions/{pid}/activate")
        assert r.status_code == 200
        assert r.json()["activated"] is True


def test_admin_crud_recipes(admin_client):
    r = admin_client.get("/api/admin/potion-recipes")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = admin_client.post("/api/admin/potion-recipes", json={
        "name": "Зелье силы", "level": "green",
        "ingredient_slots": ["plant_garden", "workshop"],
        "bonus_code": "double_garden_harvest", "reward_coins": 100,
    })
    assert r.status_code == 201
    rid = r.json()["id"]

    r = admin_client.put(f"/api/admin/potion-recipes/{rid}", json={
        "name": "Зелье мощи", "level": "blue",
        "ingredient_slots": ["plant_garden", "workshop", "sewing"],
        "bonus_code": "double_garden_harvest", "reward_coins": 150,
    })
    assert r.status_code == 200

    r = admin_client.delete(f"/api/admin/potion-recipes/{rid}")
    assert r.status_code == 204


def test_admin_player_forbidden(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/admin/potion-recipes")
        assert r.status_code == 403
