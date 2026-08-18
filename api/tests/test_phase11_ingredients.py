import io

from tests.conftest import TestingSessionLocal, make_user_client


def _img_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), (60, 180, 90)).save(buf, format="PNG")
    return buf.getvalue()


def _seed_ingredient(name: str, sort_order: int = 0) -> int:
    from models import Ingredient
    from routes.admin_catalog import _auto_code, _unique_code
    s = TestingSessionLocal()
    try:
        code = _unique_code(_auto_code(name, "ingredient"), Ingredient, s)
        ing = Ingredient(code=code, name=name, sort_order=sort_order)
        s.add(ing)
        s.commit()
        s.refresh(ing)
        return ing.id
    finally:
        s.close()


def _seed_user_ingredient(vk_id: int, ingredient_id: int, qty: int) -> None:
    from models import UserIngredient
    s = TestingSessionLocal()
    try:
        s.add(UserIngredient(user_id=vk_id, ingredient_id=ingredient_id, qty=qty))
        s.commit()
    finally:
        s.close()


def test_admin_create_ingredient_generates_code(admin_client):
    r = admin_client.post("/api/admin/ingredients", json={"name": "Роса", "sort_order": 1})
    assert r.status_code == 201
    data = r.json()
    assert data["code"]
    assert data["name"] == "Роса"
    assert data["sort_order"] == 1


def test_admin_create_ingredient_requires_name(admin_client):
    r = admin_client.post("/api/admin/ingredients", json={"name": "   "})
    assert r.status_code == 400


def test_admin_update_ingredient(admin_client):
    iid = _seed_ingredient("Роса")
    r = admin_client.put(f"/api/admin/ingredients/{iid}", json={"name": "Вода", "sort_order": 5})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Вода"
    assert data["sort_order"] == 5


def test_admin_delete_ingredient(admin_client):
    iid = _seed_ingredient("Роса")
    r = admin_client.delete(f"/api/admin/ingredients/{iid}")
    assert r.status_code == 204
    rows = admin_client.get("/api/admin/ingredients").json()
    assert all(i["id"] != iid for i in rows)


def test_admin_upload_ingredient_image(admin_client, uploads_tmp):
    iid = _seed_ingredient("Роса")
    r = admin_client.put(
        f"/api/admin/ingredients/{iid}/image",
        files={"image": ("i.png", io.BytesIO(_img_bytes()), "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["image_url"]


def test_player_forbidden_on_admin_ingredients(player_client):
    with make_user_client(123, "player") as c:
        assert c.get("/api/admin/ingredients").status_code == 403
        assert c.post("/api/admin/ingredients", json={"name": "Роса"}).status_code == 403
        assert c.put("/api/admin/ingredients/1", json={"name": "X"}).status_code == 403
        assert c.delete("/api/admin/ingredients/1").status_code == 403
        assert c.put(
            "/api/admin/ingredients/1/image",
            files={"image": ("i.png", io.BytesIO(_img_bytes()), "image/png")},
        ).status_code == 403


def test_ingredients_catalog_ordered(player_client):
    _seed_ingredient("Вода", 5)
    _seed_ingredient("Роса", 1)
    with make_user_client(123, "player") as c:
        r = c.get("/api/ingredients")
        assert r.status_code == 200
        assert [i["name"] for i in r.json()] == ["Роса", "Вода"]


def test_ingredients_catalog_requires_auth(client):
    assert client.get("/api/ingredients").status_code == 401


def test_apothecary_empty_after_start(player_client):
    with make_user_client(123, "player") as c:
        r = c.get("/api/apothecary")
        assert r.status_code == 200
        assert r.json() == []


def test_apothecary_shows_qty(player_client):
    iid = _seed_ingredient("Роса")
    _seed_user_ingredient(123, iid, 7)
    with make_user_client(123, "player") as c:
        r = c.get("/api/apothecary")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["ingredient_id"] == iid
        assert data[0]["qty"] == 7


def test_apothecary_requires_auth(client):
    assert client.get("/api/apothecary").status_code == 401
