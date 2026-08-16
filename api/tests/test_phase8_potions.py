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


def test_active_cauldron_none(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/potions/cauldrons/active")
        assert r.status_code == 200
        assert r.json() is None


def test_active_cauldron_returns_created(admin_client):
    with make_user_client(123, "player") as c:
        c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        r = c.get("/api/potions/cauldrons/active")
        assert r.status_code == 200
        assert r.json()["recipe_id"] == 1
        assert r.json()["status"] == "empty"
        assert len(r.json()["slots"]) == 4


def test_active_cauldron_null_after_brew(admin_client):
    _seed_plant_inventory(123, 1, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        for i in range(3):
            c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/brew")
        r = c.get("/api/potions/cauldrons/active")
        assert r.status_code == 200
        assert r.json() is None


def test_active_cauldron_requires_auth(client):
    r = client.get("/api/potions/cauldrons/active")
    assert r.status_code == 401


def test_active_cauldron_isolated_between_players(admin_client):
    with make_user_client(123, "player") as c:
        c.post("/api/potions/cauldrons", json={"recipe_id": 1})
    with make_user_client(124, "player") as c:
        r = c.get("/api/potions/cauldrons/active")
        assert r.status_code == 200
        assert r.json() is None


_recipe_seq = 0


def _seed_recipe(name: str, slots: list[str]) -> int:
    import json
    from models import PotionRecipe
    from tests.conftest import TestingSessionLocal
    global _recipe_seq
    _recipe_seq += 1
    s = TestingSessionLocal()
    try:
        r = PotionRecipe(
            code=f"test_auto_{_recipe_seq}", name=name, level="green",
            ingredient_slots=json.dumps(slots), bonus_code=None, reward_coins=100,
        )
        s.add(r)
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def _seed_catalog_extras() -> dict:
    from models import Plant, Product
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        apple = Plant(code="apple_tree_t", name="Яблоня", emoji="🍎",
                      category="orchard", level=1, norm_per_crystal=100)
        dragon = Product(code="dragon_scale_t", name="Чешуя дракона", emoji="🐉",
                         stars=1, production_kind="barnyard", animal_id=1)
        vial = Product(code="vial_t", name="Фиал", emoji="⚗️",
                       stars=1, production_kind="shatyor_zelevareniya")
        mantle = Product(code="mantle_t", name="Мантия", emoji="🧥",
                         stars=1, production_kind="shatyor_masterskaya")
        amulet = Product(code="amulet_t", name="Амулет", emoji="📿",
                         stars=1, production_kind="shatyor_masterskaya_3")
        for obj in (apple, dragon, vial, mantle, amulet):
            s.add(obj)
        s.commit()
        for obj in (apple, dragon, vial, mantle, amulet):
            s.refresh(obj)
        return {
            "apple": apple.id, "dragon": dragon.id, "vial": vial.id,
            "mantle": mantle.id, "amulet": amulet.id,
        }
    finally:
        s.close()


def _make_cauldron(c, slots: list[str]) -> int:
    rid = _seed_recipe("Тестовое зелье", slots)
    r = c.post("/api/potions/cauldrons", json={"recipe_id": rid})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_slot_warehouse_animal_product(admin_client):
    ids = _seed_catalog_extras()
    _seed_plant_inventory(123, 1, 5)
    _seed_product_inventory(123, 1, 5)
    _seed_product_inventory(123, ids["dragon"], 3)
    with make_user_client(123, "player") as c:
        cid = _make_cauldron(c, ["animal_product"])
        r = c.get(f"/api/potions/cauldrons/{cid}/slot/0/warehouse")
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 1
        assert items[0]["item_id"] == ids["dragon"]
        assert items[0]["item_kind"] == "product"
        assert items[0]["item_emoji"] == "🐉"


def test_slot_warehouse_real_production_kinds(admin_client):
    ids = _seed_catalog_extras()
    _seed_product_inventory(123, ids["vial"], 2)
    _seed_product_inventory(123, ids["mantle"], 2)
    _seed_product_inventory(123, ids["amulet"], 2)
    _seed_product_inventory(123, ids["dragon"], 2)
    with make_user_client(123, "player") as c:
        cid = _make_cauldron(c, ["workshop", "sewing", "alchemy", "barnyard"])
        w = c.get(f"/api/potions/cauldrons/{cid}/slot/0/warehouse").json()
        assert [i["item_id"] for i in w] == [ids["amulet"]]
        w = c.get(f"/api/potions/cauldrons/{cid}/slot/1/warehouse").json()
        assert [i["item_id"] for i in w] == [ids["mantle"]]
        w = c.get(f"/api/potions/cauldrons/{cid}/slot/2/warehouse").json()
        assert [i["item_id"] for i in w] == [ids["vial"]]
        w = c.get(f"/api/potions/cauldrons/{cid}/slot/3/warehouse").json()
        assert [i["item_id"] for i in w] == [ids["dragon"]]


def test_slot_warehouse_plant_categories(admin_client):
    ids = _seed_catalog_extras()
    _seed_plant_inventory(123, 1, 5)
    _seed_plant_inventory(123, ids["apple"], 5)
    with make_user_client(123, "player") as c:
        cid = _make_cauldron(c, ["plant_garden", "plant_orchard"])
        w = c.get(f"/api/potions/cauldrons/{cid}/slot/0/warehouse").json()
        assert [i["item_id"] for i in w] == [1]
        w = c.get(f"/api/potions/cauldrons/{cid}/slot/1/warehouse").json()
        assert [i["item_id"] for i in w] == [ids["apple"]]


def test_fill_slot_rejects_wrong_type(admin_client):
    ids = _seed_catalog_extras()
    _seed_plant_inventory(123, 1, 5)
    _seed_product_inventory(123, 1, 5)
    _seed_product_inventory(123, ids["dragon"], 3)
    with make_user_client(123, "player") as c:
        cid = _make_cauldron(c, ["animal_product"])
        r = c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={"item_kind": "plant", "item_id": 1})
        assert r.status_code == 400
        r = c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={"item_kind": "product", "item_id": 1})
        assert r.status_code == 400
        r = c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={"item_kind": "product", "item_id": ids["dragon"]})
        assert r.status_code == 200
        assert r.json()["slots"][0]["item_id"] == ids["dragon"]


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


def _img_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (30, 30), (90, 60, 200)).save(buf, format="PNG")
    return buf.getvalue()


def test_admin_create_with_description(admin_client):
    res = admin_client.post("/api/admin/potion-recipes", json={
        "name": "Эликсир дождя",
        "level": "green",
        "ingredient_slots": ["plant_garden"],
        "bonus_code": "double_garden_harvest",
        "reward_coins": 120,
        "description": "Удваивает урожай с одной грядки при сборе.",
    })
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["description"] == "Удваивает урожай с одной грядки при сборе."

    res2 = admin_client.put(f"/api/admin/potion-recipes/{data['id']}", json={
        "name": "Эликсир дождя",
        "level": "green",
        "ingredient_slots": ["plant_garden"],
        "bonus_code": "double_garden_harvest",
        "reward_coins": 130,
        "description": "Обновлённое описание.",
    })
    assert res2.status_code == 200
    assert res2.json()["description"] == "Обновлённое описание."


def test_upload_potion_image_admin(admin_client, uploads_tmp):
    res = admin_client.put(
        "/api/admin/potion-recipes/1/image",
        files={"image": ("p.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert res.status_code == 200
    assert res.json()["image_url"] is not None


def test_upload_potion_image_requires_admin(player_client, uploads_tmp):
    denied = player_client.put(
        "/api/admin/potion-recipes/1/image",
        files={"image": ("p.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert denied.status_code == 403


def test_user_potion_shows_bonus_description(admin_client, uploads_tmp):
    admin_client.put("/api/admin/potion-recipes/1", json={
        "name": "Сонное пророчество",
        "level": "green",
        "ingredient_slots": ["plant_garden", "plant_garden", "plant_garden", "alchemy"],
        "bonus_code": "skip_plant_stitch",
        "reward_coins": 100,
        "description": "Позволяет вырастить растение без вышивки нормы.",
    })
    admin_client.put(
        "/api/admin/potion-recipes/1/image",
        files={"image": ("p.png", io.BytesIO(_img_bytes()), "image/png")},
    )

    _seed_plant_inventory(123, 1, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        for i in range(3):
            c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/brew")

        potions = c.get("/api/potions").json()
        assert len(potions) == 1
        p = potions[0]
        assert p["bonus_description"] == "Растение без отшива нормы"
        assert p["description"] == "Позволяет вырастить растение без вышивки нормы."
        assert p["image_url"] is not None

        recipes = c.get("/api/potions/recipes").json()
        rec = [r2 for r2 in recipes if r2["id"] == 1][0]
        assert rec["description"] == "Позволяет вырастить растение без вышивки нормы."
        assert rec["image_url"] is not None
