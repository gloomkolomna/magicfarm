import json

from tests.conftest import TestingSessionLocal, make_user_client


def _seed_recipe(level: str, name: str, slots: list[str]) -> int:
    from models import PotionRecipe
    s = TestingSessionLocal()
    try:
        r = PotionRecipe(
            code=f"gating_{name.lower()}", name=name, level=level,
            ingredient_slots=json.dumps(slots), bonus_code=None, reward_coins=100,
        )
        s.add(r)
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def _seed_plant_inventory(vk_id: int, plant_id: int, qty: int):
    from models import Inventory
    s = TestingSessionLocal()
    try:
        inv = s.query(Inventory).filter(
            Inventory.user_id == vk_id, Inventory.plant_id == plant_id
        ).first()
        if inv is None:
            s.add(Inventory(user_id=vk_id, plant_id=plant_id, qty=qty))
            s.commit()
    finally:
        s.close()


def _seed_product_inventory(vk_id: int, product_id: int, qty: int):
    from models import Inventory
    s = TestingSessionLocal()
    try:
        inv = s.query(Inventory).filter(
            Inventory.user_id == vk_id, Inventory.product_id == product_id
        ).first()
        if inv is None:
            s.add(Inventory(user_id=vk_id, product_id=product_id, qty=qty))
            s.commit()
    finally:
        s.close()


def _brew_green(c):
    for pid in (1, 2, 3):
        _seed_plant_inventory(123, pid, 5)
    _seed_product_inventory(123, 1, 5)
    r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for i, pid in enumerate((1, 2, 3)):
        rr = c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": pid})
        assert rr.status_code == 200, rr.text
    rr = c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
    assert rr.status_code == 200, rr.text
    rr = c.post(f"/api/potions/cauldrons/{cid}/brew")
    assert rr.status_code == 200, rr.text


def _brew_blue(c, blue_id: int):
    for pid in (1, 2, 3, 4):
        _seed_plant_inventory(123, pid, 5)
    _seed_product_inventory(123, 1, 5)
    r = c.post("/api/potions/cauldrons", json={"recipe_id": blue_id})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for i, pid in enumerate((1, 2, 3, 4)):
        rr = c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": pid})
        assert rr.status_code == 200, rr.text
    rr = c.post(f"/api/potions/cauldrons/{cid}/slot/4", json={"item_kind": "product", "item_id": 1})
    assert rr.status_code == 200, rr.text
    rr = c.post(f"/api/potions/cauldrons/{cid}/brew")
    assert rr.status_code == 200, rr.text


def test_blue_and_violet_locked_for_new_player(admin_client):
    blue_id = _seed_recipe("blue", "Среднее зелье", ["plant_garden"] * 4 + ["alchemy"])
    violet_id = _seed_recipe("violet", "Сложное зелье", ["plant_garden"] * 5 + ["alchemy"])
    with make_user_client(123, "player") as c:
        recipes = {r["id"]: r for r in c.get("/api/potions/recipes").json()}
        assert recipes[1]["unlocked"] is True
        assert recipes[blue_id]["unlocked"] is False
        assert recipes[violet_id]["unlocked"] is False

        r = c.post("/api/potions/cauldrons", json={"recipe_id": blue_id})
        assert r.status_code == 403
        assert "предыдущего уровня" in r.json()["detail"]
        r = c.post("/api/potions/cauldrons", json={"recipe_id": violet_id})
        assert r.status_code == 403


def test_green_always_unlocked_for_new_player(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        assert r.status_code == 201, r.text


def test_blue_unlocks_after_brewing_all_green(admin_client):
    blue_id = _seed_recipe("blue", "Среднее зелье", ["plant_garden"] * 4 + ["alchemy"])
    violet_id = _seed_recipe("violet", "Сложное зелье", ["plant_garden"] * 5 + ["alchemy"])
    with make_user_client(123, "player") as c:
        _brew_green(c)
        recipes = {r["id"]: r for r in c.get("/api/potions/recipes").json()}
        assert recipes[blue_id]["unlocked"] is True
        assert recipes[violet_id]["unlocked"] is False

        r = c.post("/api/potions/cauldrons", json={"recipe_id": blue_id})
        assert r.status_code == 201, r.text
        r = c.post("/api/potions/cauldrons", json={"recipe_id": violet_id})
        assert r.status_code == 403


def test_violet_unlocks_after_brewing_all_blue(admin_client):
    blue_id = _seed_recipe("blue", "Среднее зелье", ["plant_garden"] * 4 + ["alchemy"])
    violet_id = _seed_recipe("violet", "Сложное зелье", ["plant_garden"] * 5 + ["alchemy"])
    with make_user_client(123, "player") as c:
        _brew_green(c)
        _brew_blue(c, blue_id)
        recipes = {r["id"]: r for r in c.get("/api/potions/recipes").json()}
        assert recipes[violet_id]["unlocked"] is True

        r = c.post("/api/potions/cauldrons", json={"recipe_id": violet_id})
        assert r.status_code == 201, r.text
