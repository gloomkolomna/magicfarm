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


def test_cauldron_returns_zone_image(admin_client):
    from models import BreweryZone, Field
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        f = Field(code="brew_field_test", name="Зельеварня", cols=3, rows=2, field_kind="brewery")
        s.add(f)
        s.flush()
        s.add(BreweryZone(field_id=f.id, zone_kind="cauldron", col1=0, row1=0, col2=1, row2=1,
                          image_url="/api/uploads/cauldron.png"))
        s.commit()
        fid = f.id
    finally:
        s.close()

    r = admin_client.put(f"/api/admin/fields/{fid}/potion-recipes", json={"recipe_ids": [1]})
    assert r.status_code == 200, r.text

    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        assert r.status_code == 201, r.text
        assert r.json()["image_url"] == "/api/uploads/cauldron.png"
        r = c.get("/api/potions/cauldrons/active")
        assert r.status_code == 200
        assert r.json()[0]["image_url"] == "/api/uploads/cauldron.png"


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


def test_fill_slot_returns_item_details(admin_client):
    _seed_plant_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        assert r.json()["slots"][1]["item_name"] is None
        r = c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={"item_kind": "plant", "item_id": 1})
        assert r.status_code == 200
        slot = r.json()["slots"][0]
        assert slot["item_id"] == 1
        assert slot["item_name"]
        assert slot["item_emoji"]
        assert "item_image" in slot


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
    for pid in (1, 2, 3):
        _seed_plant_inventory(123, pid, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        for i, pid in enumerate((1, 2, 3)):
            c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": pid})
        c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
        r = c.post(f"/api/potions/cauldrons/{cid}/brew")
        assert r.status_code == 200
        assert r.json()["status"] == "done"


def test_user_potions(admin_client):
    for pid in (1, 2, 3):
        _seed_plant_inventory(123, pid, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        for i, pid in enumerate((1, 2, 3)):
            c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": pid})
        c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/brew")
        r = c.get("/api/potions")
        assert len(r.json()) == 1
        assert r.json()[0]["bonus_code"] == "skip_plant_stitch"
        assert r.json()[0]["activated"] is False


def test_activate_potion(admin_client):
    for pid in (1, 2, 3):
        _seed_plant_inventory(123, pid, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        for i, pid in enumerate((1, 2, 3)):
            c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": pid})
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
        assert r.json() == []


def test_active_cauldron_returns_created(admin_client):
    with make_user_client(123, "player") as c:
        c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        r = c.get("/api/potions/cauldrons/active")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) == 1
        assert r.json()[0]["recipe_id"] == 1
        assert r.json()[0]["status"] == "empty"
        assert len(r.json()[0]["slots"]) == 4


def test_active_cauldron_null_after_brew(admin_client):
    for pid in (1, 2, 3):
        _seed_plant_inventory(123, pid, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        for i, pid in enumerate((1, 2, 3)):
            c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": pid})
        c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/brew")
        r = c.get("/api/potions/cauldrons/active")
        assert r.status_code == 200
        assert r.json() == []


def test_active_cauldron_requires_auth(client):
    r = client.get("/api/potions/cauldrons/active")
    assert r.status_code == 401


def test_active_cauldron_isolated_between_players(admin_client):
    with make_user_client(123, "player") as c:
        c.post("/api/potions/cauldrons", json={"recipe_id": 1})
    with make_user_client(124, "player") as c:
        r = c.get("/api/potions/cauldrons/active")
        assert r.status_code == 200
        assert r.json() == []


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
        egg = Product(code="sweet_egg_t", name="Сладкое яйцо", emoji="🥚",
                      stars=1, production_kind="barnyard", animal_id=2)
        vial = Product(code="vial_t", name="Фиал", emoji="⚗️",
                       stars=1, production_kind="shatyor_zelevareniya")
        mantle = Product(code="mantle_t", name="Мантия", emoji="🧥",
                         stars=1, production_kind="shatyor_masterskaya")
        amulet = Product(code="amulet_t", name="Амулет", emoji="📿",
                         stars=1, production_kind="shatyor_masterskaya_3")
        for obj in (apple, dragon, egg, vial, mantle, amulet):
            s.add(obj)
        s.commit()
        for obj in (apple, dragon, egg, vial, mantle, amulet):
            s.refresh(obj)
        return {
            "apple": apple.id, "dragon": dragon.id, "egg": egg.id, "vial": vial.id,
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


def test_slot_warehouse_item_images(admin_client):
    from models import Plant as PlantModel, Product as ProductModel
    from tests.conftest import TestingSessionLocal
    ids = _seed_catalog_extras()
    s = TestingSessionLocal()
    try:
        dragon = s.query(ProductModel).filter(ProductModel.id == ids["dragon"]).first()
        dragon.image_url = "/api/uploads/dragon.png"
        plant = s.query(PlantModel).filter(PlantModel.id == 1).first()
        plant.image_harvested_url = "/api/uploads/jack_harvested.png"
        s.commit()
    finally:
        s.close()
    _seed_plant_inventory(123, 1, 5)
    _seed_product_inventory(123, ids["dragon"], 3)
    with make_user_client(123, "player") as c:
        cid = _make_cauldron(c, ["plant_garden", "animal_product"])
        w = c.get(f"/api/potions/cauldrons/{cid}/slot/0/warehouse").json()
        assert [i["item_image"] for i in w] == ["/api/uploads/jack_harvested.png"]
        w = c.get(f"/api/potions/cauldrons/{cid}/slot/1/warehouse").json()
        assert [i["item_image"] for i in w] == ["/api/uploads/dragon.png"]

        products = c.get("/api/farm/products").json()
        dragon_out = next(p for p in products if p["id"] == ids["dragon"])
        assert dragon_out["image_url"] == "/api/uploads/dragon.png"


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


def test_fill_slot_rejects_duplicate_item(admin_client):
    ids = _seed_catalog_extras()
    _seed_plant_inventory(123, 1, 5)
    _seed_plant_inventory(123, 2, 5)
    _seed_product_inventory(123, ids["dragon"], 3)
    _seed_product_inventory(123, ids["egg"], 3)
    with make_user_client(123, "player") as c:
        cid = _make_cauldron(c, ["plant_garden", "plant_garden", "animal_product", "animal_product"])
        assert c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={"item_kind": "plant", "item_id": 1}).status_code == 200
        r = c.post(f"/api/potions/cauldrons/{cid}/slot/1", json={"item_kind": "plant", "item_id": 1})
        assert r.status_code == 400
        assert "уже заложен" in r.json()["detail"]
        assert c.post(f"/api/potions/cauldrons/{cid}/slot/1", json={"item_kind": "plant", "item_id": 2}).status_code == 200

        assert c.post(f"/api/potions/cauldrons/{cid}/slot/2", json={"item_kind": "product", "item_id": ids["dragon"]}).status_code == 200
        r = c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": ids["dragon"]})
        assert r.status_code == 400

        w = c.get(f"/api/potions/cauldrons/{cid}/slot/3/warehouse").json()
        assert [i["item_id"] for i in w] == [ids["egg"]]


def test_warehouse_excludes_used_items(admin_client):
    _seed_plant_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        cid = _make_cauldron(c, ["plant_garden", "plant_garden"])
        assert c.post(f"/api/potions/cauldrons/{cid}/slot/0", json={"item_kind": "plant", "item_id": 1}).status_code == 200
        w = c.get(f"/api/potions/cauldrons/{cid}/slot/1/warehouse").json()
        assert w == []
        r = c.delete(f"/api/potions/cauldrons/{cid}/slot/0")
        assert r.status_code == 200
        w = c.get(f"/api/potions/cauldrons/{cid}/slot/1/warehouse").json()
        assert [i["item_id"] for i in w] == [1]


def test_brewed_potion_appears_in_inventory(admin_client):
    for pid in (1, 2, 3):
        _seed_plant_inventory(123, pid, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        inv = c.get("/api/farm/inventory").json()
        assert not any(i["item_kind"] == "potion" for i in inv)

        cid = _make_cauldron(c, ["plant_garden", "plant_garden", "plant_garden", "alchemy"])
        for i, pid in enumerate((1, 2, 3)):
            c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": pid})
        c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
        assert c.post(f"/api/potions/cauldrons/{cid}/brew").status_code == 200

        inv = c.get("/api/farm/inventory").json()
        potions = [i for i in inv if i["item_kind"] == "potion"]
        assert len(potions) == 1
        assert potions[0]["item_kind"] == "potion"
        assert potions[0]["item_code"].startswith("test_auto_")
        assert potions[0]["item_name"] == "Тестовое зелье"
        assert potions[0]["qty"] == 1

        only_potions = c.get("/api/farm/inventory?item_kind=potion").json()
        assert [i["item_kind"] for i in only_potions] == ["potion"]
        plants = c.get("/api/farm/inventory?item_kind=plant").json()
        assert not any(i["item_kind"] == "potion" for i in plants)


def test_rebrew_after_use_restores_potion(admin_client):
    for pid in (1, 2, 3):
        _seed_plant_inventory(123, pid, 10)
    _seed_product_inventory(123, 1, 10)
    rid = _seed_recipe("Зелье переварки", ["plant_garden", "plant_garden", "plant_garden", "alchemy"])

    def brew(c):
        cid = c.post("/api/potions/cauldrons", json={"recipe_id": rid}).json()["id"]
        for i, pid in enumerate((1, 2, 3)):
            assert c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={
                "item_kind": "plant", "item_id": pid,
            }).status_code == 200
        assert c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={
            "item_kind": "product", "item_id": 1,
        }).status_code == 200
        assert c.post(f"/api/potions/cauldrons/{cid}/brew").status_code == 200

    with make_user_client(123, "player") as c:
        brew(c)
        potions = c.get("/api/potions").json()
        assert len(potions) == 1
        assert potions[0]["used"] is False

        from models import UserPotion
        from tests.conftest import TestingSessionLocal
        s = TestingSessionLocal()
        try:
            up = s.query(UserPotion).filter(UserPotion.user_id == 123).first()
            up.used = True
            s.commit()
        finally:
            s.close()

        inv = c.get("/api/farm/inventory").json()
        assert not any(i["item_kind"] == "potion" for i in inv)

        brew(c)

        potions = c.get("/api/potions").json()
        assert len(potions) == 2
        unused = [p for p in potions if not p["used"]]
        assert len(unused) == 1

        potions_inv = [i for i in c.get("/api/farm/inventory").json() if i["item_kind"] == "potion"]
        assert len(potions_inv) == 1
        assert potions_inv[0]["qty"] == 1


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

    for pid in (1, 2, 3):
        _seed_plant_inventory(123, pid, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        cid = r.json()["id"]
        for i, pid in enumerate((1, 2, 3)):
            c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": pid})
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


# ── Бонусы зелий: каталог, активация и эффекты ──

def _seed_potion(vk_id: int, bonus_code: str, activated: bool = False, used: bool = False, recipe_id: int = 1) -> int:
    from models import UserPotion
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        up = UserPotion(user_id=vk_id, potion_recipe_id=recipe_id, bonus_code=bonus_code,
                        activated=activated, used=used)
        s.add(up)
        s.commit()
        s.refresh(up)
        return up.id
    finally:
        s.close()


def _field_with_bed(admin_client):
    r = admin_client.post("/api/admin/fields", json={"name": "Поле бонусов", "code": "test_bonus", "cols": 3, "rows": 2})
    assert r.status_code == 201
    fid = r.json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/cells/blocked", json={"cells": [{"col": 1, "row": 1}], "kind": "bed"})
    admin_client.put(f"/api/admin/fields/{fid}/plants", json={"plant_ids": [1]})
    return fid


def _credit(c, amount):
    c.post("/api/stitches/reports", data={"amount": str(amount)},
           files={"photo_after": ("r.png", io.BytesIO(_img_bytes()), "image/png")})


def test_bonuses_catalog(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/potions/bonuses")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 15
        by_code = {b["code"]: b for b in data}
        assert by_code["early_level_up"]["label"] == "+1 уровень маршрутного листа"
        assert by_code["early_level_up"]["kind"] == "instant"
        assert by_code["double_order_reward"]["kind"] == "conditional"


def test_activate_instant_bonus(admin_client):
    _seed_potion(123, "early_level_up", activated=False, used=False)
    with make_user_client(123, "player") as c:
        pid = c.get("/api/potions").json()[0]["id"]
        r = c.post(f"/api/potions/{pid}/activate")
        assert r.status_code == 200
        assert r.json()["activated"] is True
        assert r.json()["used"] is True
        assert c.get("/api/me").json()["level"] == 1


def test_activate_conditional_bonus_arms(admin_client):
    _seed_potion(123, "double_order_reward", activated=False, used=False)
    with make_user_client(123, "player") as c:
        pid = c.get("/api/potions").json()[0]["id"]
        r = c.post(f"/api/potions/{pid}/activate")
        assert r.status_code == 200
        assert r.json()["activated"] is True
        assert r.json()["used"] is False


def test_double_order_reward(admin_client):
    _seed_product_inventory(123, 1, 2)
    _seed_potion(123, "double_order_reward", activated=True, used=False)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": 1, "qty": 2}).json()["id"]
    with make_user_client(123, "player") as c:
        c.post(f"/api/orders/{oid}/take")
        r = c.post(f"/api/orders/{oid}/fulfill")
        assert r.status_code == 200
        assert c.get("/api/me").json()["coins"] == 180
        assert c.get("/api/potions").json()[0]["used"] is True


def test_partial_order_full_reward(admin_client):
    _seed_product_inventory(123, 1, 1)
    _seed_potion(123, "partial_order", activated=True, used=False)
    oid = admin_client.post("/api/admin/orders/generate", json={"product_id": 1, "qty": 2}).json()["id"]
    with make_user_client(123, "player") as c:
        c.post(f"/api/orders/{oid}/take")
        r = c.post(f"/api/orders/{oid}/fulfill")
        assert r.status_code == 200
        assert r.json()["status"] == "fulfilled"
        assert c.get("/api/me").json()["coins"] == 90
        assert c.get("/api/potions").json()[0]["used"] is True


def test_fulfill_potion_order_prefers_non_activated(admin_client):
    from models import UserPotion
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        s.add(UserPotion(user_id=123, potion_recipe_id=1, bonus_code="skip_plant_stitch", activated=True, used=False))
        s.add(UserPotion(user_id=123, potion_recipe_id=1, bonus_code="skip_plant_stitch", activated=False, used=False))
        s.commit()
    finally:
        s.close()

    oid = admin_client.post("/api/admin/orders/generate", json={"potion_recipe_id": 1}).json()["id"]
    with make_user_client(123, "player") as c:
        c.post(f"/api/orders/{oid}/take")
        r = c.post(f"/api/orders/{oid}/fulfill")
        assert r.status_code == 200

    s = TestingSessionLocal()
    try:
        rows = s.query(UserPotion).filter(UserPotion.user_id == 123).order_by(UserPotion.id).all()
        activated = [p for p in rows if p.activated]
        used = [p for p in rows if p.used]
        assert len(activated) == 1
        assert activated[0].used is False
        assert len(used) == 1
        assert used[0].activated is False
    finally:
        s.close()


def test_skip_plant_stitch_grows_instantly(admin_client):
    fid = _field_with_bed(admin_client)
    _seed_potion(123, "skip_plant_stitch", activated=True, used=False)
    with make_user_client(123, "player") as c:
        r = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1})
        assert r.status_code == 201
        assert r.json()["plot"]["status"] == "grown"
        assert r.json()["plot"]["required"] == 0
        assert c.get("/api/potions").json()[0]["used"] is True


def test_double_garden_harvest(admin_client, uploads_tmp):
    fid = _field_with_bed(admin_client)
    with make_user_client(123, "player") as c:
        _credit(c, 1000)
        planted = c.post(f"/api/fields/{fid}/cells/1/1/plant", json={"plant_id": 1}).json()
        plot_id = planted["plot"]["id"]
        c.post(f"/api/farm/plots/{plot_id}/invest", json={"amount": planted["plot"]["required"]})
        _seed_potion(123, "double_garden_harvest", activated=True, used=False)
        r = c.post(f"/api/fields/{fid}/cells/1/1/harvest")
        assert r.status_code == 200
        inv = c.get("/api/farm/inventory").json()
        plant_inv = [i for i in inv if i["item_kind"] == "plant"][0]
        assert plant_inv["qty"] == 2
        assert c.get("/api/potions").json()[0]["used"] is True


def test_potions_when_fires_hint(admin_client):
    _seed_potion(123, "double_order_reward", activated=False, used=False)
    with make_user_client(123, "player") as c:
        pots = c.get("/api/potions").json()
        assert len(pots) == 1
        assert pots[0]["when_fires"] is not None
        assert "заказ" in pots[0]["when_fires"]

        bns = {b["code"]: b for b in c.get("/api/potions/bonuses").json()}
        assert bns["double_order_reward"]["when_fires"] == pots[0]["when_fires"]
        assert bns["free_pet"]["when_fires"] == "Применяется сразу при активации"

        r = c.post(f"/api/potions/{pots[0]['id']}/activate")
        assert r.status_code == 200
        assert r.json()["when_fires"] == pots[0]["when_fires"]
