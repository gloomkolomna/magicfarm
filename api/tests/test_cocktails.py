import io

from tests.conftest import TestingSessionLocal, make_user_client


def _img_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (30, 30), (120, 60, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _seed_patient():
    from models import PatientAnimal
    s = TestingSessionLocal()
    try:
        p = PatientAnimal(code="test_rabbit", name="Тестовый кролик", level=1)
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id
    finally:
        s.close()


def _seed_ingredient(code="trava", name="Трава"):
    from models import Ingredient
    s = TestingSessionLocal()
    try:
        ing = Ingredient(code=code, name=name)
        s.add(ing)
        s.commit()
        s.refresh(ing)
        return ing.id
    finally:
        s.close()


def _seed_remedy(code="maz", name="Мазь"):
    from models import Remedy
    s = TestingSessionLocal()
    try:
        r = Remedy(code=code, name=name)
        s.add(r)
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def _seed_inventory_product(vk_id, product_id, qty):
    from models import Inventory
    s = TestingSessionLocal()
    try:
        s.add(Inventory(user_id=vk_id, product_id=product_id, qty=qty))
        s.commit()
    finally:
        s.close()


def _seed_inventory_plant(vk_id, plant_id, qty):
    from models import Inventory
    s = TestingSessionLocal()
    try:
        s.add(Inventory(user_id=vk_id, plant_id=plant_id, qty=qty))
        s.commit()
    finally:
        s.close()


def _seed_user_ingredient(vk_id, ingredient_id, qty):
    from models import UserIngredient
    s = TestingSessionLocal()
    try:
        s.add(UserIngredient(user_id=vk_id, ingredient_id=ingredient_id, qty=qty))
        s.commit()
    finally:
        s.close()


def _seed_user_remedy(vk_id, remedy_id, qty):
    from models import UserRemedy
    s = TestingSessionLocal()
    try:
        s.add(UserRemedy(user_id=vk_id, remedy_id=remedy_id, qty=qty))
        s.commit()
    finally:
        s.close()


def _seed_user_card(vk_id, patient_id):
    from models import UserCard
    s = TestingSessionLocal()
    try:
        s.add(UserCard(user_id=vk_id, patient_id=patient_id))
        s.commit()
    finally:
        s.close()


def _make_items(ingredient_id, remedy_id):
    return [
        {"kind": "product", "item_id": 1, "qty": 1},
        {"kind": "plant", "item_id": 1, "qty": 2},
        {"kind": "ingredient", "item_id": ingredient_id, "qty": 1},
        {"kind": "remedy", "item_id": remedy_id, "qty": 1},
    ]


def _create_recipe(admin_client, ingredient_id, remedy_id, patient_id=None):
    payload = {
        "name": "Лесной коктейль",
        "description": "Освежает",
        "patient_id": patient_id,
        "items": _make_items(ingredient_id, remedy_id),
    }
    r = admin_client.post("/api/admin/cocktail-recipes", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _seed_all_stock(vk_id, ingredient_id, remedy_id):
    _seed_inventory_product(vk_id, 1, 1)
    _seed_inventory_plant(vk_id, 1, 2)
    _seed_user_ingredient(vk_id, ingredient_id, 1)
    _seed_user_remedy(vk_id, remedy_id, 1)


def test_admin_crud_cocktail_recipes(admin_client):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    rid = _create_recipe(admin_client, ing, rem)
    assert rid is not None

    r = admin_client.get("/api/admin/cocktail-recipes")
    assert r.status_code == 200
    recipes = [x for x in r.json() if x["id"] == rid]
    assert len(recipes) == 1
    assert len(recipes[0]["items"]) == 4
    assert {i["kind"] for i in recipes[0]["items"]} == {"product", "plant", "ingredient", "remedy"}

    r = admin_client.put(f"/api/admin/cocktail-recipes/{rid}", json={
        "name": "Коктейль обновлён",
        "items": _make_items(ing, rem),
    })
    assert r.status_code == 200
    assert r.json()["name"] == "Коктейль обновлён"

    r = admin_client.delete(f"/api/admin/cocktail-recipes/{rid}")
    assert r.status_code == 204
    r = admin_client.get("/api/admin/cocktail-recipes")
    assert all(x["id"] != rid for x in r.json())


def test_admin_create_rejects_bad_kind(admin_client):
    r = admin_client.post("/api/admin/cocktail-recipes", json={
        "name": "Плохой коктейль", "items": [{"kind": "alien", "item_id": 1, "qty": 1}],
    })
    assert r.status_code == 400


def test_admin_create_rejects_missing_item(admin_client):
    r = admin_client.post("/api/admin/cocktail-recipes", json={
        "name": "Плохой коктейль", "items": [{"kind": "product", "item_id": 9999, "qty": 1}],
    })
    assert r.status_code == 400


def test_admin_player_forbidden(admin_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/admin/cocktail-recipes")
        assert r.status_code == 403


def test_admin_upload_images(admin_client, uploads_tmp):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    rid = _create_recipe(admin_client, ing, rem)
    r = admin_client.put(
        f"/api/admin/cocktail-recipes/{rid}/image",
        files={"image": ("c.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["image_url"] is not None
    r = admin_client.put(
        f"/api/admin/cocktail-recipes/{rid}/card-image",
        files={"image": ("card.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["card_image_url"] is not None


def test_upload_image_requires_admin(player_client, uploads_tmp):
    r = player_client.put(
        "/api/admin/cocktail-recipes/1/image",
        files={"image": ("c.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 403


def test_list_recipes_unlocked_flag(admin_client):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    patient_id = _seed_patient()
    locked_id = _create_recipe(admin_client, ing, rem, patient_id=patient_id)
    open_id = _create_recipe(admin_client, ing, rem, patient_id=None)

    with make_user_client(123, "player") as c:
        r = c.get("/api/cocktails/recipes")
        assert r.status_code == 200
        by_id = {x["id"]: x for x in r.json()}
        assert by_id[open_id]["unlocked"] is True
        assert by_id[locked_id]["unlocked"] is False
        assert by_id[locked_id]["patient_name"] == "Тестовый кролик"

    _seed_user_card(123, patient_id)
    with make_user_client(123, "player") as c:
        r = c.get("/api/cocktails/recipes")
        by_id = {x["id"]: x for x in r.json()}
        assert by_id[locked_id]["unlocked"] is True


def test_install_shaker_locked_until_card(admin_client):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    patient_id = _seed_patient()
    rid = _create_recipe(admin_client, ing, rem, patient_id=patient_id)
    _seed_all_stock(123, ing, rem)

    with make_user_client(123, "player") as c:
        r = c.post("/api/cocktails/shaker", json={"recipe_id": rid})
        assert r.status_code == 403

    _seed_user_card(123, patient_id)
    with make_user_client(123, "player") as c:
        r = c.post("/api/cocktails/shaker", json={"recipe_id": rid})
        assert r.status_code == 201
        assert r.json()["status"] == "empty"
        assert len(r.json()["items"]) == 4


def test_install_shaker_conflict(admin_client):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    rid = _create_recipe(admin_client, ing, rem)
    _seed_all_stock(123, ing, rem)
    with make_user_client(123, "player") as c:
        assert c.post("/api/cocktails/shaker", json={"recipe_id": rid}).status_code == 201
        r = c.post("/api/cocktails/shaker", json={"recipe_id": rid})
        assert r.status_code == 409


def test_mix_happy_path(admin_client):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    rid = _create_recipe(admin_client, ing, rem)
    _seed_all_stock(123, ing, rem)

    with make_user_client(123, "player") as c:
        sh = c.post("/api/cocktails/shaker", json={"recipe_id": rid}).json()
        items = {i["kind"]: i for i in sh["items"]}
        assert items["product"]["enough"] is True
        assert items["plant"]["enough"] is True
        assert items["ingredient"]["enough"] is True
        assert items["remedy"]["enough"] is True

        r = c.post("/api/cocktails/shaker/mix")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["coins_earned"] == 300
        assert data["coins_balance"] == 300

        me = c.get("/api/me").json()
        assert me["coins"] == 300

        sh = c.get("/api/cocktails/shaker").json()
        assert sh is None

    from models import Inventory, UserIngredient, UserRemedy
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        prod = s.query(Inventory).filter(Inventory.user_id == 123, Inventory.product_id == 1).first()
        assert prod.qty == 0
        plant = s.query(Inventory).filter(Inventory.user_id == 123, Inventory.plant_id == 1).first()
        assert plant.qty == 0
        ui = s.query(UserIngredient).filter(UserIngredient.user_id == 123, UserIngredient.ingredient_id == ing).first()
        assert ui.qty == 0
        ur = s.query(UserRemedy).filter(UserRemedy.user_id == 123, UserRemedy.remedy_id == rem).first()
        assert ur.qty == 0
    finally:
        s.close()


def test_mix_insufficient(admin_client):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    rid = _create_recipe(admin_client, ing, rem)
    _seed_inventory_product(123, 1, 1)
    _seed_inventory_plant(123, 1, 1)
    _seed_user_ingredient(123, ing, 1)
    _seed_user_remedy(123, rem, 1)

    with make_user_client(123, "player") as c:
        c.post("/api/cocktails/shaker", json={"recipe_id": rid})
        r = c.post("/api/cocktails/shaker/mix")
        assert r.status_code == 400
        assert "Джекобоб" in r.json()["detail"]


def test_mix_without_shaker(player_client):
    r = player_client.post("/api/cocktails/shaker/mix")
    assert r.status_code == 409


def test_repeat_mix(admin_client):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    rid = _create_recipe(admin_client, ing, rem)
    _seed_inventory_product(123, 1, 2)
    _seed_inventory_plant(123, 1, 4)
    _seed_user_ingredient(123, ing, 2)
    _seed_user_remedy(123, rem, 2)

    with make_user_client(123, "player") as c:
        assert c.post("/api/cocktails/shaker", json={"recipe_id": rid}).status_code == 201
        assert c.post("/api/cocktails/shaker/mix").json()["coins_balance"] == 300
        assert c.post("/api/cocktails/shaker", json={"recipe_id": rid}).status_code == 201
        assert c.post("/api/cocktails/shaker/mix").json()["coins_balance"] == 600


def _create_bar_field(admin_client, cols=6, rows=4):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Лесной бар", "cols": cols, "rows": rows, "field_kind": "forest_bar",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_bar_zone(c, field_id, zone_kind, col1, row1, col2, row2, recipe_id=None, files=None):
    data = {"zone_kind": zone_kind, "col1": col1, "row1": row1, "col2": col2, "row2": row2}
    if recipe_id is not None:
        data["cocktail_recipe_id"] = recipe_id
    return c.post(f"/api/admin/fields/{field_id}/bar-zones", data=data, files=files)


def test_bar_zone_admin_crud(admin_client):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    rid = _create_recipe(admin_client, ing, rem)
    fid = _create_bar_field(admin_client)

    assert _create_bar_zone(admin_client, fid, "shaker", 0, 0, 1, 1).status_code == 201
    assert _create_bar_zone(admin_client, fid, "book", 2, 0, 3, 1).status_code == 201

    admin_client.put(f"/api/admin/fields/{fid}/cocktail-recipes", json={"recipe_ids": [rid]})
    r = _create_bar_zone(admin_client, fid, "cocktail_card", 4, 0, 5, 1, recipe_id=rid)
    assert r.status_code == 201
    assert r.json()["cocktail_recipe_id"] == rid

    d = admin_client.get(f"/api/admin/fields/{fid}").json()
    kinds = sorted(z["zone_kind"] for z in d["bar_zones"])
    assert kinds == ["book", "cocktail_card", "shaker"]
    assert d["cocktail_recipe_ids"] == [rid]
    assert d["cocktail_recipes"][0]["name"] == "Лесной коктейль"


def test_bar_zone_requires_forest_bar_field(admin_client):
    r = admin_client.post("/api/admin/fields", json={"name": "Обычное", "cols": 6, "rows": 4})
    fid = r.json()["id"]
    r = _create_bar_zone(admin_client, fid, "shaker", 0, 0, 1, 1)
    assert r.status_code == 400


def test_bar_zone_bad_kind(admin_client):
    fid = _create_bar_field(admin_client)
    r = _create_bar_zone(admin_client, fid, "alien", 0, 0, 1, 1)
    assert r.status_code == 400


def test_bar_zone_overlap(admin_client):
    fid = _create_bar_field(admin_client)
    assert _create_bar_zone(admin_client, fid, "shaker", 0, 0, 1, 1).status_code == 201
    r = _create_bar_zone(admin_client, fid, "book", 1, 1, 2, 2)
    assert r.status_code == 409


def test_card_requires_linked_cocktail(admin_client):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    rid = _create_recipe(admin_client, ing, rem)
    fid = _create_bar_field(admin_client)
    r = _create_bar_zone(admin_client, fid, "cocktail_card", 4, 0, 5, 1, recipe_id=rid)
    assert r.status_code == 400


def test_field_detail_has_bar_data(admin_client):
    ing = _seed_ingredient()
    rem = _seed_remedy()
    rid = _create_recipe(admin_client, ing, rem)
    fid = _create_bar_field(admin_client)
    admin_client.put(f"/api/admin/fields/{fid}/cocktail-recipes", json={"recipe_ids": [rid]})
    _create_bar_zone(admin_client, fid, "shaker", 0, 0, 1, 1)
    _create_bar_zone(admin_client, fid, "book", 2, 0, 3, 1)
    _create_bar_zone(admin_client, fid, "cocktail_card", 4, 0, 5, 1, recipe_id=rid)

    with make_user_client(123, "player") as c:
        d = c.get(f"/api/fields/{fid}").json()
        assert d["field_kind"] == "forest_bar"
        kinds = sorted(z["zone_kind"] for z in d["bar_zones"])
        assert kinds == ["book", "cocktail_card", "shaker"]
        assert len(d["cocktail_recipes"]) == 1
        assert d["cocktail_recipes"][0]["unlocked"] is True
        assert d["active_shaker"] is None


def test_bar_zone_image_upload(admin_client, uploads_tmp):
    fid = _create_bar_field(admin_client)
    r = _create_bar_zone(admin_client, fid, "shaker", 0, 0, 1, 1,
                         files={"image": ("s.png", io.BytesIO(_img_bytes()), "image/png")})
    assert r.status_code == 201
    assert r.json()["image_url"] is not None
