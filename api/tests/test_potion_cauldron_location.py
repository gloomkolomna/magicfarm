import io
import json

from tests.conftest import make_user_client


def _img_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (30, 30), (120, 60, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _create_brewery_field(admin_client, name="Зельеварня тест", min_level=0):
    r = admin_client.post("/api/admin/fields", json={
        "name": name, "cols": 6, "rows": 4, "field_kind": "brewery", "min_level": min_level,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _bind_recipes(admin_client, fid, recipe_ids):
    r = admin_client.put(f"/api/admin/fields/{fid}/potion-recipes", json={"recipe_ids": recipe_ids})
    assert r.status_code == 200, r.text


def _create_cauldron_zone(admin_client, fid, image_name):
    r = admin_client.post(
        f"/api/admin/fields/{fid}/brewery-zones",
        data={"zone_kind": "cauldron", "col1": 0, "row1": 0, "col2": 1, "row2": 1},
        files={"image": (image_name, io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 201, r.text


def _seed_recipe(name: str, slots: list[str]) -> int:
    from models import PotionRecipe
    from tests.conftest import TestingSessionLocal
    s = TestingSessionLocal()
    try:
        r = PotionRecipe(
            code=f"loc_{name.lower()}", name=name, level="green",
            ingredient_slots=json.dumps(slots), bonus_code=None, reward_coins=100,
        )
        s.add(r)
        s.commit()
        s.refresh(r)
        return r.id
    finally:
        s.close()


def test_create_with_field_id_binds_location(admin_client):
    fid = _create_brewery_field(admin_client, name="Зельеварня А")
    _bind_recipes(admin_client, fid, [1])
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1, "field_id": fid})
        assert r.status_code == 201, r.text
        assert r.json()["field_id"] == fid
        assert r.json()["field_name"] == "Зельеварня А"


def test_create_with_field_id_recipe_not_bound(admin_client):
    fid = _create_brewery_field(admin_client)
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1, "field_id": fid})
        assert r.status_code == 400
        assert "не привязано" in r.json()["detail"]


def test_create_with_field_id_not_brewery(admin_client):
    r = admin_client.post("/api/admin/fields", json={"name": "Просто поле", "cols": 6, "rows": 4})
    fid = r.json()["id"]
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1, "field_id": fid})
        assert r.status_code == 400
        assert "зельеварне" in r.json()["detail"]


def test_create_with_unknown_field_id(admin_client):
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1, "field_id": 99999})
        assert r.status_code == 400


def test_second_cauldron_same_field_conflict(admin_client):
    fid = _create_brewery_field(admin_client)
    _bind_recipes(admin_client, fid, [1])
    with make_user_client(123, "player") as c:
        assert c.post("/api/potions/cauldrons", json={"recipe_id": 1, "field_id": fid}).status_code == 201
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1, "field_id": fid})
        assert r.status_code == 409
        assert "зельеварне" in r.json()["detail"]


def test_parallel_cauldrons_in_different_fields(admin_client):
    fid_a = _create_brewery_field(admin_client, name="Зельеварня А")
    fid_b = _create_brewery_field(admin_client, name="Зельеварня Б")
    second = _seed_recipe("Параллель", ["plant_garden"] * 5)
    _bind_recipes(admin_client, fid_a, [1])
    _bind_recipes(admin_client, fid_b, [second])

    with make_user_client(123, "player") as c:
        r1 = c.post("/api/potions/cauldrons", json={"recipe_id": 1, "field_id": fid_a})
        assert r1.status_code == 201, r1.text
        r2 = c.post("/api/potions/cauldrons", json={"recipe_id": second, "field_id": fid_b})
        assert r2.status_code == 201, r2.text

        actives = c.get("/api/potions/cauldrons/active").json()
        assert isinstance(actives, list)
        assert len(actives) == 2
        by_field = {a["field_id"]: a for a in actives}
        assert by_field[fid_a]["recipe_id"] == 1
        assert by_field[fid_b]["recipe_id"] == second


def test_auto_detect_field_from_binding(admin_client):
    fid = _create_brewery_field(admin_client, name="Зельеварня А")
    _bind_recipes(admin_client, fid, [1])
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        assert r.status_code == 201, r.text
        assert r.json()["field_id"] == fid


def test_field_min_level_blocks_install(admin_client):
    fid = _create_brewery_field(admin_client, min_level=3)
    _bind_recipes(admin_client, fid, [1])
    with make_user_client(123, "player") as c:
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1, "field_id": fid})
        assert r.status_code == 403
        assert "недоступна" in r.json()["detail"]
        r = c.post("/api/potions/cauldrons", json={"recipe_id": 1})
        assert r.status_code == 403


def test_active_cauldron_only_in_own_field(admin_client):
    fid_a = _create_brewery_field(admin_client, name="Зельеварня А")
    fid_b = _create_brewery_field(admin_client, name="Зельеварня Б")
    fid_c = _create_brewery_field(admin_client, name="Зельеварня В")
    second = _seed_recipe("Соседнее", ["plant_garden"] * 5)
    _bind_recipes(admin_client, fid_a, [1])
    _bind_recipes(admin_client, fid_b, [second])

    with make_user_client(123, "player") as c:
        assert c.post("/api/potions/cauldrons", json={"recipe_id": 1, "field_id": fid_a}).status_code == 201
        assert c.post("/api/potions/cauldrons", json={"recipe_id": second, "field_id": fid_b}).status_code == 201

        a = c.get(f"/api/fields/{fid_a}").json()
        assert a["active_cauldron"] is not None
        assert a["active_cauldron"]["recipe_id"] == 1

        b = c.get(f"/api/fields/{fid_b}").json()
        assert b["active_cauldron"] is not None
        assert b["active_cauldron"]["recipe_id"] == second

        c_field = c.get(f"/api/fields/{fid_c}").json()
        assert c_field["active_cauldron"] is None


def test_zone_image_from_own_field(admin_client, uploads_tmp):
    fid_a = _create_brewery_field(admin_client, name="Зельеварня А")
    fid_b = _create_brewery_field(admin_client, name="Зельеварня Б")
    second = _seed_recipe("Картинное", ["plant_garden"] * 5)
    _bind_recipes(admin_client, fid_a, [1])
    _bind_recipes(admin_client, fid_b, [second])
    _create_cauldron_zone(admin_client, fid_a, "a.png")
    _create_cauldron_zone(admin_client, fid_b, "b.png")

    with make_user_client(123, "player") as c:
        assert c.post("/api/potions/cauldrons", json={"recipe_id": 1, "field_id": fid_a}).status_code == 201
        assert c.post("/api/potions/cauldrons", json={"recipe_id": second, "field_id": fid_b}).status_code == 201

        actives = c.get("/api/potions/cauldrons/active").json()
        by_field = {a["field_id"]: a["image_url"] for a in actives}
        assert by_field[fid_a] != by_field[fid_b]
        assert by_field[fid_a] is not None
        assert by_field[fid_b] is not None
