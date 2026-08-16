import io

from tests.conftest import make_user_client


def _img_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (30, 30), (120, 60, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _create_brewery_field(admin_client, cols=6, rows=4):
    r = admin_client.post("/api/admin/fields", json={
        "name": "Зельеварня тест", "cols": cols, "rows": rows, "field_kind": "brewery",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_zone(c, field_id, zone_kind, col1, row1, col2, row2, files=None, recipe_id=None):
    data = {"zone_kind": zone_kind, "col1": col1, "row1": row1, "col2": col2, "row2": row2}
    if recipe_id is not None:
        data["recipe_id"] = recipe_id
    return c.post(f"/api/admin/fields/{field_id}/brewery-zones", data=data, files=files)


def test_create_cauldron_zone_with_image(admin_client, uploads_tmp):
    fid = _create_brewery_field(admin_client)
    r = _create_zone(admin_client, fid, "cauldron", 0, 0, 1, 1, files={"image": ("c.png", io.BytesIO(_img_bytes()), "image/png")})
    assert r.status_code == 201, r.text
    z = r.json()
    assert z["zone_kind"] == "cauldron"
    assert z["image_url"] is not None
    assert z["recipe_id"] is None


def test_create_jar_zone(admin_client):
    fid = _create_brewery_field(admin_client)
    r = _create_zone(admin_client, fid, "jar", 2, 0, 3, 1)
    assert r.status_code == 201
    assert r.json()["zone_kind"] == "jar"


def test_zone_requires_brewery_field(admin_client):
    r = admin_client.post("/api/admin/fields", json={"name": "Обычное поле", "cols": 6, "rows": 4})
    fid = r.json()["id"]
    r = _create_zone(admin_client, fid, "cauldron", 0, 0, 1, 1)
    assert r.status_code == 400


def test_zone_bad_kind(admin_client):
    fid = _create_brewery_field(admin_client)
    r = _create_zone(admin_client, fid, "alien", 0, 0, 1, 1)
    assert r.status_code == 400


def test_zone_out_of_bounds(admin_client):
    fid = _create_brewery_field(admin_client)
    r = _create_zone(admin_client, fid, "cauldron", 5, 3, 6, 4)
    assert r.status_code == 400


def test_zone_overlap(admin_client):
    fid = _create_brewery_field(admin_client)
    assert _create_zone(admin_client, fid, "cauldron", 0, 0, 1, 1).status_code == 201
    r = _create_zone(admin_client, fid, "jar", 1, 1, 2, 2)
    assert r.status_code == 409


def test_ingredient_zone_single_cell_only(admin_client):
    fid = _create_brewery_field(admin_client)
    r = _create_zone(admin_client, fid, "ingredient", 0, 0, 1, 0)
    assert r.status_code == 400


def test_ingredient_zone_max_six(admin_client):
    fid = _create_brewery_field(admin_client)
    for i in range(6):
        r = _create_zone(admin_client, fid, "ingredient", i, 3, i, 3)
        assert r.status_code == 201, f"окошко {i}"
    r = _create_zone(admin_client, fid, "ingredient", 0, 2, 0, 2)
    assert r.status_code == 400


def test_recipe_card_requires_recipe(admin_client):
    fid = _create_brewery_field(admin_client)
    r = _create_zone(admin_client, fid, "recipe_card", 4, 0, 5, 1)
    assert r.status_code == 400


def test_recipe_card_requires_linked_recipe(admin_client):
    fid = _create_brewery_field(admin_client)
    r = _create_zone(admin_client, fid, "recipe_card", 4, 0, 5, 1, recipe_id=1)
    assert r.status_code == 400
    r = admin_client.put(f"/api/admin/fields/{fid}/potion-recipes", json={"recipe_ids": [1]})
    assert r.status_code == 200
    assert r.json() == [1]
    r = _create_zone(admin_client, fid, "recipe_card", 4, 0, 5, 1, recipe_id=1)
    assert r.status_code == 201
    assert r.json()["recipe_id"] == 1


def test_admin_field_detail_returns_potion_recipes(admin_client):
    fid = _create_brewery_field(admin_client)
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert detail["potion_recipes"] == []
    assert detail["potion_recipe_ids"] == []

    admin_client.put(f"/api/admin/fields/{fid}/potion-recipes", json={"recipe_ids": [1]})
    detail = admin_client.get(f"/api/admin/fields/{fid}").json()

    assert detail["potion_recipe_ids"] == [1]
    recipes = detail["potion_recipes"]
    assert len(recipes) == 1
    assert recipes[0]["id"] == 1
    assert recipes[0]["name"] == "Сонное пророчество"
    assert recipes[0]["ingredient_slots"] == ["plant_garden", "plant_garden", "plant_garden", "alchemy"]


def test_recipe_id_only_for_card(admin_client):
    fid = _create_brewery_field(admin_client)
    r = _create_zone(admin_client, fid, "cauldron", 0, 0, 1, 1, recipe_id=1)
    assert r.status_code == 400


def test_upload_zone_image(admin_client, uploads_tmp):
    fid = _create_brewery_field(admin_client)
    zid = _create_zone(admin_client, fid, "cauldron", 0, 0, 1, 1).json()["id"]
    r = admin_client.put(
        f"/api/admin/fields/{fid}/brewery-zones/{zid}/image",
        files={"image": ("c2.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["image_url"] is not None


def test_delete_zone(admin_client):
    fid = _create_brewery_field(admin_client)
    zid = _create_zone(admin_client, fid, "jar", 2, 0, 3, 1).json()["id"]
    r = admin_client.delete(f"/api/admin/fields/{fid}/brewery-zones/{zid}")
    assert r.status_code == 204
    r = admin_client.delete(f"/api/admin/fields/{fid}/brewery-zones/{zid}")
    assert r.status_code == 404


def test_zones_in_field_detail(admin_client):
    fid = _create_brewery_field(admin_client)
    admin_client.put(f"/api/admin/fields/{fid}/potion-recipes", json={"recipe_ids": [1]})
    _create_zone(admin_client, fid, "cauldron", 0, 0, 1, 1)
    _create_zone(admin_client, fid, "recipe_card", 4, 0, 5, 1, recipe_id=1)
    r = admin_client.get(f"/api/admin/fields/{fid}")
    assert r.status_code == 200
    d = r.json()
    kinds = sorted(z["zone_kind"] for z in d["brewery_zones"])
    assert kinds == ["cauldron", "recipe_card"]
    assert d["potion_recipe_ids"] == [1]


def test_unlink_recipe_deletes_its_card_zone(admin_client):
    fid = _create_brewery_field(admin_client)
    admin_client.put(f"/api/admin/fields/{fid}/potion-recipes", json={"recipe_ids": [1]})
    zid = _create_zone(admin_client, fid, "recipe_card", 4, 0, 5, 1, recipe_id=1).json()["id"]
    admin_client.put(f"/api/admin/fields/{fid}/potion-recipes", json={"recipe_ids": []})
    d = admin_client.get(f"/api/admin/fields/{fid}").json()
    assert d["brewery_zones"] == []
    assert d["potion_recipe_ids"] == []
    r = admin_client.delete(f"/api/admin/fields/{fid}/brewery-zones/{zid}")
    assert r.status_code == 404


def test_player_cannot_create_zone(admin_client):
    fid = _create_brewery_field(admin_client)
    with make_user_client(123, "player") as c:
        r = _create_zone(c, fid, "cauldron", 0, 0, 1, 1)
        assert r.status_code == 403


def test_upload_potion_card_image(admin_client, uploads_tmp):
    r = admin_client.put(
        "/api/admin/potion-recipes/1/card-image",
        files={"image": ("card.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["card_image_url"] is not None


def test_card_image_requires_admin(player_client, uploads_tmp):
    r = player_client.put(
        "/api/admin/potion-recipes/1/card-image",
        files={"image": ("card.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 403


def _seed_brewery(admin_client):
    fid = _create_brewery_field(admin_client)
    admin_client.put(f"/api/admin/fields/{fid}/potion-recipes", json={"recipe_ids": [1]})
    _create_zone(admin_client, fid, "cauldron", 0, 0, 1, 1)
    _create_zone(admin_client, fid, "jar", 2, 0, 3, 1)
    _create_zone(admin_client, fid, "ingredient", 0, 2, 0, 2)
    _create_zone(admin_client, fid, "recipe_card", 4, 0, 5, 1, recipe_id=1)
    return fid


def test_brewery_field_public_detail(admin_client):
    fid = _seed_brewery(admin_client)
    with make_user_client(123, "player") as c:
        r = c.get(f"/api/fields/{fid}")
        assert r.status_code == 200
        d = r.json()
        kinds = sorted(z["zone_kind"] for z in d["brewery_zones"])
        assert kinds == ["cauldron", "ingredient", "jar", "recipe_card"]
        card = next(z for z in d["brewery_zones"] if z["zone_kind"] == "recipe_card")
        assert card["recipe_name"] == "Сонное пророчество"
        assert len(d["potion_recipes"]) == 1
        assert d["active_cauldron"] is None


def test_brewery_field_active_cauldron(admin_client):
    from tests.test_phase8_potions import _seed_plant_inventory, _seed_product_inventory
    fid = _seed_brewery(admin_client)
    _seed_plant_inventory(123, 1, 5)
    _seed_product_inventory(123, 1, 5)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        assert r.status_code == 201
        d = c.get(f"/api/fields/{fid}").json()
        assert d["active_cauldron"] is not None
        assert d["active_cauldron"]["recipe_id"] == 1
        assert d["active_cauldron"]["status"] == "empty"
        assert len(d["active_cauldron"]["slots"]) == 4

        cid = d["active_cauldron"]["id"]
        for i in range(3):
            c.post(f"/api/potions/cauldrons/{cid}/slot/{i}", json={"item_kind": "plant", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/slot/3", json={"item_kind": "product", "item_id": 1})
        c.post(f"/api/potions/cauldrons/{cid}/brew")

        d = c.get(f"/api/fields/{fid}").json()
        assert d["active_cauldron"] is None


def test_non_brewery_field_has_no_brewery_data(admin_client):
    r = admin_client.post("/api/admin/fields", json={"name": "Просто поле", "cols": 6, "rows": 4})
    fid = r.json()["id"]
    with make_user_client(123, "player") as c:
        d = c.get(f"/api/fields/{fid}").json()
        assert d["brewery_zones"] == []
        assert d["potion_recipes"] == []
        assert d["active_cauldron"] is None
